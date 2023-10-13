from datetime import timedelta

from django.conf import settings
from django.contrib.postgres.fields import HStoreField
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils.timezone import now
from versatileimagefield.fields import VersatileImageField
from versatileimagefield.image_warmer import VersatileImageFieldWarmer

User = settings.AUTH_USER_MODEL


class ProductCategory(models.Model):
    username = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=50)
    technical_details_template = HStoreField()

    def __str__(self):
        return self.name


class ProductType(models.Model):
    category = models.ForeignKey(ProductCategory, related_name="types", on_delete=models.CASCADE)
    username = models.CharField(max_length=20)
    name = models.CharField(max_length=50)
    technical_details_template = HStoreField()

    def __str__(self):
        return self.name


class BrandPlan(models.Model):
    plan_id = models.CharField(unique=True, max_length=10)
    name = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=9, decimal_places=0)
    product_space = models.PositiveIntegerField()
    area_covered = models.CharField(max_length=50)
    validity_duration = models.DurationField(help_text='Validity period in days', default=timedelta(days=28))

    def __str__(self):
        return self.name


class Brand(models.Model):
    IMG_MAX_WIDTH = 720

    username = models.CharField(max_length=50, unique=True)
    owner = models.OneToOneField(User, on_delete=models.CASCADE)
    public_username = models.CharField(max_length=50)
    title = models.CharField(max_length=50)
    hero_image = VersatileImageField(verbose_name='Brand hero image', upload_to='brand_images/')
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return self.public_username
        
    def get_thumb(self):
        # thumb = self.hero_image.thumbnail['480x360']
        thumb = self.hero_image.thumbnail('360x270')
        thumb.save("thumbnails")
        return thumb

    def delete_hero_image(self):
        self.hero_image.delete_all_created_images()
        self.hero_image.delete(save=False)

    def check_plans_validity(self):
        try:
            plan_queue = self.plans
            current_active_plan = plan_queue.get(is_active=True)
            if current_active_plan.is_valid():
                # the current active plan is still running
                pass
            else:
                # current active plan has expired check for next plan in plan queue
                # and delete the old plans
                expired_plans = plan_queue.filter(date_end__lt=now())

                # Keep a latest expired plan so that if no recharhge done we can show
                # the termination date of brand using that plan. ie: 1 week after expired plan
                if expired_plans.count() > 0:
                    # latest_expired_plan = expired_plans.latest('date_end')

                    # # excluding the latest expired plan from list
                    # expired_plans = expired_plans.exclude(id=latest_expired_plan.id)
                    expired_plans.delete()

                upcoming_plans = plan_queue.filter(date_end__gt=now())
                if upcoming_plans.count() > 0:
                    new_plan = upcoming_plans.first()
                    new_plan.is_active = True
                    new_plan.save()
                    if not self.is_active:
                        self.is_active = True
                        self.save()

                else:
                    # if latest_expired_plan.date_end + timedelta(days=8) > now():
                        # # terminate the brand
                        # # deleting the image from storage
                        # self.delete_hero_image()
                        # self.delete()

                    # else:
                    self.is_active = False
                    self.save()

        except self.plans.model.DoesNotExist:
            return None

    def have_active_plan(self):
        try:
            self.plans.get(is_active=True)
            return True

        except self.plans.model.DoesNotExist:
            return False

    def get_active_plan(self):
        try:
            active_plan = self.plans.get(is_active=True)
            return active_plan

        except self.plans.model.DoesNotExist:
            return None


@receiver(post_delete, sender=Brand)
def delete_Brand_instance(sender, instance, **kwargs):
    owner = instance.owner
    owner.is_brand_owner = False
    owner.save()
    # Deletes Image Renditions
    instance.hero_image.delete_all_created_images()
    # Deletes Original Image
    instance.hero_image.delete(save=False)
    

class ApplicationStatus(models.Model):
    status_code = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=50)
    description = models.CharField(max_length=255)
    
    def __str__(self):
        return self.title


class BrandApplication(models.Model):
    brand = models.OneToOneField(Brand, related_name="application", on_delete=models.CASCADE)
    status = models.ForeignKey(ApplicationStatus, on_delete=models.DO_NOTHING, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    errors = HStoreField(default=dict)

    def __str__(self):
        return self.brand.public_username


class BrandPlanQueueManager(models.Manager):
    def add_plan_to_queue(self, plan_id=None, brand_id=None, plan=None, brand=None, order_id=None):
        try:
            plan = BrandPlan.objects.get(id=plan_id) if plan_id else plan
            brand = Brand.objects.get(id=brand_id) if brand_id else brand

            def add_to_plan_queue(date_start, date_end, is_active=False):
                brand_plan = self.model(brand=brand, product_space=plan.product_space, plan=plan, is_active=is_active,
                                        date_start=date_start, order_id=order_id, date_end=date_end)
                brand_plan.save()
                if not brand.is_active:
                    brand.is_active = True
                    brand.save()

                return brand_plan

            no_brand_plans_in_queue = brand.plans.count()

            if no_brand_plans_in_queue == 0:
                brand_plan = add_to_plan_queue(is_active=True, date_start=now(),
                                               date_end=now() + plan.validity_duration)

            else:
                brand_plans = brand.plans
                latest_shop_plan_in_queue = brand_plans.latest('added_at')
                # New plan start date will be equal to previous plan end date if previous plan is still active
                latest_plan_end_date = latest_shop_plan_in_queue.date_end
                end_date = latest_plan_end_date + plan.validity_duration

                if latest_plan_end_date < now():
                    # it means the brand do not have any active plans. All plans have expired.
                    # and will be removed from table by cron job
                    brand_plans.update(is_active=False)
                    brand_plan = add_to_plan_queue(is_active=True, date_start=now(),
                                                   date_end=now() + plan.validity_duration)
                else:
                    # brand have either active plan or extra future plan in queue. Add another plan in queue
                    # This plan will not be active and will continue the dates from previous latest plan
                    brand_plan = add_to_plan_queue(is_active=False, date_start=latest_plan_end_date, date_end=end_date)

            return brand_plan

        except self.model.DoesNotExist:
            raise Exception("No brand plan exist with that id")

        except Brand.DoesNotExist:
            raise Exception("No brand with that id exist")


class PlanQueue(models.Model):
    brand = models.ForeignKey(Brand, related_name="plans", on_delete=models.CASCADE)
    plan = models.ForeignKey(BrandPlan, on_delete=models.SET_NULL, null=True)
    is_active = models.BooleanField(default=False)
    order_id = models.UUIDField(unique=True, null=True, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)
    product_space = models.PositiveIntegerField(default=30)
    date_start = models.DateTimeField()
    date_end = models.DateTimeField()

    objects = BrandPlanQueueManager()

    def __str__(self):
        return self.plan.name

    def is_expired(self):
        is_expired = self.date_end < now()
        return is_expired

    def is_valid(self):
        is_valid = self.date_start < now() < self.date_end
        return is_valid
        

class MeasurementUnit(models.Model):
    # unit = models.CharField(max_length=10)
    name = models.CharField(max_length=20)
    
    def __str__(self):
        return self.name


class Product(models.Model):
    IMG_MAX_WIDTH = 480

    title = models.CharField(max_length=100)
    brand = models.ForeignKey(Brand, related_name='products', on_delete=models.CASCADE)
    thumb_overlay_text = models.CharField(max_length=64, null=True, blank=True)
    measurement_unit = models.ForeignKey(MeasurementUnit, on_delete=models.SET_NULL, null=True, blank=True)
    mrp = models.DecimalField(null=True, blank=True, max_digits=9, decimal_places=0)
    category = models.ForeignKey(ProductCategory, related_name="items", on_delete=models.DO_NOTHING)
    type = models.ForeignKey(ProductType, related_name="items", on_delete=models.DO_NOTHING)
    description = models.CharField(max_length=200)
    long_description = models.TextField(max_length=1000)
    is_available = models.BooleanField(default=True)
    technical_details = HStoreField()

    def __str__(self):
        return self.title

    def have_mrp(self):
        return True if self.mrp else False

    def get_thumb(self):
        image = self.images.get(position=0).image
        thumb = image.thumbnail['200x250']
        return thumb


class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    image = VersatileImageField('Image', upload_to='product_images/')
    position = models.IntegerField(default=1)

    def __str__(self):
        image_url = self.image.url
        return image_url


@receiver(post_delete, sender=ProductImage)
def delete_ProductImage_images(sender, instance, **kwargs):
    # Deletes Image Renditions
    instance.image.delete_all_created_images()
    # Deletes Original Image
    instance.image.delete(save=False)
    
@receiver(post_save, sender=ProductImage)
def warm_ProductImage_images(sender, instance, **kwargs):
    instance_position = instance.position
    if instance_position == 0:
        product_img_warmer = VersatileImageFieldWarmer(instance_or_queryset=instance,
                                                       rendition_key_set='product_image',
                                                       image_attr='image')
        product_img_warmer.warm()

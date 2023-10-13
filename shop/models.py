import datetime
from json import dumps
from random import randint
from django.conf import settings
from django.contrib.gis.db.models import PointField
from django.contrib.postgres.fields import HStoreField
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils.timezone import now
from versatileimagefield.fields import VersatileImageField
from versatileimagefield.image_warmer import VersatileImageFieldWarmer

from product.models import ApplicationStatus
from product.models import Product
from search.env import MANDI_LOCATION
from core.utils import image_from_64

User = settings.AUTH_USER_MODEL


class PopularPlace(models.Model):
    IMG_MAX_WIDTH = 240 # It's a square, 240x240

    name = models.CharField(max_length=50)
    location = PointField(geography=True, srid=4326)
    image = VersatileImageField(null=True, upload_to="popular_places/")

    def delete_image(self):
        # remove image from storage
        if self.image:
            self.image.delete_all_created_images()
            self.image.delete(save=False)

    def __str__(self):
        return self.name
        
@receiver(post_delete, sender=PopularPlace)
def delete_PopularPlace_instance(sender, instance, **kwargs):
    instance.delete_image()


class ShopPlan(models.Model):
    plan_id = models.CharField(unique=True, max_length=10)
    name = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=9, decimal_places=0)
    product_space = models.PositiveIntegerField()
    validity_duration = models.DurationField(help_text='Validity period in days', default=datetime.timedelta(days=28))

    def __str__(self):
        return self.name


class Shop(models.Model):
    IMG_MAX_WIDTH = 720

    default_return_refund_policy = dumps(
        ["Item should be in the same good condition as it was when customer bought it.",
         "The return and refund window will only remain open for 7 days after customer have made the purchase.",
         "There should be no markings, names, ink or anything that was not previously on the product.",
         "Exchange of the product with other similar product will be preferred from our shop."])
    default_off_days = dumps([0])

    title = models.CharField(max_length=100)
    username = models.CharField(max_length=50, unique=True)
    public_username = models.CharField(max_length=50)
    contact_number = models.CharField(max_length=10, null=True)
    website = models.URLField(max_length=255, null=True, blank=True)
    hero_image = VersatileImageField(verbose_name='shop hero image', upload_to='shop_images/')
    owner = models.OneToOneField(User, on_delete=models.CASCADE)
    about = models.CharField(max_length=1024, default="About my shop")
    # cluster = models.ForeignKey(Cluster, on_delete=models.DO_NOTHING, null=True, blank=True)
    is_active = models.BooleanField(default=False)
    is_open_today = models.BooleanField(default=True)
    open_at = models.TimeField(default=datetime.time(8, 0, 0))
    close_at = models.TimeField(default=datetime.time(18, 0, 0))
    off_days = models.CharField(max_length=32, default=default_off_days)
    address = models.CharField(max_length=250)
    location = PointField(geography=True, srid=4326, null=True)
    return_refund_policy = models.TextField(null=True, blank=True, default=default_return_refund_policy,
                                            max_length=4 * 200)

    def __str__(self):
        return self.public_username
        
    def get_thumb(self):
        thumb = self.hero_image.thumbnail['360x270']
        return thumb
        
    def warm_image(self):
        shop_img_warmer = VersatileImageFieldWarmer(instance_or_queryset=self, rendition_key_set='hero_image',
                                                image_attr='hero_image')
        shop_img_warmer.warm()

    def delete_hero_image(self):
        # remove hero_image from storage
        self.hero_image.delete_all_created_images()
        self.hero_image.delete(save=False)
        
    def update_hero_image(self, base64image):
        suffix = randint(100, 999)
        img_name = f'{self.public_username}-${suffix}'
        hero_img_file = image_from_64(base64image, img_name, max_width=Shop.IMG_MAX_WIDTH)
        if self.hero_image:
            self.delete_hero_image()
        self.hero_image.save(hero_img_file.name, hero_img_file, save=False)
        self.save()
        self.warm_image()

    def occupied_space(self):
        # A shop product, food item occupy a space of 1 unit
        # A combo product, service occupy a space of 2 units
        no_of_combos = self.combos.count()
        no_of_products = self.products.count()
        return no_of_products + no_of_combos * 2

    def remaining_space(self):
        active_plan = self.get_active_plan()

        if active_plan:
            remaining_space = active_plan.product_space - self.occupied_space()
            return remaining_space

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
                if expired_plans.count() > 0:
                    expired_plans.delete()

                upcoming_plans = plan_queue.filter(date_end__gt=now())
                if upcoming_plans.count() > 0:
                    new_plan = upcoming_plans.first()
                    new_plan.is_active = True
                    new_plan.save()

                else:
                    self.is_active = False
                    self.save()

        except self.plans.model.DoesNotExist:
            if self.is_active:
                self.is_active = False
                self.save()

    def have_active_plan(self):
        try:
            self.plans.get(is_active=True)
            return True

        except self.plans.model.DoesNotExist:
            return False

    def is_open_now(self):
        pass

    def get_active_plan(self):
        try:
            active_plan = self.plans.get(is_active=True)
            return active_plan

        except self.plans.model.DoesNotExist:
            return None


@receiver(post_delete, sender=Shop)
def delete_Shop_instance(sender, instance, **kwargs):
    owner = instance.owner
    owner.is_shop_owner = False
    owner.save()
    # Deletes Image Renditions
    instance.hero_image.delete_all_created_images()
    # Deletes Original Image
    instance.hero_image.delete(save=False)
    
# @receiver(post_save, sender=Shop)
# def warm_Shop_image(sender, instance, **kwargs):
    # shop_img_warmer = VersatileImageFieldWarmer(instance_or_queryset=instance, rendition_key_set='hero_image',
                                                # image_attr='hero_image')
    # shop_img_warmer.warm()


class ShopPlanQueueManager(models.Manager):
    def add_plan_to_queue(self, plan_id=None, shop_id=None, plan=None, shop=None, order_id=None):
        try:
            plan = ShopPlan.objects.get(id=plan_id) if plan_id else plan
            shop = Shop.objects.get(id=shop_id) if shop_id else shop

            def add_to_plan_queue(date_start, date_end, is_active=False):
                shop_plan = self.model(shop=shop, product_space=plan.product_space, plan=plan, is_active=is_active,
                                       date_start=date_start, order_id=order_id, date_end=date_end)
                shop_plan.save()
                if not shop.is_active:
                    shop.is_active = True
                    shop.save()

                return shop_plan

            no_shop_plans_in_queue = shop.plans.count()

            if no_shop_plans_in_queue == 0:
                shop_plan = add_to_plan_queue(is_active=True, date_start=now(),
                                              date_end=now() + plan.validity_duration)

            else:
                latest_shop_plan_in_queue = shop.plans.latest('added_at')
                # New plan start date will be equal to previous plan end date if previous plan is still active
                latest_plan_end_date = latest_shop_plan_in_queue.date_end
                end_date = latest_plan_end_date + plan.validity_duration

                if latest_plan_end_date < now():
                    # it means the shop do not have any active plans. All plans have expired.
                    # and will be reomved from table by cron job
                    shop_plan = add_to_plan_queue(is_active=True, date_start=now(),
                                                  date_end=now() + plan.validity_duration)
                else:
                    # shop have either active plan or extra future plan in queue. Add another plan in queue
                    # This plan will not be active and will continue the dates from previous latest plan
                    shop_plan = add_to_plan_queue(is_active=False, date_start=latest_plan_end_date, date_end=end_date)

            return shop_plan

        except self.model.DoesNotExist:
            raise Exception("No plan exist with that id")

        except Shop.DoesNotExist:
            raise Exception("No shop with that id exist")


class PlanQueue(models.Model):
    shop = models.ForeignKey(Shop, related_name="plans", on_delete=models.CASCADE)
    plan = models.ForeignKey(ShopPlan, on_delete=models.SET_NULL, null=True)
    is_active = models.BooleanField(default=False)
    order_id = models.UUIDField(unique=True, null=True, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)
    product_space = models.PositiveIntegerField(default=30)
    date_start = models.DateTimeField()
    date_end = models.DateTimeField()

    objects = ShopPlanQueueManager()

    # Convert uuid to str:-  str(uuid_obj)
    # convert str to uuid: uuid.UUID(uuid_str)

    def __str__(self):
        return self.shop.public_username + ' ' + self.plan.name

    def is_valid(self):
        is_valid = self.date_start < now() < self.date_end
        return is_valid


class ShopApplication(models.Model):
    shop = models.OneToOneField(Shop, related_name="application", on_delete=models.CASCADE)
    status = models.ForeignKey(ApplicationStatus, null=True, blank=True, on_delete=models.SET_NULL)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    errors = HStoreField(default=dict)

    def __str__(self):
        return self.shop.public_username


class ShopProduct(models.Model):
    shop = models.ForeignKey(Shop, related_name='products', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    offered_price = models.DecimalField(default=0, max_digits=9, decimal_places=0)
    in_stock = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self):
        return self.product.title


class Combo(models.Model):
    shop = models.ForeignKey(Shop, related_name="combos", on_delete=models.CASCADE)
    offered_price = models.DecimalField(max_digits=9, decimal_places=0, default=0)
    # It is sum of combo_product.quantity * combo_product.shop_product.offered_price
    # offered_price of combo can not be greater than of the offered_price of its consisting shop_products
    max_offered_price = models.DecimalField(max_digits=9, decimal_places=0, default=0)
    name = models.CharField(max_length=200)
    thumbs = models.TextField(null=True, blank=True)
    # Total cost - cost when all the products in combo are bought at mrp
    total_cost = models.DecimalField(max_digits=9, decimal_places=0, null=True)
    description = models.CharField(max_length=255)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self):
        return self.name
    
    def update_thumbs(self):
        combo_products = self.products
        
        thumbs = []
        
        for combo_product in combo_products.all():
            product = combo_product.shop_product.product
            
            thumb_src = product.get_thumb().name
            thumb_overlay_text = product.thumb_overlay_text
            thumb = {
            "src": thumb_src,
            "overlayText": thumb_overlay_text,
            "quantity": quantity
            }
            thumbs.append(thumb)
            
        self.thumbs = dumps(thumbs)
        self.save()
        
    def update_is_available(self):
        combo_products = self.products
        
        is_available = True
        
        for combo_product in combo_products.all():
            in_stock  = combo_product.shop_product.in_stock
            if not in_stock:
                is_available = False
                break
        self.is_available = is_available
    
    def update_prices(self):
        combo_products = self.products
        
        max_offered_price = 0
        total_cost = 0
        
        for combo_product in combo_products.all():
            quantity = combo_product.quantity
            shop_product = combo_product.shop_product
            mrp = shop_product.product.mrp
            offered_price = shop_product.offered_price
            
            cost_subtotal = mrp * quantity if mrp else offered_price * quantity
            max_offered_price_subtotal = offered_price * quantity
            
            total_cost += cost_subtotal
            max_offered_price += max_offered_price_subtotal
        
        self.max_offered_price = max_offered_price
        self.total_cost = total_cost
        self.save()


class ComboProduct(models.Model):
    combo = models.ForeignKey(Combo, related_name="products", on_delete=models.CASCADE)
    shop_product = models.ForeignKey(ShopProduct, related_name='combo_products', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.shop_product.product.title


@receiver(post_delete, sender=ComboProduct)
def handle_ComboProduct_delete(sender, instance, **kwargs):
    # When the brand product is deleted -> shop product deleted -> Delete the combo
    try:
        instance.combo.delete()

    except Combo.DoesNotExist:
        pass

import graphene
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.timezone import now
from django_filters import FilterSet, OrderingFilter
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from graphql_jwt.decorators import login_required, user_passes_test, superuser_required
from graphql_relay.node.node import from_global_id

from core.utils import image_from_64
from search.postgresql_search import search_products_in_brand
from .models import Product, ProductCategory, ProductType, ProductImage, Brand, ApplicationStatus, BrandPlan, \
    BrandApplication, PlanQueue, MeasurementUnit

User = get_user_model()


class MeasurementUnitNode(DjangoObjectType):
    class Meta:
        model = MeasurementUnit
        filter_fields = ['name']
        interfaces = (graphene.relay.Node,)
        

class BrandPlanQueueNode(DjangoObjectType):
    class Meta:
        model = PlanQueue
        filter_fields = ['is_active', 'brand', 'plan']
        interfaces = (graphene.relay.Node,)

    is_valid = graphene.Boolean()

    def resolve_is_valid(self, info):
        return self.is_valid()


class BrandNode(DjangoObjectType):
    class Meta:
        model = Brand
        filter_fields = ['username']
        interfaces = (graphene.relay.Node,)

    occupied_space = graphene.Int()
    have_active_plan = graphene.Boolean()
    active_plan = graphene.Field(BrandPlanQueueNode)

    def resolve_occupied_space(self, info, **kwargs):
        space = self.products.count()
        return space

    def resolve_have_active_plan(self, info, **kwargs):
        return self.have_active_plan()

    def resolve_active_plan(self, info, **kwargs):
        return self.get_active_plan()


class BrandNodeConnections(graphene.relay.Connection):
    class Meta:
        node = BrandNode


class BrandApplicationNode(DjangoObjectType):
    class Meta:
        model = BrandApplication
        filter_fields = ['id', 'brand', 'status', 'submitted_at']
        interfaces = (graphene.relay.Node,)


class BrandPlanNode(DjangoObjectType):
    class Meta:
        model = BrandPlan
        filter_fields = ['plan_id']
        interfaces = (graphene.relay.Node,)

    validity_duration = graphene.String()

    def resolve_validity_duration(self, info, **kwargs):
        return str(self.validity_duration)


class ApplicationStatusNode(DjangoObjectType):
    class Meta:
        model = ApplicationStatus
        filter_fields = ['status_code']
        interfaces = (graphene.relay.Node,)


class ProductNode(DjangoObjectType):
    class Meta:
        model = Product
        filter_fields = ['title', 'id']
        interfaces = (graphene.relay.Node,)

    thumb = graphene.String()
    is_service = graphene.Boolean()
    is_food = graphene.Boolean()
    measurement_unit = graphene.String()

    def resolve_is_food(self, info, **kwargs):
        category = self.category
        is_food = category.username == "raspaaifood"
        return is_food
        
    def resolve_measurement_unit(self, info, **kwargs):
        unit = self.measurement_unit.name if self.measurement_unit else None
        return unit

    def resolve_is_service(self, info, **kwargs):
        category = self.category
        is_service = category.username == 'raspaaiservices'
        return is_service

    def resolve_thumb(self, info, **kwargs):
        # Using image.name preserve consitency between non-thumb images and thumb images
        # sized image when returned driectly they return the image.url which include "/media"
        # while simple non-sized images return image url do not contain "/media"
        thumb_name = self.get_thumb().name
        return thumb_name


class ProductNodeConnections(graphene.relay.Connection):
    class Meta:
        node = ProductNode

    # count = graphene.Int()
    #
    # def resolve_count(root, info):
    #     return len(root.edges)


class ProductImageNode(DjangoObjectType):
    class Meta:
        model = ProductImage
        filter_fields = ['id']
        interfaces = (graphene.relay.Node,)


class ProductCategoryNode(DjangoObjectType):
    class Meta:
        model = ProductCategory
        filter_fields = ['id', 'name']
        interfaces = (graphene.relay.Node,)


class ProductTypeNode(DjangoObjectType):
    class Meta:
        model = ProductType
        filter_fields = ['id', 'name', 'category']
        interfaces = (graphene.relay.Node,)


class AdminAddBrand(graphene.relay.ClientIDMutation):
    brand = graphene.Field(BrandNode)

    class Input:
        brand_username = graphene.String(required=True)
        hero_img64 = graphene.String(required=True)
        brand_name = graphene.String(required=True)
        owner_email = graphene.String(required=True)
        plan_id = graphene.ID(required=True)

    @classmethod
    @superuser_required
    def mutate_and_get_payload(cls, root, info, **input):
        public_username = input.get('brand_username')
        hero_img64 = input.get('hero_img64')
        owner_email = input.get('owner_email')
        brand_name = input.get('brand_name')
        plan_id = from_global_id(input.get('plan_id'))[1]

        try:
            owner = User.objects.get(email=owner_email)
            if owner.is_brand_owner:
                raise Exception("This email is already registered as brand")

            username = public_username.lower()
            hero_img_file = image_from_64(hero_img64, public_username, Brand.IMG_MAX_WIDTH)

            brand = Brand(username=username, public_username=public_username.replace(' ', ''),
                          owner=owner, title=brand_name)
            try:
                brand.full_clean(exclude=['hero_image'])
                brand.save()

                try:
                    PlanQueue.objects.add_plan_to_queue(plan_id=plan_id, brand=brand)

                    owner.is_brand_owner = True
                    brand.is_active = True
                    brand.hero_image.save(hero_img_file.name, hero_img_file)
                    owner.save()

                    return cls(brand)

                except BrandPlan.DoesNotExist:
                    brand.delete()
                    raise Exception("Plan do not exist")
                
                except Exception as e:
                    brand.delete()
                    raise Exception(e)

            except ValidationError as e:
                raise Exception(e)

        except User.DoesNotExist:
            raise Exception("No user with this email")


class BrandRegisterApplication(graphene.relay.ClientIDMutation):
    brand_application = graphene.Field(BrandApplicationNode)

    class Input:
        public_username = graphene.String()
        hero_img64 = graphene.String()
        brand_name = graphene.String()
        img_name = graphene.String()
        user_email = graphene.String()

    @classmethod
    @superuser_required
    def mutate_and_get_payload(cls, root, info, **input):
        public_username = input.get('public_username')
        hero_img64 = input.get('hero_img64')
        img_name = input.get('img_name')
        user_email = input.get('user_email')
        brand_name = input.get('brand_name')

        try:
            owner = User.objects.get(email=user_email)
            if owner.is_brand_owner:
                raise Exception("This email is already registered as brand")

            # Admin is itself adding brands or sending application so disable validate_username() for now
            # when the sending brand application becomes public re enable it.
            # username is just lower_case PublicUsername if other things are correct

            # username = validate_username(public_username)
            username = public_username.lower()
            hero_img_content = image_from_64(hero_img64)

            application_status = ApplicationStatus.objects.get(status_code='under_review')

            brand = Brand(username=username, public_username=public_username.replace(' ', ''),
                          owner=owner, title=brand_name)
            try:
                brand.full_clean(exclude=['hero_image'])
                brand.hero_image.save(img_name, hero_img_content, save=False)
                brand.save()

                # Create a brand application
                brand_application = BrandApplication(brand=brand, status=application_status)
                brand_application.save()

                return cls(brand_application)

            except ValidationError as e:
                raise Exception(e)

        except User.DoesNotExist:
            raise Exception("No user with this email")


class ReviewBrandApplication(graphene.relay.ClientIDMutation):
    brand = graphene.Field(BrandNode)

    class Input:
        application_id = graphene.ID(required=True)
        has_error = graphene.Boolean()
        errors = graphene.JSONString()

    @classmethod
    @superuser_required
    def mutate_and_get_payload(cls, root, info, **input):
        application_id = from_global_id(input.get('application_id'))[1]
        has_error = input.get('has_error')

        brand_application = BrandApplication.objects.get(id=application_id)

        if has_error:
            errors = input.get('errors')
        else:
            brand = brand_application.brand
            user = brand.owner
            try:
                plan_info = BrandPlan.objects.get(plan_id='99')

                def add_to_plan_queue(date_start, date_end, is_active=False):
                    plan = PlanQueue(brand=brand, plan=plan_info, is_active=is_active, date_start=date_start,
                                     date_end=date_end)
                    plan.save()

                add_to_plan_queue(is_active=True, date_start=now(),
                                  date_end=timezone.now() + plan_info.validity_duration)

                user.is_brand_owner = True
                user.save()
                brand.full_clean()
                brand.save()
                brand_application.delete()

                return cls(brand)

            except BrandPlan.DoesNotExist:
                raise Exception("Plan do not exist")


class AddBrandProduct(graphene.relay.ClientIDMutation):
    product = graphene.Field(ProductNode)

    class Input:
        product_title = graphene.String(required=True)
        category_id = graphene.ID(required=True)
        type_id = graphene.ID(required=True)
        mrp = graphene.Int()
        measurement_unit = graphene.String()
        thumb_overlay_text = graphene.String()
        description = graphene.String(required=True)
        long_description = graphene.String(required=True)
        technical_details = graphene.JSONString(required=True)
        base64images = graphene.List(graphene.JSONString)

    @classmethod
    @login_required
    @user_passes_test(lambda user: user.is_brand_owner)
    def mutate_and_get_payload(cls, root, info, **input):
        base64images = input.get('base64images')
        if len(base64images) == 0:
            raise Exception("No product images were provided")

        user = info.context.user
        brand = user.brand

        category_id = from_global_id(input.get('category_id'))[1]
        type_id = from_global_id(input.get('type_id'))[1]

        category = ProductCategory.objects.get(pk=category_id)
        category_username = category.username
    
        product_title = input.get('product_title')
        thumb_overlay_text = input.get('thumb_overlay_text')
        measurement_unit = input.get('measurement_unit')
        
        try:
            measurement_unit = MeasurementUnit.objects.get(name=measurement_unit) if measurement_unit else None
        except MeasurementUnit.DoesNotExist:
            measurement_unit = None
        
        mrp = None if category_username == 'raspaaifood' or category_username == 'raspaaiservices' else int(input.get('mrp'))
        description = input.get('description')
        long_description = input.get('long_description')
        technical_details = input.get('technical_details')

        product = Product(title=product_title, brand=brand, mrp=mrp, category=category, type_id=type_id,
                          description=description, thumb_overlay_text=thumb_overlay_text, measurement_unit=measurement_unit,
                          long_description=long_description, technical_details=technical_details)
        product.save()

        try:
            for imgNodeObj in base64images:
                img = imgNodeObj['node']

                img64 = img['base64']
                img_name = img['name']
                position = int(img['position'])
                img_file = image_from_64(img64, img_name, max_width=Product.IMG_MAX_WIDTH)

                product_image = ProductImage(product=product, position=position)
                product_image.image.save(img_file.name, img_file)

        except Exception as e:
            product.delete()
            raise Exception(e)

        return cls(product)


class ModifyBrandProduct(graphene.relay.ClientIDMutation):
    product = graphene.Field(ProductNode)

    class Input:
        product_id = graphene.ID(required=True)
        product_title = graphene.String()
        category_id = graphene.ID()
        type_id = graphene.ID()
        mrp = graphene.Int()
        thumb_overlay_text = graphene.String()
        measurement_unit = graphene.String()
        description = graphene.String()
        long_description = graphene.String()
        technical_details = graphene.JSONString()
        images = graphene.JSONString()
        action = graphene.String(required=True)

    @classmethod
    @login_required
    @user_passes_test(lambda user: user.is_brand_owner)
    def mutate_and_get_payload(cls, root, info, **input):
        product_id = from_global_id(input.get('product_id'))[1]
        product_title = input.get('product_title')
        category_id = input.get('category_id')
        type_id = input.get('type_id')
        mrp = input.get('mrp')
        thumb_overlay_text = input.get('thumb_overlay_text')
        description = input.get('description')
        long_description = input.get('long_description')
        technical_details = input.get('technical_details')
        measurement_unit = input.get('measurement_unit')
        images = input.get('images')
        action = input.get('action')
        user = info.context.user
        
        # Check if the product that is being modified belongs to the logged in brand owner
        try:
            product = user.brand.products.get(pk=product_id)
            if action == "edit":
                if product_title:
                    product.title = product_title
                if mrp:
                    product.mrp = mrp
                if description:
                    product.description = description
                if long_description:
                    product.long_description = long_description
                if thumb_overlay_text:
                    product.thumb_overlay_text = thumb_overlay_text
                if measurement_unit:
                    try:
                        measurement_unit = MeasurementUnit.objects.get(name=measurement_unit)
                    except MeasurementUnit.DoesNotExist:
                        measurement_unit = None
                    product.measurement_unit = measurement_unit
                    
                if category_id and type_id:
                    # If category is changed then type will be changed.
                    # And new technical_details will be for new category
                    category_id = from_global_id(category_id)[1]
                    type_id = from_global_id(type_id)[1]

                    product.category_id = category_id
                    product.type_id = type_id
                    product.technical_details = technical_details

                elif type_id:
                    type_id = from_global_id(type_id)[1]
                    product.type_id = type_id
                    product.technical_details = technical_details

                if (category_id or type_id) and technical_details:
                    # In this case new technical_details details are already set above
                    pass
                elif technical_details:
                    # this case will arise when no category or type is changed, but only,
                    # technical_details are changed
                    product_technical_details = product.technical_details

                    for key, value in technical_details.items():
                        product_technical_details[key] = value

                    product.technical_details = product_technical_details

                if images:
                    product_images = product.images
                    if len(images["deleted"]) != 0:
                        to_delete = images['deleted']
                        to_delete_ids = []
                        for img_node_obj in to_delete:
                            img_id = from_global_id(img_node_obj['node']['id'])[1]
                            to_delete_ids.append(img_id)

                        no_of_product_images = product_images.count()

                        print(len(to_delete_ids), no_of_product_images)
                        if len(to_delete_ids) >= no_of_product_images:
                            raise Exception("At least 1 image is required. You can not delete all images.")

                        images = product_images.filter(id__in=to_delete_ids)
                        images.delete()
                    
                    if len(images["changed"]) != 0:
                        change_position = images['changed']
                        # product_img_objs = []
                        for img_obj in change_position:
                            img_node = img_obj["node"]
                            img_id = from_global_id(img_node['id'])[1]
                            new_position = int(img_node['position'])

                            product_image = product_images.get(id=img_id)
                            product_image.position = new_position
                            product_image.save()
                        
                    if len(images["added"]) != 0:
                        new_images = images['added']
                        for imgNodeObj in new_images:
                            img = imgNodeObj['node']

                            img64 = img['image']
                            img_name = img['name']
                            position = img['position']
                            img_file = image_from_64(img64, img_name, Product.IMG_MAX_WIDTH)

                            product_image_obj = ProductImage.objects.create(product=product, position=position)
                            product_image_obj.image.save(img_file.name, img_file)
                
                product.save()

            elif action == 'delete':
                product.delete()

        except Product.DoesNotExist:
            raise Exception("Unauthorized access")

        return cls(product)


class AdminGetBrandInfo(graphene.relay.ClientIDMutation):
    brand = graphene.Field(BrandNode)

    class Input:
        brand_username = graphene.String()
        owner_email = graphene.String()

    @classmethod
    @superuser_required
    def mutate_and_get_payload(cls, root, info, **input):
        brand_username = input.get('brand_username')
        owner_email = input.get('owner_email')

        if brand_username:
            try:
                brand = Brand.objects.get(username=brand_username)
                return cls(brand)

            except Brand.DoesNotExist:
                raise Exception("Invalid brand username")

        if owner_email:
            try:
                owner = User.objects.get(email=owner_email)
                if owner.is_brand_owner:
                    brand = owner.brand
                    return cls(brand)
                else:
                    raise Exception("User is not registered as shop owner.")

            except User.DoesNotExist:
                raise Exception("No registered user with this email")

        raise Exception("No option provided")


class AdminAddBrandPlan(graphene.relay.ClientIDMutation):
    brand_plan = graphene.Field(BrandPlanQueueNode)

    class Input:
        plan_id = graphene.ID(required=True)
        brand_id = graphene.ID(required=True)

    @classmethod
    @superuser_required
    def mutate_and_get_payload(cls, root, info, **input):
        plan_id = from_global_id(input.get('plan_id'))[1]
        brand_id = from_global_id(input.get('brand_id'))[1]

        brand_plan = PlanQueue.objects.add_plan_to_queue(plan_id=plan_id, brand_id=brand_id)

        return cls(brand_plan)


class Mutation(graphene.ObjectType):
    add_brand_product = AddBrandProduct.Field()
    modify_brand_product = ModifyBrandProduct.Field()
    brand_register_application = BrandRegisterApplication.Field()
    review_brand_application = ReviewBrandApplication.Field()
    admin_add_brand = AdminAddBrand.Field()
    admin_get_brand_info = AdminGetBrandInfo.Field()
    admin_add_brand_plan = AdminAddBrandPlan.Field()


class BrandPlanFilter(FilterSet):
    class Meta:
        model = BrandPlan
        fields = ['price']

    order_by = OrderingFilter(
        fields=(
            ('price'),
        )
    )


class Query(graphene.ObjectType):
    product = graphene.relay.Node.Field(ProductNode)
    product_types = DjangoFilterConnectionField(ProductTypeNode)
    categories = DjangoFilterConnectionField(ProductCategoryNode)
    brands = DjangoFilterConnectionField(BrandNode)
    brand = graphene.Field(BrandNode, public_brand_username=graphene.String())
    available_plans_for_brand = DjangoFilterConnectionField(BrandPlanNode, filterset_class=BrandPlanFilter)
    # brand_application = graphene.relay.Node.Field(BrandApplicationNode)
    products = graphene.relay.ConnectionField(ProductNodeConnections, phrase=graphene.String(),
                                              product_type=graphene.String())

    # services = graphene.relay.ConnectionField(ProductNodeConnections, phrase=graphene.String())
    @login_required
    # @user_passes_test(lambda user: user.is_brand_owner)
    def resolve_available_plans_for_brand(self, info, **kwargs):
        return BrandPlanFilter(kwargs).qs

    @superuser_required
    def resolve_brand_application(self, info, **kwargs):
        return self

    def resolve_brand(self, info, **kwargs):
        public_brand_username = kwargs.get('public_brand_username')
        try:
            brand = Brand.objects.get(username=public_brand_username.lower())
            return brand

        except Brand.DoesNotExist:
            return None

    all_brand_applications = DjangoFilterConnectionField(BrandApplicationNode)

    @superuser_required
    def resolve_all_brand_applications(self, info, **kwargs):
        return self

    admin_brands = graphene.relay.ConnectionField(BrandNodeConnections, category=graphene.String(),
                                                  brand_username=graphene.String(),
                                                  search_by_username=graphene.Boolean(),
                                                  user_email=graphene.String())

    @superuser_required
    def resolve_admin_brands(self, info, **kwargs):
        category = kwargs.get('category')
        return BrandApplication.objects.filter(status__status_code=category)

    def resolve_services(self, info, **kwargs):
        phrase = kwargs.get('phrase')

        raspaai_services_brand = Brand.objects.get(username='raspaaiservices')
        services = raspaai_services_brand.products

        if (not (phrase and not phrase.isspace())):
            return services.all()
        else:
            return search_products_in_brand(phrase, services, sim_gt=0.3)

    def resolve_products(self, info, **kwargs):
        phrase = kwargs.get('phrase')
        product_type = kwargs.get('product_type')

        products = []
        if product_type == 'is_service':
            raspaai_services_brand = Brand.objects.get(username='raspaaiservices')
            products = raspaai_services_brand.products

        elif product_type == 'is_food':
            raspaai_food_brand = Brand.objects.get(username='raspaaifood')
            products = raspaai_food_brand.products

        else:
            brands = Brand.objects.filter(is_active=True).exclude(username__in=['raspaaifood', 'raspaaiservices'])
            products = Product.objects.filter(brand__in=brands)

        if (not (phrase and not phrase.isspace())):
            return products.all()
        else:
            return search_products_in_brand(phrase, products, sim_gt=0.3)

    brand_products = graphene.relay.ConnectionField(ProductNodeConnections, public_brand_username=graphene.String(),
                                                    phrase=graphene.String())

    def resolve_brand_products(self, info, **kwargs):
        phrase = kwargs.get('phrase')
        public_brand_username = kwargs.get('public_brand_username')
        brand_username = public_brand_username.lower()

        products = Product.objects.filter(brand__username=brand_username)

        if (not (phrase and not phrase.isspace())):
            return products
        else:
            return search_products_in_brand(phrase, products)

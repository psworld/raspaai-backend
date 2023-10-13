import datetime
import os
import random
from json import dumps

import graphene
import graphql_geojson
import jwt
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.timezone import now
from django_filters import FilterSet, OrderingFilter
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from graphql_jwt.decorators import user_passes_test, login_required, superuser_required
from graphql_relay import from_global_id
from django.contrib.postgres.search import TrigramSimilarity

from core.utils import validate_username, image_from_64
from search.postgresql_search import search_products_in_shop, shop_product_search, combos_search, search_combos_in_shop
from .models import Shop, ShopPlan, PopularPlace, ShopProduct, PlanQueue, ShopApplication, Combo, ComboProduct, ApplicationStatus

User = get_user_model()

SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
FRONT_END = os.environ.get('CORS_ORIGIN_WHITELIST')

SHOP_PRODUCT_VOLUME = 1
COMBO_VOLUME = 2


class PopularPlaceNode(graphql_geojson.GeoJSONType):
    class Meta:
        model = PopularPlace
        geojson_field = 'location'
        filter_fields = ['id']
        interfaces = (graphene.relay.Node,)


class ShopPlanQueueNode(DjangoObjectType):
    class Meta:
        model = PlanQueue
        filter_fields = ['is_active', 'shop', 'plan']
        interfaces = (graphene.relay.Node,)

    is_valid = graphene.Boolean()

    def resolve_is_valid(self, info):
        is_valid = self.is_valid()
        return is_valid


class ShopApplicationNode(DjangoObjectType):
    class Meta:
        model = ShopApplication
        filter_fields = ['id', 'status', 'shop']
        interfaces = (graphene.relay.Node,)
        
        
class ShopApplicationFilter(FilterSet):
    class Meta:
        model = ShopApplication
        fields = ['status__status_code', 'updated_at']

    order_by = OrderingFilter(
        fields=(
            ('status', 'updated_at'),
        )
    )


class PopularPlaceNodeConnections(graphene.relay.Connection):
    class Meta:
        node = PopularPlaceNode

    count = graphene.Int()

    def resolve_count(root, info):
        return len(root.edges)


class ShopNode(graphql_geojson.GeoJSONType):
    class Meta:
        model = Shop
        geojson_field = 'location'
        filter_fields = ['id', 'username', 'owner']
        interfaces = (graphene.relay.Node,)

    no_of_products = graphene.Int()
    no_of_combos = graphene.Int()
    have_active_plan = graphene.Boolean()
    active_plan = graphene.Field(ShopPlanQueueNode)
    occupied_space = graphene.Int()
    hero_image_thumb = graphene.String()

    def resolve_hero_image_thumb(self, info, **kwargs):
        thumb = self.get_thumb().name
        return thumb

    def resolve_occupied_space(self, info, **kwargs):
        occupied_space = self.occupied_space()
        return occupied_space

    def resolve_no_of_combos(self, info, **kwargs):
        no_of_combos = self.shop.combos.count()
        return no_of_combos

    def resolve_no_of_products(self, info, **kwargs):
        no_of_products = self.products.count()
        return no_of_products

    def resolve_have_active_plan(self, info, **kwargs):
        have_active_plan = self.have_active_plan()
        return have_active_plan

    def resolve_active_plan(self, info, **kwargs):
        active_plan = self.get_active_plan()
        return active_plan


class ShopPlanNode(DjangoObjectType):
    class Meta:
        model = ShopPlan
        filter_fields = ['plan_id']
        interfaces = (graphene.relay.Node,)

    validity_duration = graphene.String()

    def resolve_validity_duration(self, info, **kwargs):
        validity_duration = str(self.validity_duration)
        return validity_duration


class ShopPlanFilter(FilterSet):
    class Meta:
        model = ShopPlan
        fields = ['price']

    order_by = OrderingFilter(
        fields=(
            ('price'),
        )
    )


class ShopNodeConnections(graphene.relay.Connection):
    class Meta:
        node = ShopNode


class ShopProductNode(DjangoObjectType):
    class Meta:
        model = ShopProduct
        filter_fields = {
            'id': ['exact'],
            'shop_id': ['exact']
        }
        interfaces = (graphene.relay.Node,)


class ShopProductNodeConnections(graphene.relay.Connection):
    class Meta:
        node = ShopProductNode

    count = graphene.Int()
    shop = graphene.Field(ShopNode)

    def resolve_count(root, info):
        return len(root.edges)

    def resolve_shop(root, info):
        try:
            shop = root.edges[0].node.shop
            return shop

        except IndexError:
            return None


class ComboNode(DjangoObjectType):
    class Meta:
        model = Combo
        filter_fields = ['id', 'shop', 'is_available']
        interfaces = (graphene.relay.Node,)


class ComboNodeConnections(graphene.relay.Connection):
    class Meta:
        node = ComboNode

    count = graphene.Int()
    shop = graphene.Field(ShopNode)

    def resolve_count(root, info):
        return len(root.edges)

    def resolve_shop(root, info):
        try:
            shop = root.edges[0].node.shop
            return shop

        except IndexError:
            return None


class ComboProductNode(DjangoObjectType):
    class Meta:
        model = ComboProduct
        filter_fields = ['id']
        interfaces = (graphene.relay.Node,)


class AdminAddPopularPlace(graphene.relay.ClientIDMutation):
    popular_place = graphene.Field(PopularPlaceNode)

    class Input:
        lat_lng = graphene.String(required=True)
        name = graphene.String(required=True)
        img64 = graphene.String()

    @classmethod
    @superuser_required
    def mutate_and_get_payload(cls, root, info, **input):
        lat_lng = input.get('lat_lng')
        name = input.get('name')
        img64 = input.get('img64')
        
        lat_lng_list = lat_lng.split(', ')
        lat = float(lat_lng_list[0])
        lng = float(lat_lng_list[1])
        location = Point(lng, lat, srid=4326)
        
        popular_place = PopularPlace(name=name, location=location)
        
        if img64:
            img_file = image_from_64(img64, name, max_width=PopularPlace.IMG_MAX_WIDTH)
            popular_place.image.save(img_file.name, img_file, save=False)
        
        popular_place.save()

        return cls(popular_place)
        

class AdminEditPopularPlace(graphene.relay.ClientIDMutation):
    popular_place = graphene.Field(PopularPlaceNode)

    class Input:
        popular_place_id = graphene.ID(required=True)
        lat_lng = graphene.String()
        name = graphene.String()
        img64 = graphene.String()
        delete = graphene.Boolean(default=False)
        
    @classmethod
    @superuser_required
    def mutate_and_get_payload(cls, root, info, **input):
        popular_place_id = from_global_id(input.get('popular_place_id'))[1]
        lat_lng = input.get('lat_lng')
        name = input.get('name')
        img64 = input.get('img64')
        delete = input.get('delete')
        
        try:
            popular_place = PopularPlace.objects.get(pk=popular_place_id)
            
            if delete:
                popular_place.delete()
            
            else:
                img_name = name if name else popular_place.name
            
                if lat_lng:
                    lat_lng_list = lat_lng.split(', ')
                    lat = float(lat_lng_list[0])
                    lng = float(lat_lng_list[1])
                    location = Point(lng, lat, srid=4326)
                    popular_place.location = location
                
                if name:
                    popular_place.name = name
                
                if img64:
                    img_file = image_from_64(img64, img_name, max_width=PopularPlace.IMG_MAX_WIDTH)
                    if popular_place.image:
                        popular_place.delete_image()
                    popular_place.image.save(img_file.name, img_file, save=False)
                    
                popular_place.save()

            return cls(popular_place)
        
        except PopularPlace.DoesNotExist:
            raise Exception("Popular place with this id do not exist")


class ModifyShopReturnRefundPolicy(graphene.relay.ClientIDMutation):
    shop = graphene.Field(ShopNode)

    class Input:
        return_refund_policy = graphene.JSONString(required=True)

    @classmethod
    @login_required
    @user_passes_test(lambda user: user.is_shop_owner)
    def mutate_and_get_payload(cls, root, info, **input):
        return_refund_policy = input.get('return_refund_policy')
        for policy in return_refund_policy:
            if len(policy) > 200:
                raise Exception("Too large. Keep the privacy policy precise and small")
        user = info.context.user
        shop = user.shop

        if shop.is_active:
            shop.return_refund_policy = dumps(return_refund_policy)
            shop.save()

            return cls(shop)
        else:
            raise Exception("No active plan")


class AddShopProduct(graphene.relay.ClientIDMutation):
    shop_product = graphene.Field(ShopProductNode)

    class Input:
        product_id = graphene.ID(required=True)
        offered_price = graphene.Int(required=True)

    @classmethod
    @login_required
    @user_passes_test(lambda user: user.is_shop_owner)
    def mutate_and_get_payload(cls, root, info, **input):
        user = info.context.user

        offered_price = input.get('offered_price')
        product_id = from_global_id(input.get('product_id'))[1]

        shop = user.shop
        shop_products = shop.products
        remaining_space = shop.remaining_space()

        if remaining_space - SHOP_PRODUCT_VOLUME >= 0:
            try:
                shop_products.get(product_id=product_id)
                raise Exception("This product is already in your shop")

            except ShopProduct.DoesNotExist:
                shop_product = ShopProduct(shop=shop, product_id=product_id, offered_price=offered_price)
                shop_product.full_clean()
                shop_product.save()

                return cls(shop_product)

        else:
            raise Exception("Not enough product space. Please upgrade your plan")


class ModifyShopProduct(graphene.relay.ClientIDMutation):
    shop_product = graphene.Field(ShopProductNode)

    class Input:
        shop_product_id = graphene.ID(required=True)
        offered_price = graphene.Int()
        action = graphene.String(required=True)
        in_stock = graphene.Boolean()

    @classmethod
    @login_required
    @user_passes_test(lambda user: user.is_shop_owner)
    def mutate_and_get_payload(cls, root, info, **input):
        user = info.context.user
        shop_product_id = from_global_id(input.get('shop_product_id'))[1]

        offered_price = input.get('offered_price')
        action = input.get('action')

        shop = user.shop
        shop_products = shop.products

        if shop.is_active:
            try:
                shop_product = shop_products.get(pk=shop_product_id)

                if action == 'modify':
                    in_stock = input.get('in_stock')
                    
                    if in_stock is not None:
                            shop_product.in_stock = in_stock
                            
                    if offered_price:
                        combo_products = shop_product.combo_products
                        if combo_products.count() == 0:
                            shop_product.offered_price = offered_price
                        else:
                            raise Exception("Delete any combos associated with this product before making changes")

                    shop_product.save()

                elif action == 'delete':
                    # checking for combos
                    combo_products = shop_product.combo_products
                    if combo_products.count() == 0:
                        shop_product.delete()
                    else:
                        combo = combo_products.first().combo
                        combo.delete()
                        shop_product.delete()

            except ShopProduct.DoesNotExist:
                raise Exception("Unauthorized access")

            return cls(shop_product)

        else:
            raise Exception("No active shop plan")


class DeleteCombo(graphene.relay.ClientIDMutation):
    deleted_combo_id = graphene.ID()

    class Input:
        combo_id = graphene.ID(required=True)

    @classmethod
    @login_required
    @user_passes_test(lambda user: user.is_shop_owner)
    def mutate_and_get_payload(cls, root, info, **input):
        relay_combo_id = input.get('combo_id')
        combo_id = from_global_id(relay_combo_id)[1]
        user = info.context.user
        shop = user.shop
        shop_combos = shop.combos
        if shop.is_active:
            try:
                combo = shop_combos.get(id=combo_id)
                combo.delete()
                return cls(deleted_combo_id=relay_combo_id)

            except Combo.DoesNotExist:
                raise Exception('No combo exist with the given id in your shop.')
        else:
            raise Exception("No active shop plan")


class CreateCombo(graphene.relay.ClientIDMutation):
    combo = graphene.Field(ComboNode)

    class Input:
        combo_name = graphene.String(required=True)
        offered_price = graphene.Float(required=True)
        description = graphene.String(required=True)
        combo_products = graphene.JSONString(required=True)

    @classmethod
    @login_required
    @user_passes_test(lambda user: user.is_shop_owner)
    def mutate_and_get_payload(cls, root, info, **input):
        combo_name = input.get('combo_name')
        offered_price = input.get('offered_price')
        description = input.get('description')
        combo_products = input.get('combo_products')

        # Structure of combo_products should be:-
        # { relayShopProductId:{qty}, ddbuiyw87y7324:{qty:2}, adv872b0andia:{qty:1} }

        if len(combo_products) > 1:
            shop = info.context.user.shop

            remaining_space = shop.remaining_space()

            if remaining_space - SHOP_PRODUCT_VOLUME >= 0:
                if shop.is_active:
                    shop_products = shop.products

                    combo = Combo(shop=shop, offered_price=offered_price, name=combo_name,
                                  description=description)
                    combo.save()

                    combo_product_list = []
                    thumbs = []

                    # Total cost is the cost when all the items in a combo are bought at mrp
                    combo_total_cost = 0

                    for shop_product_relay_id, combo_product in combo_products.items():
                        shop_product_id = from_global_id(shop_product_relay_id)[1]
                        quantity = combo_product['quantity']
                        try:
                            shop_product = shop_products.get(id=shop_product_id)
                            
                            thumb_src = shop_product.product.get_thumb().name
                            thumb_overlay_text = shop_product.product.thumb_overlay_text
                            thumb = {
                            "src": thumb_src,
                            "overlayText": thumb_overlay_text,
                            "quantity": quantity
                            }
                            thumbs.append(thumb)
                            combo_product = ComboProduct(combo=combo, shop_product=shop_product, quantity=quantity)
                            combo_product_list.append(combo_product)

                            combo_total_cost += shop_product.product.mrp * quantity if shop_product.product.mrp else shop_product.offered_price * quantity

                        except ShopProduct.DoesNotExist:
                            combo.delete()
                            raise Exception(
                                'No shop product exist with that id. Make sure that the product is added to you shop first')
                        
                        except Exception as e:
                            combo.delete()
                            raise Exception(e)

                    ComboProduct.objects.bulk_create(combo_product_list)
                    combo.thumbs = dumps(thumbs)
                    combo.total_cost = combo_total_cost
                    combo.save()

                    return cls(combo)

                else:
                    raise Exception("No active plan")

            else:
                raise Exception("Not enough product space. Please upgrade your plan")

        else:
            raise Exception("Two or more products are required for making a combo.")


class EditCombo(graphene.relay.ClientIDMutation):
    combo = graphene.Field(ComboNode)
    
    class Input:
        combo_id = graphene.ID(required=True)
        combo_name = graphene.String()
        description = graphene.String()
        offered_price = graphene.Int()
        is_available = graphene.Boolean()
        
    @classmethod
    @login_required
    @user_passes_test(lambda user: user.is_shop_owner)
    def mutate_and_get_payload(cls, root, info, **input):
        combo_id = from_global_id(input.get('combo_id'))[1]
        combo_name = input.get('combo_name')
        description =  input.get('description')
        offered_price = input.get('offered_price')
        is_available = input.get('is_available')
    
        shop = info.context.user.shop
        shop_combos = shop.combos
        
        if shop.is_active:
            try:
                combo = shop_combos.get(pk=combo_id)
                
                if combo_name:
                    combo.name = combo_name
                if description:
                    combo.description = description
                if offered_price:
                    combo.offered_price = offered_price
                if is_available != None:
                    combo.is_available = is_available
                    
                combo.save()
                return cls(combo)
            
            except Combo.DoesNotExist:
                raise Exception("No combo with this id exist in your shop")
                
        else:
            raise Exception("Your shop plans have expired. Recharge to continue")


class ReviewShopApplication(graphene.relay.ClientIDMutation):
    shop_application = graphene.Field(ShopApplicationNode)

    class Input:
        application_id = graphene.ID(required=True)
        status_code = graphene.String(required=True)
        errors = graphene.JSONString()
        plan_id = graphene.ID()
        lat_lng_obj = graphene.JSONString()

    @classmethod
    @superuser_required
    def mutate_and_get_payload(cls, root, info, **input):
        application_id = from_global_id(input.get('application_id'))[1]
        status_code = input.get('status_code')
        shop_application = ShopApplication.objects.get(id=application_id)

        if status_code == "error" or status_code == "rejected":
            errors = input.get('errors')
            try:
                status = ApplicationStatus.objects.get(status_code=status_code)

                if errors == "{}":
                    raise Exception("No errors provided")
                shop_application.errors = errors
                shop_application.status = status
                shop_application.save()
                return cls(shop_application=shop_application)
            
            except ApplicationStatus.DoesNotExist:
                raise Exception("Application status does not exist")
            
        else:
            shop = shop_application.shop
            user = shop.owner
            
            lat_lng_obj = input.get('lat_lng_obj')
            plan_id = from_global_id(input.get('plan_id'))[1]
            lat = float(lat_lng_obj['lat'])
            lng = float(lat_lng_obj['lng'])
            location = Point(lng, lat, srid=4326)
            try:
                plan = ShopPlan.objects.get(id=plan_id)
                PlanQueue.objects.add_plan_to_queue(plan=plan, shop=shop)
                shop.location = location
                shop.save()
                user.is_shop_owner = True
                user.save()
                
                shop_application.delete()
                
                return cls(shop_application)

            except ShopPlan.DoesNotExist:
                raise Exception("Shop plans do not exist")

            except Exception as e:
                raise Exception(e)


class AdminAddShopVerifyEmail(graphene.relay.ClientIDMutation):
    jwt_encoded_str = graphene.String()

    class Input:
        email = graphene.String()

    @classmethod
    @superuser_required
    def mutate_and_get_payload(cls, root, info, **input):
        email = input.get('email')
        try:
            user = User.objects.get(email=email)
            if user.is_shop_owner:
                raise Exception('A shop owner is already registered with this email')

            key_code = random.randint(1000, 10000)

            payload = {
                'email': email,
                'key_code': key_code,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=20)
            }

            jwt_encoded_str = jwt.encode(payload, key=SECRET_KEY).decode('utf-8')

            mail_subject = 'Raspaai: Verify Your Email For Shop Registration'
            message = f'Hi {email}. Welcome to raspaai.'
            html_message = render_to_string('email_verification_template.html',
                                            {'key_code': key_code, 'email': email, 'front_end': FRONT_END})

            email_resp = send_mail(mail_subject, message, None,
                                   recipient_list=[email], html_message=html_message)
            if email_resp == 1:
                return cls(jwt_encoded_str=jwt_encoded_str)
            else:
                raise Exception('Email could not be sent please try again.')

        except User.DoesNotExist:
            raise Exception('No user with this email')


class AdminAddShop(graphene.relay.ClientIDMutation):
    shop = graphene.Field(ShopNode)

    class Input:
        owner_email = graphene.String(required=True)
        key_code = graphene.String()
        jwt_encoded_str = graphene.String()
        public_username = graphene.String(required=True)
        hero_image = graphene.JSONString(required=True)
        contact_number = graphene.String(required=True)
        address = graphene.String(required=True)
        shop_name = graphene.String(required=True)
        latLng = graphene.String(required=True)
        verify_email = graphene.Boolean(required=True)
        plan_id = graphene.ID(required=True)

    @classmethod
    @superuser_required
    def mutate_and_get_payload(cls, root, info, **input):
        jwt_encoded_str = input.get('jwt_encoded_str')
        owner_email = input.get('owner_email')
        public_username = input.get('public_username')
        contact_number = input.get('contact_number')
        address = input.get('address')
        hero_image = input.get('hero_image')
        shop_name = input.get('shop_name')
        latLng = input.get('latLng')
        key_code = input.get('key_code')
        verify_email = input.get('verify_email')
        plan_id = from_global_id(input.get('plan_id'))[1]

        latLngList = latLng.split(', ')

        lat = float(latLngList[0])
        lng = float(latLngList[1])

        def add_shop():
            try:
                user = User.objects.get(email=owner_email)
                if user.is_shop_owner:
                    raise Exception('A shop owner is already registered with this email')

                # username = validate_username(public_username)
                username = public_username.lower()
                
                base64 = hero_image['base64']
                hero_img_file = image_from_64(base64, public_username, max_width=Shop.IMG_MAX_WIDTH)
                location = Point(lng, lat, srid=4326)

                shop = Shop(username=username, address=address, contact_number=contact_number, is_active=True,
                            public_username=public_username.replace(' ', ''),
                            owner=user, title=shop_name, location=location)
                shop.full_clean(exclude=['hero_image'])
                shop.save()

                try:
                    PlanQueue.objects.add_plan_to_queue(plan_id=plan_id, shop=shop)
                    shop.hero_image.save(hero_img_file.name, hero_img_file, save=False)
                    shop.save()
                    shop.warm_image()
                    user.is_shop_owner = True
                    user.save()

                    return shop

                except ShopPlan.DoesNotExist:
                    shop.delete()
                    raise Exception("Shop plans do not exist")

                except Exception as e:
                    shop.delete()
                    raise Exception(e)

            except User.DoesNotExist:
                raise Exception("No user exist with that email")

        if verify_email == True:
            try:
                key_code = int(key_code)
                payload = jwt.decode(jwt_encoded_str, SECRET_KEY)

                if payload['key_code'] == key_code and payload['email'] == owner_email:
                    # Email verified
                    return cls(add_shop())

                else:
                    raise Exception('The provided key was wrong. Please check the key again in your email.')

            except jwt.ExpiredSignatureError:
                raise Exception("Key has expired. Please try again")

        elif verify_email == False:
            shop = cls(add_shop())
            return shop

        else:
            raise Exception("Verify email option not specified")


class ShopRegistrationApplication(graphene.relay.ClientIDMutation):
    shop_application = graphene.Field(ShopApplicationNode)

    class Input:
        shop_username = graphene.String(required=True)
        hero_img64 = graphene.String(required=True)
        contact_number = graphene.String(required=True)
        website = graphene.String()
        address = graphene.String(required=True)
        shop_name = graphene.String(required=True)

    @classmethod
    @login_required
    def mutate_and_get_payload(cls, root, info, **input):
        public_username = input.get('shop_username')
        contact_number = input.get('contact_number')
        address = input.get('address')
        website = input.get('website')
        hero_img64 = input.get('hero_img64')
        shop_name = input.get('shop_name')
        
        user = info.context.user

        if not user.is_shop_owner:
            username = validate_username(public_username)
            hero_img_file = image_from_64(hero_img64, public_username, max_width=Shop.IMG_MAX_WIDTH)

            shop = Shop(username=username, website=website, address=address, contact_number=contact_number,
                        public_username=public_username.replace(' ', ''), owner=user, title=shop_name)
            shop.full_clean(exclude=['hero_image', 'location'])
            shop.hero_image.save(hero_img_file.name, hero_img_file, save=False)
            try:
                shop.save()
                shop.warm_image()
            
            except Exception as e:
                shop.hero_image.delete(save=False)
                raise Exception(e)
                
            try:
                status = ApplicationStatus.objects.get(status_code="under_review")
                shop_application = ShopApplication.objects.create(shop=shop, status=status)
            
            except Exception as e:
                shop.delete()
                raise Exception(e)

            return cls(shop_application)

        else:
            raise Exception('You are already registered as a shop owner. If this is a mistake contact us.')
    
    
class DeleteShopApplication(graphene.relay.ClientIDMutation):
    resp = graphene.Boolean()
    
    class Input:
        application_id = graphene.ID(required=True)
        
    @classmethod
    @login_required
    def mutate_and_get_payload(cls, root, info, **input):
        application_id = from_global_id(input.get('application_id'))[1]
        user = info.context.user
        
        try:
            shop = user.shop
            shop.delete()
            return cls(True)
            # deleting shop will delete shop_application because fk
            
        except Shop.DoesNotExist:
            raise Exception("No shop applicaion was found with your account.")
    

class ModifyShopApplication(graphene.relay.ClientIDMutation):
    shop_application = graphene.Field(ShopApplicationNode)
    
    class Input:
        application_id = graphene.ID(required=True)
        shop_username = graphene.String()
        hero_image = graphene.String()
        contact_number = graphene.String()
        website = graphene.String()
        address = graphene.String()
        shop_name = graphene.String()
    
    @classmethod
    @login_required
    def mutate_and_get_payload(cls, root, info, **input):
        application_id = from_global_id(input.get('application_id'))[1]
        public_username = input.get('shop_username')
        contact_number = input.get('contact_number')
        address = input.get('address')
        website = input.get('website')
        hero_image = input.get('hero_image')
        shop_name = input.get('shop_name')
        
        user = info.context.user
        
        shop = user.shop
        shop_application = shop.application
        
        img_name = public_username if public_username else shop.public_username
        
        if not user.is_shop_owner:
            if public_username:
                username = validate_username(public_username)
                shop.username = username
                shop.public_username = public_username
            if contact_number:
                shop.contact_number = contact_number
            if address:
                shop.address = address
            if website:
                shop.website = website
            if shop_name:
                shop.title = shop_name
            if hero_image:
                shop.update_hero_image(hero_image)
            shop.save()
            status = ApplicationStatus.objects.get(status_code="under_review")
            shop_application.status = status
            shop_application.save()

            return cls(shop_application)

        else:
            raise Exception('You are already registered as a shop owner. If this is a mistake contact us.')
        

class ModifyShop(graphene.relay.ClientIDMutation):
    shop = graphene.Field(ShopNode)   
    
    class Input:
        about = graphene.String()
        website = graphene.String()
        is_open_today = graphene.Boolean()
        off_days = graphene.JSONString()
        open_close_time = graphene.JSONString()
        
    @classmethod
    @login_required
    @user_passes_test(lambda user: user.is_shop_owner)
    def mutate_and_get_payload(cls, root, info, **input):
        about = input.get('about')
        is_open_today = input.get('is_open_today')
        off_days = input.get('off_days')
        website = input.get('website')
        open_close_time = input.get('open_close_time')
        
        shop = info.context.user.shop
        
        if shop.is_active:
            if about:
                shop.about = about
            if website:
                shop.website = website
            
            if is_open_today != None:
                shop.is_open_today = is_open_today

            if off_days or off_days == []:
                shop.off_days = dumps(off_days)

            if open_close_time:
                open_at = open_close_time['openAt']
                close_at = open_close_time['closeAt']

                open_at = datetime.time(open_at['hour'], open_at['minutes'], 0)
                close_at = datetime.time(close_at['hour'], close_at['minutes'], 0)

                shop.open_at = open_at
                shop.close_at = close_at

            shop.save()
            return cls(shop)
        
        else:
            raise Exception("No active plan")


class ModifyShopActiveTime(graphene.relay.ClientIDMutation):
    shop = graphene.Field(ShopNode)

    class Input:
        is_open_today = graphene.Boolean()
        off_days = graphene.JSONString()
        open_close_time = graphene.JSONString()

    @classmethod
    @login_required
    @user_passes_test(lambda user: user.is_shop_owner)
    def mutate_and_get_payload(cls, root, info, **input):
        is_open_today = input.get('is_open_today')
        off_days = input.get('off_days')
        open_close_time = input.get('open_close_time')

        shop = info.context.user.shop

        if shop.is_active:
            if is_open_today != None:
                shop.is_open_today = is_open_today

            elif off_days or off_days == []:
                shop.off_days = dumps(off_days)

            elif open_close_time:
                open_at = open_close_time['openAt']
                close_at = open_close_time['closeAt']

                open_at = datetime.time(open_at['hour'], open_at['minutes'], 0)
                close_at = datetime.time(close_at['hour'], close_at['minutes'], 0)

                shop.open_at = open_at
                shop.close_at = close_at

            else:
                raise Exception("No option specified")

            shop.save()
            return cls(shop)

        else:
            raise Exception("No active plan")


class AdminGetShopInfo(graphene.relay.ClientIDMutation):
    shop = graphene.Field(ShopNode)

    class Input:
        shop_username = graphene.String()
        owner_email = graphene.String()

    @classmethod
    @superuser_required
    def mutate_and_get_payload(cls, root, info, **input):
        shop_username = input.get('shop_username')
        owner_email = input.get('owner_email')

        if shop_username:
            try:
                shop = Shop.objects.get(username=shop_username.lower())
                return cls(shop)

            except Shop.DoesNotExist:
                raise Exception("Invalid Shop Username")

        if owner_email:
            try:
                owner = User.objects.get(email=owner_email)
                if owner.is_shop_owner:
                    shop = owner.shop
                    return cls(shop)
                else:
                    raise Exception("User is not registered as shop owner.")

            except User.DoesNotExist:
                raise Exception("No registered user with this email")

        raise Exception("No option provided")


class AdminAddShopPlan(graphene.relay.ClientIDMutation):
    shop_plan = graphene.Field(ShopPlanQueueNode)

    class Input:
        plan_id = graphene.ID(required=True)
        shop_id = graphene.ID(required=True)

    @classmethod
    @superuser_required
    def mutate_and_get_payload(cls, root, info, **input):
        plan_id = from_global_id(input.get('plan_id'))[1]
        shop_id = from_global_id(input.get('shop_id'))[1]

        shop_plan = PlanQueue.objects.add_plan_to_queue(plan_id=plan_id, shop_id=shop_id)

        return cls(shop_plan)
        

class AdminEditShop(graphene.relay.ClientIDMutation):
    shop = graphene.Field(ShopNode)
    
    class Input:
        shop_id = graphene.ID(required=True)
        shop_name = graphene.String()
        hero_image = graphene.String()
        public_username = graphene.String()
        lat_lng = graphene.String()
        address = graphene.String()
        owner_email = graphene.String()
        contact_number = graphene.String()
        
    @classmethod
    @superuser_required
    def mutate_and_get_payload(cls, root, info, **input):
        shop_id = from_global_id(input.get('shop_id'))[1]
        shop_name = input.get('shop_name')
        hero_image = input.get('hero_image')
        public_username = input.get('public_username')
        lat_lng = input.get('lat_lng')
        address = input.get('address')
        owner_email = input.get('owner_email')
        contact_number = input.get('contact_number')
        
        try:
            shop = Shop.objects.get(pk=shop_id)
            
            if shop_name:
                shop.title = shop_name
            
            if public_username:
                username = public_username.lower()
                try:
                    Shop.objects.get(username=username)
                    raise Exception("Username already taken")
                
                except Shop.DoesNotExist:
                    shop.public_username = public_username
                    shop.username = username
            if contact_number:
                shop.contact_number = contact_number
            if address:
                shop.address = address
            if lat_lng:
                lat_lng_list = lat_lng.split(', ')
                lat = float(lat_lng_list[0])
                lng = float(lat_lng_list[1])
                location = Point(lng, lat, srid=4326)
                shop.location = location
            if owner_email:
                try:
                    user = User.objects.get(email=owner_email)
                    
                    if not user.is_shop_owner:
                        shop.owner = owner
                    else:
                        raise Exception("New email user is already a shop owner")
                
                except User.DoesNotExist:
                    raise Exception("No user with that email address")
            
            shop.save()
            
            if hero_image:
                shop.update_hero_image(hero_image)
            
            return cls(shop)
            
        except Shop.DoesNotExist:
            raise Exception("No shop exist with that id.")


class Mutation(graphene.ObjectType):
    shop_registration_application = ShopRegistrationApplication.Field()
    review_shop_application = ReviewShopApplication.Field()
    modify_shop_product = ModifyShopProduct.Field()
    admin_add_shop_verify_email = AdminAddShopVerifyEmail.Field()
    admin_add_shop = AdminAddShop.Field()
    admin_get_shop_info = AdminGetShopInfo.Field()
    admin_add_shop_plan = AdminAddShopPlan.Field()
    admin_add_popular_place = AdminAddPopularPlace.Field()
    admin_edit_popular_place = AdminEditPopularPlace.Field()
    admin_edit_shop = AdminEditShop.Field()
    modify_shop_return_refund_policy = ModifyShopReturnRefundPolicy.Field()
    add_shop_product = AddShopProduct.Field()
    create_combo = CreateCombo.Field()
    delete_combo = DeleteCombo.Field()
    edit_combo = EditCombo.Field()
    modify_shop = ModifyShop.Field()
    modify_shop_application = ModifyShopApplication.Field()
    delete_shop_application = DeleteShopApplication.Field()
    # modify_shop_active_time = ModifyShopActiveTime.Field()


class Query(graphene.ObjectType):
    nearby_shop_products = graphene.relay.ConnectionField(ShopProductNodeConnections, lat=graphene.Float(),
                                                          lng=graphene.Float())
    nearby_combos = graphene.relay.ConnectionField(ComboNodeConnections, lat=graphene.Float(),
                                                   lng=graphene.Float())
    combo_search = graphene.relay.ConnectionField(ComboNodeConnections, lat=graphene.Float(required=True),
                                                  lng=graphene.Float(required=True), phrase=graphene.String(required=True),
                                                  range_in_km=graphene.Int(), shop_name=graphene.String())
    shop_combos = graphene.relay.ConnectionField(ComboNodeConnections, public_shop_username=graphene.String(),
                                                 phrase=graphene.String())
    shops = DjangoFilterConnectionField(ShopNode)
    shop_product = graphene.relay.Node.Field(ShopProductNode)
    combo = graphene.relay.Node.Field(ComboNode)
    shop_products = graphene.relay.ConnectionField(ShopProductNodeConnections, public_shop_username=graphene.String(),
                                                   phrase=graphene.String())
    dashboard_shop_products = graphene.relay.ConnectionField(ShopProductNodeConnections,
                                                             public_shop_username=graphene.String(required=True),
                                                             phrase=graphene.String(), product_type=graphene.String())
    product_search = graphene.relay.ConnectionField(ShopProductNodeConnections, lat=graphene.Float(required=True),
                                                    lng=graphene.Float(required=True), phrase=graphene.String(required=True),
                                                    range_in_km=graphene.Int(), shop_name=graphene.String())

    available_plans = DjangoFilterConnectionField(ShopPlanNode, filterset_class=ShopPlanFilter)
    shop_application = graphene.relay.Node.Field(ShopApplicationNode)
    shop_applications = DjangoFilterConnectionField(ShopApplicationNode, filterset_class=ShopApplicationFilter)
    my_shop_application = graphene.relay.Node.Field(ShopApplicationNode)
    
    @login_required
    def resolve_my_shop_application(self, info, **kwargs):
        viewer = info.context.user
        try:
            shop_application = viewer.shop.application
            return shop_application
        
        except Shop.DoesNotExist:
            raise Exception("No applicaion found !")
        
        except ShopApplication.DoesNotExist:
            raise Exception("No applicaion found !")
    
    @superuser_required
    def resolve_shop_application(self, info, **kwargs):
        shop_applications = ShopApplicationFilter(kwargs).qs
        return shop_applications

    @login_required
    def resolve_available_plans(self, info, **kwargs):
        shop_plans = ShopPlanFilter(kwargs).qs
        return shop_plans

    def resolve_nearby_shop_products(self, info, **kwargs):
        lat = kwargs.get('lat')
        lng = kwargs.get('lng')
        ref_location = Point(lng, lat, srid=4326)
        nearby_shop_products = ShopProduct.objects.filter(shop__location__dwithin=(ref_location, D(km=5)),
                                                          shop__is_active=True)

        return nearby_shop_products

    def resolve_nearby_combos(self, info, **kwargs):
        lat = kwargs.get('lat')
        lng = kwargs.get('lng')
        ref_location = Point(lng, lat, srid=4326)

        nearby_combos = Combo.objects.filter(shop__location__dwithin=(ref_location, D(km=5)),
                                             shop__is_active=True)
        return nearby_combos

    def resolve_shop_combos(self, info, **kwargs):
        phrase = kwargs.get('phrase')
        public_shop_username = kwargs.get('public_shop_username')
        shop_username = public_shop_username.lower()

        shop_combos = Combo.objects.filter(shop__username=shop_username)

        if not (phrase and not phrase.isspace()):
            shop_combos = shop_combos.order_by('-created_at')
            return shop_combos
        else:
            combos_in_shop = search_combos_in_shop(phrase, shop_combos)
            return combos_in_shop

    def resolve_dashboard_shop_products(self, info, **kwargs):
        phrase = kwargs.get('phrase')
        public_shop_username = kwargs.get('public_shop_username')
        product_type = kwargs.get('product_type')
        shop_username = public_shop_username.lower()
        if product_type == 'is_service':
            shop_products = ShopProduct.objects.filter(shop__username=shop_username,
                                                       product__category__username="raspaaiservices")
        elif product_type == 'is_food':
            shop_products = ShopProduct.objects.filter(shop__username=shop_username,
                                                       product__category__username="raspaaifood")
        else:
            shop_products = ShopProduct.objects.filter(shop__username=shop_username).exclude(
                product__category__username__in=["raspaaiservices", "raspaaifood"])

        if not (phrase and not phrase.isspace()):
            shop_products = shop_products.order_by('-created_at')
            return shop_products
        else:
            products_in_shop = search_products_in_shop(phrase, shop_products)
            return products_in_shop

    def resolve_shop_products(self, info, **kwargs):
        phrase = kwargs.get('phrase')
        public_shop_username = kwargs.get('public_shop_username')
        shop_username = public_shop_username.lower()
        shop_products = ShopProduct.objects.filter(shop__username=shop_username)
        if not (phrase and not phrase.isspace()):
            shop_products = shop_products.order_by('-created_at')
            return shop_products
        else:
            products_in_shop = search_products_in_shop(phrase, shop_products)
            return products_in_shop

    def resolve_combo_search(self, info, **kwargs):
        lat = kwargs.get('lat')
        lng = kwargs.get('lng')
        phrase = kwargs.get('phrase')
        shop_name = kwargs.get('shop_name')
        shop_name = kwargs.get('shop_name')
        matching_shops = None
        if shop_name and len(shop_name) > 3:
            shop_name_sim = TrigramSimilarity("title", shop_name)
            matching_shops = Shop.objects.annotate(name_sim=shop_name_sim).filter(name_sim__gt=0.3)
        
        range_in_km = kwargs.get('range_in_km')
        coords = {
            'lat': lat,
            'lng': lng
        }

        return combos_search(phrase=phrase, coords=coords, shops=matching_shops)

    def resolve_product_search(self, info, **kwargs):
        lat = kwargs.get('lat')
        lng = kwargs.get('lng')
        phrase = kwargs.get('phrase')
        shop_name = kwargs.get('shop_name')
        matching_shops = None
        if shop_name and len(shop_name) > 3:
            shop_name_sim = TrigramSimilarity("title", shop_name)
            matching_shops = Shop.objects.annotate(name_sim=shop_name_sim).filter(name_sim__gt=0.3)
        
        range_in_km = kwargs.get('range_in_km')
        coords = {
            'lat': lat,
            'lng': lng
        }
        search_result = shop_product_search(phrase, coords, range_in_km, shops=matching_shops)
        return search_result

    shop = graphene.relay.node.Field(ShopNode, public_shop_username=graphene.String())
    # admin_shops = graphene.relay.ConnectionField(ShopNodeConnections, category=graphene.String(),
                                                 # shop_username=graphene.String(), search_by_username=graphene.Boolean(),
                                                 # user_email=graphene.String())
    user_shop = graphene.Field(ShopNode)

    popular_places = graphene.relay.ConnectionField(PopularPlaceNodeConnections, lat=graphene.Float(),
                                                    lng=graphene.Float())
    
    popular_place = graphene.relay.Node.Field(PopularPlaceNode)

    def resolve_popular_places(self, info, **kwargs):
        lat = kwargs.get('lat')
        lng = kwargs.get('lng')
        ref_location = Point(lng, lat, srid=4326)

        all_popular_places = PopularPlace.objects.all()
        return all_popular_places
        # return PopularPlace.objects.filter(location__dwithin=(ref_location, D(km=5)))

    def resolve_user_shop(self, info, **kwargs):
        user = info.context.user
        if user.is_authenticated:
            shop = Shop.objects.get(owner=user)
            return shop

    def resolve_shop(self, info, **kwargs):
        public_shop_username = kwargs.get('public_shop_username')
        shop = Shop.objects.filter(username=public_shop_username.lower()).first()
        return shop

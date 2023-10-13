import datetime
import os
import random

import graphene
import graphql_geojson
import graphql_jwt
import jwt
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail
from django.template.loader import render_to_string
from graphene_django.filter import DjangoFilterConnectionField
from graphene_django.types import DjangoObjectType
from graphql_jwt.decorators import login_required, superuser_required
from graphql_relay import from_global_id

from product.models import MeasurementUnit
from shop.models import ShopProduct, Combo
from .models import UserSavedLocation, CartItem, UserSavedAddress, CartLine

SECRET_KEY = os.environ.get('JWT_SECRET_KEY')

User = get_user_model()

FRONT_END = os.environ.get('CORS_ORIGIN_WHITELIST')


class UserNode(DjangoObjectType):
    class Meta:
        model = User
        filter_fields = ['email']
        interfaces = (graphene.relay.Node,)

    total_cart_items = graphene.Int()

    def resolve_total_cart_items(self, info, **kwargs):
        return self.cart_lines.count()


class UserSavedAddressNode(DjangoObjectType):
    class Meta:
        model = UserSavedAddress
        filter_fields = ['user']
        interfaces = (graphene.relay.Node,)


class UserSavedLocationNode(graphql_geojson.GeoJSONType):
    class Meta:
        model = UserSavedLocation
        geojson_field = 'location'
        filter_fields = ['is_active']
        interfaces = (graphene.relay.Node,)


class CartLineNode(DjangoObjectType):
    class Meta:
        model = CartLine
        filter_fields = ['id', 'cart']
        interfaces = (graphene.relay.Node,)


class CartItemNode(DjangoObjectType):
    class Meta:
        model = CartItem
        filter_fields = ['id', 'cart_line']
        interfaces = (graphene.relay.Node,)

    is_combo = graphene.Boolean()
    total_cost = graphene.Float()
    offered_price_total = graphene.Float()
    measurement_unit = graphene.String()
    
    def resolve_measurement_unit(self, info, **kwargs):
        unit = self.measurement_unit.name if self.measurement_unit else None
        return unit

    def resolve_is_combo(self, info, **kwargs):
        return self.is_combo()

    def resolve_total_cost(self, info, **kwargs):
        return self.get_total_cost()

    def resolve_offered_price_total(self, info, **kwargs):
        return self.get_offered_total()


# class UserSavedLocationNodeConnection(graphene.relay.Connection):
#     class Meta:
#         node = UserSavedLocationNode
#
#     count = graphene.Int()
#
#     def resolve_count(root, info):
#         return len(root.edges)


class LoginUser(graphql_jwt.relay.JSONWebTokenMutation):
    user = graphene.Field(UserNode)
    remember_me = graphene.Boolean()

    class Input:
        remember_me = graphene.Boolean(default=True)

    @classmethod
    def resolve(cls, root, info, **input):
        remember_me = input.get('remember_me')
        return cls(user=info.context.user, remember_me=remember_me)


class AddItemToCart(graphene.relay.ClientIDMutation):
    cart_line = graphene.Field(CartLineNode)

    class Input:
        shop_product_id = graphene.ID(required=True)
        quantity = graphene.Int(default=1)

    @classmethod
    @login_required
    def mutate_and_get_payload(cls, root, info, **input):
        shop_product_id = from_global_id(input.get('shop_product_id'))[1]
        quantity = input.get('quantity')

        user = info.context.user

        shop_product = ShopProduct.objects.get(id=shop_product_id)
        measurement_unit = shop_product.product.measurement_unit
        try:
            # cart line of a user for a shop
            cart_line = user.cart_lines.get(shop=shop_product.shop)
            # All items that belong to that cart line
            cart_items = CartItem.objects.filter(cart_line=cart_line)

            # if cart item already exist increase the quantity of it else add new cart item to existing cart line
            try:
                cart_item = cart_items.get(shop_product=shop_product)
                cart_item.quantity += 1

            except CartItem.DoesNotExist:
                cart_item = CartItem(cart_line=cart_line, shop_product=shop_product, quantity=quantity,
                                    measurement_unit=measurement_unit)

        except CartLine.DoesNotExist:
            cart_line = CartLine(cart=user, shop=shop_product.shop)
            cart_line.save()

            cart_item = CartItem(cart_line=cart_line, shop_product=shop_product, quantity=quantity, measurement_unit=measurement_unit)

        cart_item.save()
        return cls(cart_line)


class AddComboToCart(graphene.relay.ClientIDMutation):
    cart_line = graphene.Field(CartLineNode)

    class Input:
        combo_id = graphene.ID(required=True)
        quantity = graphene.Int(default=1)

    @classmethod
    @login_required
    def mutate_and_get_payload(cls, root, info, **input):
        combo_id = from_global_id(input.get('combo_id'))[1]
        quantity = input.get('quantity')

        user = info.context.user

        combo = Combo.objects.get(id=combo_id)

        try:
            # cart line of a user for a shop
            cart_line = user.cart_lines.get(shop=combo.shop)
            # All items that belong to that cart line
            cart_items = CartItem.objects.filter(cart_line=cart_line)

            # if cart item already exist increase the quantity of it else add new cart item to existing cart line
            try:
                cart_item = cart_items.get(combo=combo)
                cart_item.quantity += 1

            except CartItem.DoesNotExist:
                cart_item = CartItem(cart_line=cart_line, combo=combo, quantity=quantity)

        except CartLine.DoesNotExist:
            cart_line = CartLine(cart=user, shop=combo.shop)
            cart_line.save()

            cart_item = CartItem(cart_line=cart_line, combo=combo, quantity=quantity)

        cart_item.save()
        return cls(cart_line)


class ModifyCartItem(graphene.relay.ClientIDMutation):
    cart_item = graphene.Field(CartItemNode)

    class Input:
        cart_item_id = graphene.ID(required=True)
        quantity = graphene.Int()
        measurement_unit = graphene.String()
        shop_id = graphene.ID(required=True)
        delete = graphene.Boolean(default=False)

    @classmethod
    @login_required
    def mutate_and_get_payload(cls, root, info, **input):
        user = info.context.user
        delete = input.get('delete')
        quantity = input.get('quantity')
        measurement_unit = input.get('measurement_unit')
        cart_item_id = from_global_id(input.get('cart_item_id'))[1]
        shop_id = from_global_id(input.get('shop_id'))[1]

        try:
            cart_line = user.cart_lines.get(shop=shop_id)

            try:
                cart_item = cart_line.items.get(id=cart_item_id)

                if delete:
                    # We are handling cart_line delete through signals. see user.models.CartItem
                    cart_item.delete()

                else:
                    if quantity:
                        cart_item.quantity = quantity
                    if measurement_unit:
                        unit = MeasurementUnit.objects.get(name=measurement_unit)
                        cart_item.measurement_unit = unit
                    cart_item.save()

            except CartItem.DoesNotExist:
                raise Exception("Forbidden")

        except CartLine.DoesNotExist:
            raise Exception('Could find this item in your cart.')

        return cls(cart_item)


class ResetPassword(graphene.relay.ClientIDMutation):
    success = graphene.Boolean()

    class Input:
        jwt_encoded_str = graphene.String(required=True)
        key_code = graphene.Int(required=True)
        email = graphene.String(required=True)
        password1 = graphene.String(required=True)
        password2 = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **input):
        jwt_encoded_str = input.get('jwt_encoded_str')
        key_code = input.get('key_code')
        email = input.get('email')

        password1 = input.get('password1')
        password2 = input.get('password2')

        if password1 and password2 and password1 != password2:
            raise Exception("Passwords don't match")
        validate_password(password1)

        try:
            payload = jwt.decode(jwt_encoded_str, SECRET_KEY)

            if payload['key_code'] == key_code:
                # Email verified
                if payload['email'] == email:
                    try:
                        user = User.objects.get(email=email)
                        user.set_password(password1)
                        user.save()
                        return cls(success=True)

                    except User.DoesNotExist:
                        raise Exception('No registered user found with this email')

                else:
                    raise Exception(
                        'Some error occurred while verifying your email. Kindly reload the page and try again.')
            else:
                raise Exception("Invalid key. Check the key again in you email.")

        except jwt.ExpiredSignatureError:
            raise Exception("Key has expired. Kindly reload the page and resubmit password reset request.")


class ForgotPasswordEmailVerification(graphene.relay.ClientIDMutation):
    jwt_encoded_str = graphene.String()

    class Input:
        email = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **input):
        email = input.get('email')

        try:
            user = User.objects.get(email=email)
            key_code = random.randint(1000, 10000)
            payload = {
                'email': email,
                'key_code': key_code,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=10),
            }
            jwt_encoded_str = jwt.encode(payload, key=SECRET_KEY).decode('utf-8')

            mail_subject = "Raspaai | Password reset confirmation."
            message = f'Hi {email}. Here is your key for password reset.'
            html_message = render_to_string('password_reset_template.html',
                                            {'key_code': key_code, 'email': email,
                                             'front_end': FRONT_END})

            email_resp = send_mail(mail_subject, message, None,
                                   recipient_list=[email], html_message=html_message)

            if email_resp == 1:
                return cls(jwt_encoded_str=jwt_encoded_str)
            else:
                raise Exception('Email could not be sent. Please try again in a moment')

        except User.DoesNotExist:
            raise Exception("No registered user found with this email. Check your email again or sign up")


class SignupEmailVerification(graphene.relay.ClientIDMutation):
    email_resp = graphene.String()
    jwt_encoded_str = graphene.String()

    class Input:
        first_name = graphene.String(required=True)
        last_name = graphene.String(required=True)
        email = graphene.String(required=True)
        password1 = graphene.String(required=True)
        password2 = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **input):
        first_name = input.get('first_name')
        last_name = input.get('last_name')
        email = input.get('email')
        password1 = input.get('password1')
        password2 = input.get('password2')

        if password1 and password2 and password1 != password2:
            raise Exception("Passwords don't match")

        try:
            # Check if user already exist
            user = User.objects.get(email=email)
            raise Exception("A user with this email already exist")

        except User.DoesNotExist:
            key_code = random.randint(1000, 10000)

            payload = {
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'password': password1,
                'key_code': key_code,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=10),
            }

            jwt_encoded_str = jwt.encode(payload, key=SECRET_KEY).decode('utf-8')

            # Email sending
            mail_subject = 'Raspaai: Verify Your Email'
            message = f'Hi {email}. You are receiving this email because you applied for signup at Raspaai'
            html_message = render_to_string('email_verification_template.html',
                                            {'key_code': key_code, 'email': email,
                                             'front_end': FRONT_END})

            email_resp = send_mail(mail_subject, message, None,
                                   recipient_list=[email], html_message=html_message)

            if email_resp == 1:
                return cls(email_resp=f'email sent successfully to {email}.',
                           jwt_encoded_str=jwt_encoded_str)
            else:
                raise Exception('Email could not be sent please try again.')


class CreateUser(graphene.relay.ClientIDMutation):
    user = graphene.Field(UserNode)

    # verify the key_code and create the user
    class Input:
        jwt_encoded_str = graphene.String(required=True)
        key_code = graphene.Int(required=True)
        email = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **input):
        jwt_encoded_str = input.get('jwt_encoded_str')
        key_code = input.get('key_code')
        email = input.get('email')

        try:
            payload = jwt.decode(jwt_encoded_str, SECRET_KEY)

            if payload['key_code'] == key_code and payload['email'] == email:
                # Email verified
                user = User.objects.create_user(
                    email=email, password=payload['password'],
                    first_name=payload['first_name'],
                    last_name=payload['last_name'])
                return cls(user)

            else:
                raise Exception('Some error occurred while verifying your email please try again')

        except jwt.ExpiredSignatureError:
            raise Exception("Token has expired")
            

class AdminCreateUser(graphene.relay.ClientIDMutation):
    user = graphene.Field(UserNode)
    
    class Input:
        first_name = graphene.String(required=True)
        last_name = graphene.String(required=True)
        email = graphene.String(required=True)
        password1 = graphene.String(required=True)
        password2 = graphene.String(required=True)
        
    @classmethod
    @superuser_required
    def mutate_and_get_payload(cls, root, info, **input):
        first_name = input.get('first_name')
        last_name = input.get('last_name')
        email = input.get('email')
        password1 = input.get('password1')
        password2 = input.get('password2')
        
        if password1 and password2 and password1 != password2:
            raise Exception("Passwords don't match")

        try:
            # Check if user already exist
            user = User.objects.get(email=email)
            raise Exception("A user with this email already exist")

        except User.DoesNotExist:
            user = User.objects.create_user(email=email, password=password1,
                                            first_name=first_name, last_name=last_name)
            return cls(user)


class LogoutUser(graphene.relay.ClientIDMutation):
    user = graphene.Field(UserNode)

    class Input:
        pass

    @classmethod
    def mutate_and_get_payload(cls, root, info, **input):
        user = info.context.user
        logout(info.context)
        return cls(user)


class Mutation(graphene.ObjectType):
    login_user = LoginUser.Field()
    logout_user = LogoutUser.Field()
    create_user = CreateUser.Field()
    signup_email_verification = SignupEmailVerification.Field()
    add_item_to_cart = AddItemToCart.Field()
    add_combo_to_cart = AddComboToCart.Field()
    modify_cart_item = ModifyCartItem.Field()
    forgot_password_email_verification = ForgotPasswordEmailVerification.Field()
    reset_password = ResetPassword.Field()
    admin_create_user = AdminCreateUser.Field()


class Query(graphene.ObjectType):
    viewer = graphene.Field(UserNode)
    active_saved_location = graphene.List(UserSavedLocationNode)
    saved_addresses = DjangoFilterConnectionField(UserSavedAddressNode)
    cart_lines = graphene.List(CartLineNode)

    @login_required
    def resolve_cart_lines(self, info, **kwargs):
        user = info.context.user
        user_cart_lines = user.cart_lines
        user_cart_lines = user.cart_lines.filter(shop__is_active=True)
        user_cart_lines = user_cart_lines.order_by('-updated')
        return user_cart_lines

    # @login_required
    def resolve_active_saved_location(self, info, **kwargs):
        user = info.context.user
        if user.is_authenticated:
            active_saved_location = UserSavedLocation.objects.filter(is_active=True)
            if len(active_saved_location) > 0:
                return active_saved_location

    def resolve_viewer(self, info, **kwargs):
        user = info.context.user
        if user.is_authenticated:
            return user

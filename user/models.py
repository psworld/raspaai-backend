from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AbstractUser, PermissionsMixin
from django.contrib.gis.db.models import PointField
from django.core.mail import send_mail
from django.core.validators import validate_email, MinValueValidator
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone

from search.env import MANDI_LOCATION
from product.models import MeasurementUnit
from shop.models import ShopProduct, Combo, Shop
from user.manager import UserManager

from . import ureg, Q_

# django-cors-headers django-filter django-versatileimagefield graphene-django pip-chill
class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(
        unique=True,
        validators=[validate_email],
        error_messages={
            'unique': "A user with that email already exists.",
        },
    )
    first_name = models.CharField('first name', max_length=30, blank=True, null=True)
    last_name = models.CharField('last name', max_length=150, blank=True, null=True)
    is_shop_owner = models.BooleanField(default=False)
    is_brand_owner = models.BooleanField(default=False)
    is_staff = models.BooleanField(
        'staff status',
        default=False,
        help_text='Designates whether the user can log into this admin site.',
    )
    is_active = models.BooleanField(
        'active',
        default=True,
        help_text=(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'
        ),
    )
    date_joined = models.DateTimeField('date joined', default=timezone.now)

    USERNAME_FIELD = 'email'

    objects = UserManager()

    def get_full_name(self):
        """
        Return the first_name plus the last_name, with a space in between.
        """
        full_name = '%s %s' % (self.first_name, self.last_name)
        return full_name.strip()

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name

    def email_user(self, subject, message, from_email=None, **kwargs):
        """Send an email to this user."""
        send_mail(subject, message, from_email, [self.email], **kwargs)

    def total_cart_items(self):
        return self.cart_lines.count()

    def __str__(self):
        return self.email


class CartLine(models.Model):
    cart = models.ForeignKey(User, related_name='cart_lines', on_delete=models.CASCADE)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.shop.title + " - " + self.cart.email


class CartItem(models.Model):
    cart_line = models.ForeignKey(CartLine, related_name="items", on_delete=models.CASCADE)
    shop_product = models.ForeignKey(ShopProduct, on_delete=models.CASCADE, null=True, blank=True)
    combo = models.ForeignKey(Combo, on_delete=models.CASCADE, null=True, blank=True)
    measurement_unit = models.ForeignKey(MeasurementUnit, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.IntegerField(validators=[MinValueValidator(0)], default=1)

    def __str__(self):
        if self.shop_product:
            return self.shop_product.product.title
        else:
            return self.combo.name

    def get_offered_total(self):
        shop_product = self.shop_product
        if shop_product:
            base_unit = shop_product.product.measurement_unit.name if self.shop_product.product.measurement_unit else None
            base_unit_price = shop_product.offered_price
            
            new_unit = self.measurement_unit.name if self.measurement_unit else None
            new_unit_in_base_unit = Q_(new_unit).to(base_unit) if new_unit else None
            
            total = 0
            
            if new_unit == base_unit:
                total = base_unit_price * self.quantity
            
            elif new_unit_in_base_unit:
                total = float(base_unit_price) * new_unit_in_base_unit.magnitude * self.quantity
                
            return round(total)
        else:
            total = self.combo.offered_price * self.quantity
            return total

    def get_total_cost(self):
        if self.shop_product:
            product = self.shop_product.product
            base_unit = product.measurement_unit.name if product.measurement_unit else None
            base_unit_mrp = product.mrp if product.mrp else None
            
            new_unit = self.measurement_unit.name if self.measurement_unit else None
            
            if not base_unit_mrp:
                return None
            if new_unit == base_unit:
                total = base_unit_mrp * self.quantity
            elif new_unit and base_unit:
                new_unit_in_base_unit = Q_(new_unit).to(base_unit)
                total = float(base_unit_mrp) * new_unit_in_base_unit.magnitude * self.quantity
                
            return round(total)
        else:
            total = self.combo.total_cost * self.quantity
            return total

    def is_combo(self):
        shop_product = self.shop_product
        if shop_product:
            return False
        return True


@receiver(post_delete, sender=CartItem)
def handle_CartItem_delete(sender, instance, **kwargs):
    # Remove cart line if no items are left in that cart_line
    try:
        cart_line = instance.cart_line
        if cart_line.items.count() == 0:
            cart_line.delete()
    
    except CartLine.DoesNotExist:
        pass


class UserSavedAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=10)
    address_line1 = models.CharField(max_length=256, null=True, blank=True)
    address_line2 = models.CharField(max_length=256, null=True, blank=True)

    def __str__(self):
        return self.user.email + " address"


class UserSavedLocation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    location = PointField(geography=True, srid=4326, null=True, default=MANDI_LOCATION)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return self.name

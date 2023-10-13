from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.timezone import now

from shop.models import Shop, ShopProduct, Combo
from . import OrderStatus

User = get_user_model()


class Order(models.Model):
    created = models.DateTimeField(default=now, editable=False)
    reference_id = models.CharField(max_length=18, default="", db_index=True)
    user = models.ForeignKey(
        User,
        blank=True,
        null=True,
        related_name="orders",
        on_delete=models.SET_NULL,
    )
    status = models.CharField(
        max_length=32, default=OrderStatus.UNFULFILLED, choices=OrderStatus.CHOICES
    )
    user_email = models.EmailField(blank=True, default="")
    user_phone = models.CharField(max_length=10)
    user_full_name = models.CharField(max_length=100)
    total = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    total_items = models.IntegerField(default=0)

    def __str__(self):
        return str(self.pk)


class ShopOrderLine(models.Model):
    order = models.ForeignKey(Order, related_name="shop_orders", on_delete=models.CASCADE)
    status = models.CharField(
        max_length=32, default=OrderStatus.UNFULFILLED, choices=OrderStatus.CHOICES
    )
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, null=True, blank=True)
    client_tracking_id = models.CharField(max_length=12)  # hh1-self.id last
    total = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    total_items = models.IntegerField(default=0)

    def __str__(self):
        return self.client_tracking_id


class OrderItem(models.Model):
    shop_order = models.ForeignKey(ShopOrderLine, related_name='order_items',
                                   on_delete=models.CASCADE)
    product_title = models.CharField(max_length=255, null=True, blank=True)
    shop_product = models.ForeignKey(ShopProduct, on_delete=models.SET_NULL, null=True, blank=True)
    combo = models.ForeignKey(Combo, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=9, decimal_places=2)

    def get_total(self):
        return self.unit_price * self.quantity

    def is_combo(self):
        if self.shop_product:
            return False
        return True

    def __str__(self):
        return self.product_title

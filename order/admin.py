from django.contrib import admin

from .models import Order, ShopOrderLine, OrderItem

admin.site.register(Order)
admin.site.register(ShopOrderLine)
admin.site.register(OrderItem)

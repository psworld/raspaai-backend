from django.contrib import admin

from shop.models import Shop, ShopPlan, PopularPlace, ShopProduct, PlanQueue, ShopApplication, Combo, ComboProduct


@admin.register(PlanQueue)
class PlanQueueAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'shop', 'plan', 'is_active', 'added_at', 'date_start', 'date_end')
    date_hierarchy = 'date_start'
    ordering = ['date_start']
    search_fields = ['shop__username']


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('title', 'public_username', 'contact_number', 'is_active', 'is_open_today')
    search_fields = ['username', 'owner__email']


@admin.register(ShopPlan)
class ShopPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan_id', 'price', 'product_space', 'validity_duration')
    ordering = ['product_space', 'validity_duration']


admin.site.register(ShopApplication)
admin.site.register(PopularPlace)
admin.site.register(ShopProduct)
admin.site.register(Combo)
admin.site.register(ComboProduct)

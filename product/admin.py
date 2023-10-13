from django.contrib import admin

from product.models import Product, ProductCategory, ProductType, ProductImage, Brand, BrandPlan, ApplicationStatus, \
    PlanQueue, BrandApplication, MeasurementUnit


@admin.register(MeasurementUnit)
class MeasurementUnitAdmin(admin.ModelAdmin):
    list_display = ['name']

@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['image', 'position', 'product']


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'username']


@admin.register(ProductType)
class ProductTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'username', 'category']
    ordering = ['category']


@admin.register(BrandPlan)
class BrandPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'plan_id', 'price', 'product_space', 'validity_duration']
    ordering = ['product_space', 'validity_duration']


@admin.register(PlanQueue)
class PlanQueueAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'brand', 'plan', 'is_active', 'is_expired', 'added_at', 'date_start', 'date_end')

    def is_expired(self, obj):
        return obj.is_expired()

    is_expired.boolean = True

    date_hierarchy = 'date_start'
    ordering = ['date_start']
    search_fields = ['brand__username']


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['title', 'public_username', 'is_active']
    search_fields = ['username', 'owner__email']


admin.site.register(BrandApplication)
admin.site.register(Product)
admin.site.register(ApplicationStatus)

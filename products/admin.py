from django.contrib import admin
from .models import (
    Tax, Category, Product, ProductAttribute, ProductAttributeValue,
    ProductVariant, ProductVariantAttribute, Inventory, PriceHistory, ProductImage
)

@admin.register(Tax)
class TaxAdmin(admin.ModelAdmin):
    list_display = ['name', 'rate', 'tax_type', 'is_active', 'created_at']
    list_filter = ['tax_type', 'is_active']
    search_fields = ['name']

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'business', 'parent', 'is_active', 'created_at']
    list_filter = ['business', 'is_active']
    search_fields = ['name', 'description']
    raw_id_fields = ['business', 'parent']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'business', 'category', 'base_selling_price', 
        'base_barcode', 'base_sku', 'has_variants', 'is_active'
    ]
    list_filter = ['business', 'category', 'has_variants', 'product_type', 'is_active']
    search_fields = ['name', 'description', 'base_sku', 'base_barcode']
    raw_id_fields = ['business', 'category', 'tax', 'created_by']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('business', 'name', 'description', 'category', 'product_type')
        }),
        ('Variants', {
            'fields': ('has_variants', 'variant_type')
        }),
        ('Identification', {
            'fields': ('base_barcode', 'base_sku')
        }),
        ('Pricing', {
            'fields': ('base_cost_price', 'base_selling_price', 'base_wholesale_price')
        }),
        ('Tax', {
            'fields': ('tax', 'tax_inclusive')
        }),
        ('Product Details', {
            'fields': ('unit_of_measure', 'reorder_level', 'is_trackable')
        }),
        ('Media', {
            'fields': ('image',)
        }),
        ('Status', {
            'fields': ('is_active', 'created_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(ProductAttribute)
class ProductAttributeAdmin(admin.ModelAdmin):
    list_display = ['product', 'name', 'display_order', 'is_required']
    list_filter = ['product']
    search_fields = ['name', 'product__name']

@admin.register(ProductAttributeValue)
class ProductAttributeValueAdmin(admin.ModelAdmin):
    list_display = ['attribute', 'value', 'display_order']
    list_filter = ['attribute__product']
    search_fields = ['value', 'attribute__name']

@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'name', 'sku', 'barcode', 'selling_price', 
        'cost_price', 'is_default', 'is_active'
    ]
    list_filter = ['product', 'is_active', 'is_default']
    search_fields = ['name', 'sku', 'barcode', 'product__name']
    raw_id_fields = ['product']

@admin.register(ProductVariantAttribute)
class ProductVariantAttributeAdmin(admin.ModelAdmin):
    list_display = ['variant', 'attribute', 'value']
    list_filter = ['attribute__product']
    raw_id_fields = ['variant', 'attribute', 'value']

@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ['shop', 'get_product', 'current_stock', 'available_stock', 'is_active']
    list_filter = ['shop', 'is_active']
    search_fields = ['product__name', 'variant__name', 'shop__name']
    readonly_fields = ['available_stock']
    raw_id_fields = ['product', 'variant', 'shop']
    
    def get_product(self, obj):
        return obj.get_product()
    get_product.short_description = 'Product'

@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ['get_product', 'old_price', 'new_price', 'price_type', 'changed_at']
    list_filter = ['price_type', 'changed_at']
    search_fields = ['product__name', 'variant__name']
    readonly_fields = ['changed_at']
    raw_id_fields = ['product', 'variant', 'changed_by']
    
    def get_product(self, obj):
        if obj.product:
            return obj.product.name
        elif obj.variant:
            return obj.variant.display_name
        return "N/A"
    get_product.short_description = 'Product'

@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['get_product', 'image', 'caption', 'is_primary', 'display_order']
    list_filter = ['is_primary']
    search_fields = ['product__name', 'variant__name', 'caption']
    raw_id_fields = ['product', 'variant']
    
    def get_product(self, obj):
        if obj.product:
            return obj.product.name
        elif obj.variant:
            return obj.variant.display_name
        return "N/A"
    get_product.short_description = 'Product'
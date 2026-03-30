from django.contrib import admin
from .models import Customer, Sale, SaleItem, Payment, ReceiptTemplate


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'phone_number', 'loyalty_points', 'total_spent', 'is_active')
    list_filter = ('business', 'is_active')
    search_fields = ('name', 'phone_number', 'email')


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'shop', 'total_amount', 'status', 'sync_status', 'sale_date')
    list_filter = ('status', 'sync_status', 'is_offline', 'shop')
    search_fields = ('receipt_number', 'offline_id')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ('sale', 'product', 'quantity', 'unit_price', 'total_price')
    search_fields = ('sale__receipt_number', 'product__name')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('sale', 'method', 'amount', 'status', 'created_at')
    list_filter = ('method', 'status')
    search_fields = ('sale__receipt_number', 'transaction_code')


@admin.register(ReceiptTemplate)
class ReceiptTemplateAdmin(admin.ModelAdmin):
    list_display = ('shop', 'layout', 'printer_width', 'show_logo', 'updated_at')
    list_filter = ('layout', 'printer_width')
    search_fields = ('shop__name', 'header_text')

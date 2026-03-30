# sales/models.py - Updated with ReceiptTemplate model
from django.db import models
import uuid

from django.contrib.auth.models import User
from products.models import Product
from shops.models import Business, Employee, Shop


class Customer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='customers')
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15, unique=True, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    # Loyalty program
    loyalty_points = models.IntegerField(default=0)
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Customer preferences
    preferences = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.phone_number})"


class Sale(models.Model):
    SALE_STATUS = (
        ('draft', 'Draft'),
        ('pending', 'Pending Payment'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    )
    SYNC_STATUS = (
        ('pending', 'Pending Sync'),
        ('synced', 'Synced to Server'),
        ('conflict', 'Sync Conflict'),
        ('failed', 'Sync Failed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt_number = models.CharField(max_length=50, unique=True)
    offline_id = models.CharField(max_length=100, blank=True, null=True)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='sales')
    attendant = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='sales')
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    change_given = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=SALE_STATUS, default='draft')
    sync_status = models.CharField(max_length=20, choices=SYNC_STATUS, default='pending')
    is_offline = models.BooleanField(default=False)

    sale_date = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['sale_date', 'shop']),
            models.Index(fields=['sync_status', 'is_offline']),
        ]

    def __str__(self):
        return f"Sale {self.receipt_number} - {self.shop.name}"


class SaleItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=3, default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock_deducted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} - {self.sale.receipt_number}"


class Payment(models.Model):
    PAYMENT_METHODS = (
        ('cash', 'Cash'),
        ('mpesa', 'M-Pesa'),
        ('card', 'Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('credit', 'Customer Credit'),
    )
    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='payments')
    method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_code = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    card_last_four = models.CharField(max_length=4, blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.method} - {self.amount} for {self.sale.receipt_number}"


# ──────────────────────────────────────────────────────────
# Receipt Template – owner-designed receipt layouts per shop
# ──────────────────────────────────────────────────────────
def receipt_logo_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    return os.path.join('receipt_logos', f"{instance.shop.id}_{uuid.uuid4().hex[:8]}.{ext}")


import os  # noqa: E402 – needed for receipt_logo_upload_path


class ReceiptTemplate(models.Model):
    """
    Owner-designed receipt template stored online.
    POS uses this template when printing via Bluetooth.
    """
    LAYOUT_CHOICES = (
        ('standard', 'Standard'),
        ('compact', 'Compact'),
        ('detailed', 'Detailed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.OneToOneField(Shop, on_delete=models.CASCADE, related_name='receipt_template')

    # Header / branding
    header_text = models.CharField(max_length=255, blank=True, default='')
    footer_text = models.CharField(max_length=255, blank=True, default='Thank you for your purchase!')
    logo = models.ImageField(upload_to='receipt_logos/', null=True, blank=True)

    # Layout
    layout = models.CharField(max_length=20, choices=LAYOUT_CHOICES, default='standard')
    show_logo = models.BooleanField(default=True)
    show_shop_address = models.BooleanField(default=True)
    show_shop_phone = models.BooleanField(default=True)
    show_attendant_name = models.BooleanField(default=True)
    show_customer_name = models.BooleanField(default=True)
    show_tax_breakdown = models.BooleanField(default=True)
    show_payment_method = models.BooleanField(default=True)

    # Printer config
    printer_width = models.IntegerField(default=58, help_text='Printer paper width in mm (32, 58, 80)')

    # Custom fields (JSON bucket for additional custom lines)
    custom_fields = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Receipt template for {self.shop.name}"

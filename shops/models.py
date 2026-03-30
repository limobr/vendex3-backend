# shops/models.py - Updated with verification_code on Employee
from django.db import models
import uuid

from accounts.models import Permission, Role
from django.contrib.auth.models import User


class Business(models.Model):
    """Parent business that can have multiple shops"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='businesses')
    name = models.CharField(max_length=255)
    registration_number = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Shop(models.Model):
    SHOP_TYPES = (
        ('retail', 'Retail Store'),
        ('wholesale', 'Wholesale'),
        ('supermarket', 'Supermarket'),
        ('restaurant', 'Restaurant/Cafe'),
        ('kiosk', 'Kiosk'),
        ('pharmacy', 'Pharmacy'),
        ('other', 'Other'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='shops')
    name = models.CharField(max_length=255)
    shop_type = models.CharField(max_length=20, choices=SHOP_TYPES, default='retail')
    location = models.CharField(max_length=500)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    currency = models.CharField(max_length=3, default='KES')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['business', 'name']

    def __str__(self):
        return f"{self.name} - {self.business.name}"


class Employee(models.Model):
    """Link users to shops with specific roles and permissions"""
    EMPLOYMENT_TYPES = (
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('casual', 'Casual'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='employments')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='employees')
    role = models.ForeignKey(Role, on_delete=models.PROTECT)
    custom_permissions = models.ManyToManyField(Permission, blank=True)
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPES, default='full_time')
    salary = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    temporary_password = models.CharField(max_length=255, blank=True, null=True)
    password_expiry = models.DateTimeField(null=True, blank=True)

    # ── Verification code for invite (valid 30 minutes) ──
    verification_code = models.CharField(max_length=6, blank=True, null=True)
    verification_code_expiry = models.DateTimeField(null=True, blank=True)
    is_invite_accepted = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    employment_date = models.DateField(auto_now_add=True)
    termination_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'shop']

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.shop.name} ({self.role.name})"

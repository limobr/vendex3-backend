# accounts/models.py - Extended with Configuration, Notification, Message models
import os
from django.db import models
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save
import uuid


def profile_picture_upload_path(instance, filename):
    """Generate upload path for profile pictures"""
    ext = filename.split('.')[-1]
    filename = f"{instance.user.id}_{uuid.uuid4().hex[:8]}.{ext}"
    return os.path.join('profile_pics', filename)


class Permission(models.Model):
    """Global permission definitions"""
    PERMISSION_CATEGORIES = (
        ('products', 'Products'),
        ('sales', 'Sales'),
        ('customers', 'Customers'),
        ('employees', 'Employees'),
        ('inventory', 'Inventory'),
        ('reports', 'Reports'),
        ('settings', 'Settings'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50, choices=PERMISSION_CATEGORIES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Role(models.Model):
    """Predefined roles with sets of permissions"""
    ROLE_TYPES = (
        ('owner', 'Shop Owner'),
        ('manager', 'Shop Manager'),
        ('cashier', 'Cashier'),
        ('stock_keeper', 'Stock Keeper'),
        ('attendant', 'Sales Attendant'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    role_type = models.CharField(max_length=20, choices=ROLE_TYPES, unique=True)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(Permission, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    USER_TYPE_CHOICES = (
        ('owner', 'Shop Owner'),
        ('employee', 'Employee'),
        ('admin', 'System Admin'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='employee')
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    profile_picture = models.ImageField(
        upload_to=profile_picture_upload_path,
        null=True,
        blank=True,
        max_length=500
    )
    date_of_birth = models.DateField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    pin_hash = models.CharField(max_length=255, blank=True, null=True)
    fcm_token = models.TextField(blank=True, null=True)
    preferences = models.JSONField(default=dict, blank=True, null=True)

    # ── First-login / onboarding tracking ──
    is_first_login_complete = models.BooleanField(default=False)
    has_changed_temp_password = models.BooleanField(default=False)
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email or self.user.username} ({self.user_type})"

    def get_profile_picture_url(self):
        if self.profile_picture:
            return self.profile_picture.url
        return None


# ──────────────────────────────────────────────────────────
# Configuration model – owner theme / app settings per business
# ──────────────────────────────────────────────────────────
class Configuration(models.Model):
    """
    Owner-chosen settings: colour palette, dark/light mode, operation mode, etc.
    Employees automatically inherit these on login.
    """
    THEME_CHOICES = (
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('system', 'System Default'),
    )
    OPERATION_MODE_CHOICES = (
        ('system', 'System Automatic'),
        ('manual', 'Manual'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.OneToOneField(
        'shops.Business', on_delete=models.CASCADE, related_name='configuration'
    )
    # Theme colours
    primary_color = models.CharField(max_length=7, default='#667eea')
    secondary_color = models.CharField(max_length=7, default='#764ba2')
    accent_color = models.CharField(max_length=7, default='#4299e1')
    theme_mode = models.CharField(max_length=10, choices=THEME_CHOICES, default='light')
    # Operation
    operation_mode = models.CharField(max_length=10, choices=OPERATION_MODE_CHOICES, default='system')
    # Receipt defaults
    default_printer_width = models.IntegerField(default=58, help_text='Printer width in mm')
    # Locale
    currency_symbol = models.CharField(max_length=5, default='KES')
    date_format = models.CharField(max_length=20, default='DD/MM/YYYY')
    time_format = models.CharField(max_length=10, default='24h')
    # Extra bucket
    extra_settings = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Config for {self.business.name}"


# ──────────────────────────────────────────────────────────
# Notification model
# ──────────────────────────────────────────────────────────
class Notification(models.Model):
    """System-generated notifications for relevant events."""
    NOTIFICATION_TYPES = (
        ('info', 'Information'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('system', 'System'),
    )
    NOTIFICATION_CATEGORIES = (
        ('sale', 'Sale'),
        ('inventory', 'Inventory'),
        ('employee', 'Employee'),
        ('stock_alert', 'Stock Alert'),
        ('receipt', 'Receipt'),
        ('sync', 'Sync'),
        ('role_change', 'Role Change'),
        ('general', 'General'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='notifications',
        null=True, blank=True, help_text='Specific recipient user'
    )
    recipient_role = models.CharField(
        max_length=20, blank=True, null=True,
        help_text='Target all users with this role type'
    )
    business = models.ForeignKey(
        'shops.Business', on_delete=models.CASCADE, related_name='notifications',
        null=True, blank=True
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=10, choices=NOTIFICATION_TYPES, default='info')
    category = models.CharField(max_length=20, choices=NOTIFICATION_CATEGORIES, default='general')
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    related_object_type = models.CharField(max_length=50, blank=True, null=True)
    related_object_id = models.UUIDField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at']),
            models.Index(fields=['business', '-created_at']),
        ]

    def __str__(self):
        return f"[{self.notification_type}] {self.title}"


# ──────────────────────────────────────────────────────────
# Message model – internal messaging
# ──────────────────────────────────────────────────────────
class Message(models.Model):
    """Internal messaging between employees/owners within a business."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        'shops.Business', on_delete=models.CASCADE, related_name='messages'
    )
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at']),
            models.Index(fields=['sender', '-created_at']),
            models.Index(fields=['business', '-created_at']),
        ]

    def __str__(self):
        return f"Message from {self.sender.username} to {self.recipient.username}"


# ──────────────────────────────────────────────────────────
# Helper methods on User model
# ──────────────────────────────────────────────────────────
def get_user_profile(self):
    profile, created = UserProfile.objects.get_or_create(user=self)
    return profile

def get_preferences(self):
    return self.profile.preferences or {}

def update_preferences(self, preferences_dict):
    self.profile.preferences = preferences_dict
    self.profile.save()
    return self.profile.preferences

User.add_to_class('get_profile', get_user_profile)
User.add_to_class('get_preferences', get_preferences)
User.add_to_class('update_preferences', update_preferences)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

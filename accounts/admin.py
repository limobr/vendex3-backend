from django.contrib import admin
from .models import Permission, Role, UserProfile, Configuration, Notification, Message


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "category", "is_active", "created_at")
    list_filter = ("category", "is_active")
    search_fields = ("name", "code", "description")
    ordering = ("name",)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "role_type", "is_default", "created_at")
    list_filter = ("role_type", "is_default")
    search_fields = ("name", "role_type", "description")
    filter_horizontal = ("permissions",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "user_type", "phone_number", "is_verified", "is_first_login_complete", "created_at")
    list_filter = ("user_type", "is_verified", "is_first_login_complete", "has_changed_temp_password")
    search_fields = ("user__username", "phone_number")


@admin.register(Configuration)
class ConfigurationAdmin(admin.ModelAdmin):
    list_display = ("business", "theme_mode", "operation_mode", "primary_color", "updated_at")
    list_filter = ("theme_mode", "operation_mode")
    search_fields = ("business__name",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "notification_type", "category", "recipient", "is_read", "created_at")
    list_filter = ("notification_type", "category", "is_read")
    search_fields = ("title", "message", "recipient__username")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("sender", "recipient", "business", "is_read", "created_at")
    list_filter = ("is_read", "business")
    search_fields = ("sender__username", "recipient__username", "message")
    readonly_fields = ("created_at", "updated_at")

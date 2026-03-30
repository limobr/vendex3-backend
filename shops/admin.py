from django.contrib import admin
from .models import Business, Shop, Employee


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "phone_number", "email", "is_active", "created_at")
    search_fields = ("name", "owner__username", "phone_number", "email")
    list_filter = ("is_active",)


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "shop_type", "location", "is_active")
    list_filter = ("shop_type", "is_active")
    search_fields = ("name", "business__name", "location")
    ordering = ("name",)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("user", "shop", "role", "is_active", "is_invite_accepted", "employment_date")
    list_filter = ("role", "is_active", "is_invite_accepted", "shop")
    search_fields = ("user__username", "shop__name")
    filter_horizontal = ("custom_permissions",)

# products/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from shops.models import Business
from .utils import create_default_categories_for_business
from .models import Category

@receiver(post_save, sender=Business)
def create_categories_on_business_creation(sender, instance, created, **kwargs):
    """
    When a new Business is created, automatically create the default categories.
    Only runs if the business has no categories yet (safe guard).
    """
    if created and not Category.objects.filter(business=instance).exists():
        count = create_default_categories_for_business(instance)
        # You can add logging here if you like
        print(f"Created {count} default categories for business {instance.name}")
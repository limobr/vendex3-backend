# products/management/commands/populate_categories_for_existing_businesses.py
from django.core.management.base import BaseCommand
from shops.models import Business
from products.models import Category
from products.utils import create_default_categories_for_business

class Command(BaseCommand):
    help = 'Populates default categories for businesses that don\'t have any categories'

    def handle(self, *args, **options):
        businesses = Business.objects.filter(is_active=True)
        for business in businesses:
            if not Category.objects.filter(business=business).exists():
                self.stdout.write(f"Adding categories to {business.name}...")
                count = create_default_categories_for_business(business)
                self.stdout.write(self.style.SUCCESS(f"Added {count} categories to {business.name}"))
            else:
                self.stdout.write(f"Business {business.name} already has categories. Skipping.")
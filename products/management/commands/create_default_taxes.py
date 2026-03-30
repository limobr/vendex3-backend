# products/management/commands/create_default_taxes.py
from django.core.management.base import BaseCommand
from products.models import Tax
from django.utils import timezone

class Command(BaseCommand):
    help = 'Creates default tax entries for the system'

    def handle(self, *args, **kwargs):
        taxes = [
            {
                'name': 'Standard VAT 16%',
                'rate': 16.00,
                'tax_type': 'standard',
                'description': 'Standard Value Added Tax at 16%'
            },
            {
                'name': 'Reduced VAT 8%',
                'rate': 8.00,
                'tax_type': 'standard',
                'description': 'Reduced rate Value Added Tax at 8%'
            },
            {
                'name': 'Zero Rated VAT 0%',
                'rate': 0.00,
                'tax_type': 'zero',
                'description': 'Zero-rated supplies (taxable at 0%)'
            },
            {
                'name': 'Exempt from VAT',
                'rate': 0.00,
                'tax_type': 'exempt',
                'description': 'Exempt from Value Added Tax'
            },
            {
                'name': 'VAT 14%',
                'rate': 14.00,
                'tax_type': 'standard',
                'description': 'Standard Value Added Tax at 14%'
            },
            {
                'name': 'VAT 12%',
                'rate': 12.00,
                'tax_type': 'standard',
                'description': 'Standard Value Added Tax at 12%'
            },
            {
                'name': 'VAT 18%',
                'rate': 18.00,
                'tax_type': 'standard',
                'description': 'Standard Value Added Tax at 18%'
            },
            {
                'name': 'No Tax',
                'rate': 0.00,
                'tax_type': 'exempt',
                'description': 'No tax applicable'
            }
        ]

        created_count = 0
        updated_count = 0
        
        self.stdout.write(self.style.MIGRATE_HEADING('🚀 Creating default taxes...'))
        
        for tax_data in taxes:
            tax, created = Tax.objects.update_or_create(
                name=tax_data['name'],
                defaults={
                    'rate': tax_data['rate'],
                    'tax_type': tax_data['tax_type'],
                    'is_active': True,
                    'created_at': timezone.now()
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Created: {tax.name} ({tax.rate}%) - {tax.tax_type}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'📝 Updated: {tax.name} ({tax.rate}%) - {tax.tax_type}')
                )
        
        # Display summary
        total_taxes = Tax.objects.count()
        
        self.stdout.write('\n' + self.style.MIGRATE_HEADING('📊 TAX CREATION SUMMARY'))
        self.stdout.write(self.style.SUCCESS(f'✅ New taxes created: {created_count}'))
        self.stdout.write(self.style.WARNING(f'📝 Existing taxes updated: {updated_count}'))
        self.stdout.write(self.style.HTTP_INFO(f'📈 Total taxes in system: {total_taxes}'))
        
        # Display all taxes in a table format
        self.stdout.write('\n' + self.style.MIGRATE_HEADING('📋 ALL AVAILABLE TAXES'))
        
        all_taxes = Tax.objects.filter(is_active=True).order_by('rate', 'name')
        if all_taxes.exists():
            for tax in all_taxes:
                status = "🟢" if tax.is_active else "🔴"
                self.stdout.write(
                    f'{status} {tax.name:30} {tax.rate:5.2f}% '
                    f'({tax.tax_type:10})'
                )
        else:
            self.stdout.write(self.style.ERROR('❌ No active taxes found!'))
# accounts/management/commands/create_default_roles.py
from django.core.management.base import BaseCommand
from accounts.models import Role, Permission
import uuid

class Command(BaseCommand):
    help = 'Create default roles for the system'

    def handle(self, *args, **kwargs):
        default_roles = [
            {
                'name': 'Shop Owner',
                'role_type': 'owner',
                'description': 'Full access to all business operations and settings',
                'is_default': True
            },
            {
                'name': 'Shop Manager',
                'role_type': 'manager',
                'description': 'Manage shop operations, employees, and inventory',
                'is_default': True
            },
            {
                'name': 'Cashier',
                'role_type': 'cashier',
                'description': 'Handle sales, transactions, and customer service',
                'is_default': True
            },
            {
                'name': 'Stock Keeper',
                'role_type': 'stock_keeper',
                'description': 'Manage inventory, stock levels, and suppliers',
                'is_default': True
            },
            {
                'name': 'Sales Attendant',
                'role_type': 'attendant',
                'description': 'Assist customers, manage sales floor, and process transactions',
                'is_default': True
            }
        ]

        created_count = 0
        updated_count = 0

        for role_data in default_roles:
            role, created = Role.objects.update_or_create(
                role_type=role_data['role_type'],
                defaults={
                    'name': role_data['name'],
                    'description': role_data['description'],
                    'is_default': role_data['is_default']
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created role: {role.name}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'Updated role: {role.name}'))

        self.stdout.write(self.style.SUCCESS(
            f'Successfully created {created_count} and updated {updated_count} roles'
        ))
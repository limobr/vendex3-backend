# accounts/management/commands/setup_default_data.py
from django.core.management.base import BaseCommand
from accounts.models import Permission, Role

class Command(BaseCommand):
    help = 'Setup default permissions and roles'

    def handle(self, *args, **options):
        # Define all permissions
        permissions_data = [
            # Products
            {'code': 'add_product', 'name': 'Can Add Products', 'category': 'products'},
            {'code': 'edit_product', 'name': 'Can Edit Products', 'category': 'products'},
            {'code': 'delete_product', 'name': 'Can Delete Products', 'category': 'products'},
            {'code': 'view_product', 'name': 'Can View Products', 'category': 'products'},
            
            # Sales
            {'code': 'make_sale', 'name': 'Can Make Sales', 'category': 'sales'},
            {'code': 'view_sale', 'name': 'Can View Sales', 'category': 'sales'},
            {'code': 'void_sale', 'name': 'Can Void Sales', 'category': 'sales'},
            {'code': 'refund_sale', 'name': 'Can Refund Sales', 'category': 'sales'},
            
            # Customers
            {'code': 'add_customer', 'name': 'Can Add Customers', 'category': 'customers'},
            {'code': 'edit_customer', 'name': 'Can Edit Customers', 'category': 'customers'},
            {'code': 'view_customer', 'name': 'Can View Customers', 'category': 'customers'},
            
            # Inventory
            {'code': 'manage_inventory', 'name': 'Can Manage Inventory', 'category': 'inventory'},
            {'code': 'view_inventory', 'name': 'Can View Inventory', 'category': 'inventory'},
            {'code': 'restock_inventory', 'name': 'Can Restock Inventory', 'category': 'inventory'},
            
            # Employees
            {'code': 'add_employee', 'name': 'Can Add Employees', 'category': 'employees'},
            {'code': 'edit_employee', 'name': 'Can Edit Employees', 'category': 'employees'},
            {'code': 'view_employee', 'name': 'Can View Employees', 'category': 'employees'},
            
            # Reports
            {'code': 'view_reports', 'name': 'Can View Reports', 'category': 'reports'},
            {'code': 'export_reports', 'name': 'Can Export Reports', 'category': 'reports'},
            
            # Settings
            {'code': 'manage_shop', 'name': 'Can Manage Shop Settings', 'category': 'settings'},
            {'code': 'manage_business', 'name': 'Can Manage Business Settings', 'category': 'settings'},
        ]

        # Create permissions
        for perm_data in permissions_data:
            Permission.objects.get_or_create(
                code=perm_data['code'],
                defaults=perm_data
            )

        # Define roles with permissions
        roles_data = {
            'owner': {
                'name': 'Shop Owner',
                'description': 'Full access to all features',
                'permissions': [p['code'] for p in permissions_data]
            },
            'manager': {
                'name': 'Shop Manager',
                'description': 'Can manage shop operations and staff',
                'permissions': [p['code'] for p in permissions_data if p['code'] not in ['manage_business']]
            },
            'cashier': {
                'name': 'Cashier',
                'description': 'Can process sales and manage customers',
                'permissions': ['make_sale', 'view_sale', 'void_sale', 'add_customer', 'edit_customer', 'view_customer', 'view_product', 'view_inventory']
            },
            'attendant': {
                'name': 'Sales Attendant',
                'description': 'Can make sales and view products',
                'permissions': ['make_sale', 'view_sale', 'add_customer', 'view_customer', 'view_product', 'view_inventory']
            },
        }

        # Create roles
        for role_type, role_data in roles_data.items():
            role, created = Role.objects.get_or_create(
                role_type=role_type,
                defaults={
                    'name': role_data['name'],
                    'description': role_data['description']
                }
            )
            
            # Assign permissions
            for perm_code in role_data['permissions']:
                try:
                    perm = Permission.objects.get(code=perm_code)
                    role.permissions.add(perm)
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f'Permission {perm_code} not found'))

        self.stdout.write(self.style.SUCCESS('Successfully setup default permissions and roles'))
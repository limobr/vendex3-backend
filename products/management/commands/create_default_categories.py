# products/management/commands/create_default_categories.py
import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from shops.models import Business, Shop
from django.contrib.auth.models import User
from products.models import (
    Category, Product, Tax, ProductAttribute, 
    ProductAttributeValue, ProductVariant, ProductVariantAttribute,
    Inventory, ProductImage
)
from django.utils import timezone
import uuid

class Command(BaseCommand):
    help = 'Creates default product categories and sample products for businesses'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--business-id',
            type=str,
            help='UUID of the business to add categories to (creates for all businesses if not specified)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating categories'
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing categories before creating new ones'
        )
        parser.add_argument(
            '--create-products',
            action='store_true',
            help='Create sample products for each category'
        )
        parser.add_argument(
            '--products-per-category',
            type=int,
            default=3,
            help='Number of sample products to create per category (default: 3)'
        )

    def handle(self, *args, **kwargs):
        business_id = kwargs.get('business_id')
        dry_run = kwargs.get('dry_run', False)
        clear_existing = kwargs.get('clear_existing', False)
        create_products = kwargs.get('create_products', False)
        products_per_category = kwargs.get('products_per_category', 3)
        
        # Default categories for retail/supermarket businesses
        default_categories = [
            # Main Categories (Level 1)
            {
                'name': 'Food & Beverages',
                'description': 'Food items, drinks, and consumables',
                'color': '#FF6B35',
                'subcategories': [
                    {
                        'name': 'Beverages',
                        'description': 'Drinks, juices, sodas, water',
                        'color': '#3B82F6',
                        'subcategories': [
                            {'name': 'Soft Drinks', 'color': '#60A5FA'},
                            {'name': 'Juices', 'color': '#93C5FD'},
                            {'name': 'Water', 'color': '#BFDBFE'},
                            {'name': 'Energy Drinks', 'color': '#DBEAFE'},
                            {'name': 'Tea & Coffee', 'color': '#EFF6FF'},
                        ]
                    },
                    {
                        'name': 'Dairy & Eggs',
                        'description': 'Milk, cheese, yogurt, eggs',
                        'color': '#10B981',
                        'subcategories': [
                            {'name': 'Milk', 'color': '#34D399'},
                            {'name': 'Cheese', 'color': '#6EE7B7'},
                            {'name': 'Yogurt', 'color': '#A7F3D0'},
                            {'name': 'Eggs', 'color': '#D1FAE5'},
                            {'name': 'Butter & Margarine', 'color': '#ECFDF5'},
                        ]
                    },
                    {
                        'name': 'Bakery',
                        'description': 'Bread, pastries, cakes',
                        'color': '#F59E0B',
                        'subcategories': [
                            {'name': 'Bread', 'color': '#FBBF24'},
                            {'name': 'Cakes', 'color': '#FCD34D'},
                            {'name': 'Pastries', 'color': '#FDE68A'},
                            {'name': 'Biscuits & Cookies', 'color': '#FEF3C7'},
                        ]
                    },
                    {
                        'name': 'Snacks & Confectionery',
                        'description': 'Chips, chocolates, candies',
                        'color': '#8B5CF6',
                        'subcategories': [
                            {'name': 'Chocolate', 'color': '#A78BFA'},
                            {'name': 'Chips & Crisps', 'color': '#C4B5FD'},
                            {'name': 'Candy & Sweets', 'color': '#DDD6FE'},
                            {'name': 'Nuts & Seeds', 'color': '#EDE9FE'},
                        ]
                    },
                    {
                        'name': 'Canned & Packaged Foods',
                        'description': 'Canned goods, pasta, rice',
                        'color': '#EF4444',
                        'subcategories': [
                            {'name': 'Canned Vegetables', 'color': '#F87171'},
                            {'name': 'Pasta & Noodles', 'color': '#FCA5A5'},
                            {'name': 'Rice & Grains', 'color': '#FECACA'},
                            {'name': 'Canned Meat & Fish', 'color': '#FEE2E2'},
                        ]
                    }
                ]
            },
            {
                'name': 'Household & Cleaning',
                'description': 'Cleaning supplies, household items',
                'color': '#6366F1',
                'subcategories': [
                    {
                        'name': 'Cleaning Supplies',
                        'description': 'Detergents, cleaners, brushes',
                        'color': '#818CF8',
                        'subcategories': [
                            {'name': 'Laundry Detergent', 'color': '#A5B4FC'},
                            {'name': 'Dish Soap', 'color': '#C7D2FE'},
                            {'name': 'All-Purpose Cleaners', 'color': '#E0E7FF'},
                            {'name': 'Bleach & Disinfectants', 'color': '#EEF2FF'},
                        ]
                    },
                    {
                        'name': 'Paper Products',
                        'description': 'Tissue, toilet paper, paper towels',
                        'color': '#EC4899',
                        'subcategories': [
                            {'name': 'Toilet Paper', 'color': '#F472B6'},
                            {'name': 'Tissues', 'color': '#F9A8D4'},
                            {'name': 'Paper Towels', 'color': '#FBCFE8'},
                            {'name': 'Napkins', 'color': '#FCE7F3'},
                        ]
                    },
                    {
                        'name': 'Kitchen Supplies',
                        'description': 'Utensils, containers, foil',
                        'color': '#14B8A6',
                        'subcategories': [
                            {'name': 'Food Storage', 'color': '#2DD4BF'},
                            {'name': 'Foil & Wrap', 'color': '#5EEAD4'},
                            {'name': 'Trash Bags', 'color': '#99F6E4'},
                            {'name': 'Kitchen Tools', 'color': '#CCFBF1'},
                        ]
                    }
                ]
            },
            {
                'name': 'Personal Care',
                'description': 'Beauty, hygiene, health products',
                'color': '#EC4899',
                'subcategories': [
                    {
                        'name': 'Bath & Body',
                        'description': 'Soap, shampoo, lotion',
                        'color': '#F472B6',
                        'subcategories': [
                            {'name': 'Soap & Body Wash', 'color': '#F9A8D4'},
                            {'name': 'Shampoo & Conditioner', 'color': '#FBCFE8'},
                            {'name': 'Lotion & Moisturizer', 'color': '#FCE7F3'},
                            {'name': 'Deodorant', 'color': '#FDF2F8'},
                        ]
                    },
                    {
                        'name': 'Oral Care',
                        'description': 'Toothpaste, toothbrushes',
                        'color': '#8B5CF6',
                        'subcategories': [
                            {'name': 'Toothpaste', 'color': '#A78BFA'},
                            {'name': 'Toothbrushes', 'color': '#C4B5FD'},
                            {'name': 'Mouthwash', 'color': '#DDD6FE'},
                            {'name': 'Dental Floss', 'color': '#EDE9FE'},
                        ]
                    },
                    {
                        'name': 'Feminine Care',
                        'description': 'Sanitary products',
                        'color': '#EF4444',
                        'subcategories': [
                            {'name': 'Sanitary Pads', 'color': '#F87171'},
                            {'name': 'Tampons', 'color': '#FCA5A5'},
                            {'name': 'Pantyliners', 'color': '#FECACA'},
                        ]
                    },
                    {
                        'name': 'Health & Wellness',
                        'description': 'Vitamins, first aid, medication',
                        'color': '#10B981',
                        'subcategories': [
                            {'name': 'Pain Relief', 'color': '#34D399'},
                            {'name': 'Vitamins & Supplements', 'color': '#6EE7B7'},
                            {'name': 'First Aid', 'color': '#A7F3D0'},
                            {'name': 'Digestive Health', 'color': '#D1FAE5'},
                        ]
                    }
                ]
            },
            {
                'name': 'Baby & Child',
                'description': 'Baby food, diapers, childcare',
                'color': '#F59E0B',
                'subcategories': [
                    {
                        'name': 'Diapers & Wipes',
                        'description': 'Baby diapers, wipes',
                        'color': '#FBBF24',
                        'subcategories': [
                            {'name': 'Diapers', 'color': '#FCD34D'},
                            {'name': 'Baby Wipes', 'color': '#FDE68A'},
                            {'name': 'Diaper Rash Cream', 'color': '#FEF3C7'},
                        ]
                    },
                    {
                        'name': 'Baby Food',
                        'description': 'Formula, baby snacks',
                        'color': '#EF4444',
                        'subcategories': [
                            {'name': 'Infant Formula', 'color': '#F87171'},
                            {'name': 'Baby Cereal', 'color': '#FCA5A5'},
                            {'name': 'Baby Snacks', 'color': '#FECACA'},
                        ]
                    }
                ]
            },
            {
                'name': 'Electronics',
                'description': 'Electronics, accessories, gadgets',
                'color': '#3B82F6',
                'subcategories': [
                    {
                        'name': 'Mobile Accessories',
                        'description': 'Chargers, headphones, cases',
                        'color': '#60A5FA',
                        'subcategories': [
                            {'name': 'Phone Chargers', 'color': '#93C5FD'},
                            {'name': 'Headphones & Earbuds', 'color': '#BFDBFE'},
                            {'name': 'Phone Cases', 'color': '#DBEAFE'},
                            {'name': 'Power Banks', 'color': '#EFF6FF'},
                        ]
                    },
                    {
                        'name': 'Batteries',
                        'description': 'All types of batteries',
                        'color': '#F59E0B',
                        'subcategories': [
                            {'name': 'AA Batteries', 'color': '#FBBF24'},
                            {'name': 'AAA Batteries', 'color': '#FCD34D'},
                            {'name': 'Button Cells', 'color': '#FDE68A'},
                            {'name': '9V Batteries', 'color': '#FEF3C7'},
                        ]
                    }
                ]
            },
            {
                'name': 'Stationery & Office',
                'description': 'Pens, paper, office supplies',
                'color': '#10B981',
                'subcategories': [
                    {
                        'name': 'Writing Instruments',
                        'description': 'Pens, pencils, markers',
                        'color': '#34D399',
                        'subcategories': [
                            {'name': 'Pens', 'color': '#6EE7B7'},
                            {'name': 'Pencils', 'color': '#A7F3D0'},
                            {'name': 'Markers', 'color': '#D1FAE5'},
                        ]
                    },
                    {
                        'name': 'Paper Products',
                        'description': 'Notebooks, paper, envelopes',
                        'color': '#8B5CF6',
                        'subcategories': [
                            {'name': 'Notebooks', 'color': '#A78BFA'},
                            {'name': 'Printing Paper', 'color': '#C4B5FD'},
                            {'name': 'Envelopes', 'color': '#DDD6FE'},
                        ]
                    }
                ]
            },
            {
                'name': 'Pet Supplies',
                'description': 'Pet food, toys, accessories',
                'color': '#F59E0B',
                'subcategories': [
                    {
                        'name': 'Pet Food',
                        'description': 'Dog, cat, bird food',
                        'color': '#FBBF24',
                        'subcategories': [
                            {'name': 'Dog Food', 'color': '#FCD34D'},
                            {'name': 'Cat Food', 'color': '#FDE68A'},
                            {'name': 'Bird Food', 'color': '#FEF3C7'},
                        ]
                    },
                    {
                        'name': 'Pet Accessories',
                        'description': 'Toys, bowls, leashes',
                        'color': '#EF4444',
                        'subcategories': [
                            {'name': 'Pet Toys', 'color': '#F87171'},
                            {'name': 'Food & Water Bowls', 'color': '#FCA5A5'},
                            {'name': 'Leashes & Collars', 'color': '#FECACA'},
                        ]
                    }
                ]
            },
            {
                'name': 'Automotive',
                'description': 'Car care, accessories',
                'color': '#6B7280',
                'subcategories': [
                    {
                        'name': 'Car Care',
                        'description': 'Cleaners, wax, air fresheners',
                        'color': '#9CA3AF',
                        'subcategories': [
                            {'name': 'Car Wash Soap', 'color': '#D1D5DB'},
                            {'name': 'Wax & Polish', 'color': '#E5E7EB'},
                            {'name': 'Air Fresheners', 'color': '#F3F4F6'},
                        ]
                    }
                ]
            },
            {
                'name': 'Miscellaneous',
                'description': 'Other uncategorized items',
                'color': '#6B7280',
                'subcategories': []
            }
        ]
        
        # Sample product data for different categories
        sample_products = {
            'Soft Drinks': [
                {'name': 'Coca-Cola 500ml', 'unit_price': 50, 'has_variants': False, 'description': 'Carbonated soft drink'},
                {'name': 'Pepsi 500ml', 'unit_price': 45, 'has_variants': False, 'description': 'Carbonated soft drink'},
                {'name': 'Fanta Orange 500ml', 'unit_price': 45, 'has_variants': False, 'description': 'Orange flavored soda'},
            ],
            'Juices': [
                {'name': 'Minute Maid Orange Juice 1L', 'unit_price': 120, 'has_variants': True, 'description': '100% pure orange juice'},
                {'name': 'Del Monte Pineapple Juice 1L', 'unit_price': 110, 'has_variants': False, 'description': 'Pineapple juice with pulp'},
            ],
            'Water': [
                {'name': 'Dasani Bottled Water 500ml', 'unit_price': 30, 'has_variants': True, 'description': 'Purified drinking water'},
                {'name': 'Aquafina Water 1L', 'unit_price': 45, 'has_variants': False, 'description': 'Purified drinking water'},
            ],
            'Milk': [
                {'name': 'Brookside Fresh Milk 500ml', 'unit_price': 80, 'has_variants': True, 'description': 'Fresh pasteurized milk'},
                {'name': 'Tuzo UHT Milk 1L', 'unit_price': 120, 'has_variants': False, 'description': 'Long life UHT milk'},
            ],
            'Bread': [
                {'name': 'White Bread Loaf', 'unit_price': 60, 'has_variants': False, 'description': 'Fresh white bread'},
                {'name': 'Brown Bread Loaf', 'unit_price': 70, 'has_variants': False, 'description': 'Whole wheat brown bread'},
            ],
            'Laundry Detergent': [
                {'name': 'OMO Detergent 1kg', 'unit_price': 350, 'has_variants': True, 'description': 'Laundry washing powder'},
                {'name': 'Ariel Detergent 500g', 'unit_price': 200, 'has_variants': False, 'description': 'High efficiency detergent'},
            ],
            'Soap & Body Wash': [
                {'name': 'Imperial Leather Soap', 'unit_price': 100, 'has_variants': True, 'description': 'Bathing soap bar'},
                {'name': 'Dettol Soap', 'unit_price': 120, 'has_variants': False, 'description': 'Antibacterial soap'},
            ],
            'Toothpaste': [
                {'name': 'Colgate Toothpaste 100g', 'unit_price': 150, 'has_variants': False, 'description': 'Fresh mint toothpaste'},
                {'name': 'Sensodyne Toothpaste 75g', 'unit_price': 250, 'has_variants': False, 'description': 'Sensitive teeth toothpaste'},
            ],
            'Diapers': [
                {'name': 'Pampers Diapers Size 3', 'unit_price': 1200, 'has_variants': True, 'description': 'Baby diapers 24-pack'},
                {'name': 'Huggies Diapers Size 2', 'unit_price': 1100, 'has_variants': True, 'description': 'Baby diapers 22-pack'},
            ],
            'Phone Chargers': [
                {'name': 'USB-C Fast Charger', 'unit_price': 800, 'has_variants': True, 'description': 'Fast charging adapter'},
                {'name': 'Micro USB Charger', 'unit_price': 400, 'has_variants': False, 'description': 'Standard micro USB charger'},
            ],
            'Pens': [
                {'name': 'Bic Ballpoint Pen', 'unit_price': 20, 'has_variants': True, 'description': 'Blue ballpoint pen'},
                {'name': 'Stabilo Highlighters 4-pack', 'unit_price': 300, 'has_variants': False, 'description': 'Assorted color highlighters'},
            ],
            'Dog Food': [
                {'name': 'Pedigree Adult Dog Food 1kg', 'unit_price': 500, 'has_variants': True, 'description': 'Complete adult dog food'},
                {'name': 'Royal Canin Puppy Food 500g', 'unit_price': 400, 'has_variants': False, 'description': 'Special puppy formula'},
            ],
            'Car Wash Soap': [
                {'name': 'Turtle Wax Car Wash Soap', 'unit_price': 450, 'has_variants': False, 'description': 'Car wash shampoo'},
                {'name': 'Meguiars Wash & Wax', 'unit_price': 600, 'has_variants': False, 'description': 'Wash and wax combo'},
            ],
        }
        
        # Sample variants data
        sample_variants = {
            'size': ['Small', 'Medium', 'Large'],
            'color': ['Red', 'Blue', 'Green', 'Black', 'White'],
            'flavor': ['Original', 'Mint', 'Strawberry', 'Vanilla'],
            'weight': ['50g', '100g', '200g', '500g', '1kg'],
            'type': ['Regular', 'Extra Strength', 'Sensitive'],
        }
        
        # Determine which businesses to add categories to
        if business_id:
            try:
                businesses = [Business.objects.get(id=business_id)]
                self.stdout.write(self.style.MIGRATE_HEADING(f'🚀 Adding categories to business: {businesses[0].name}'))
            except Business.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'❌ Business with ID {business_id} not found!'))
                return
        else:
            businesses = Business.objects.filter(is_active=True)
            self.stdout.write(self.style.MIGRATE_HEADING(f'🚀 Adding categories to all {businesses.count()} active businesses'))
        
        if not businesses.exists():
            self.stdout.write(self.style.ERROR('❌ No active businesses found!'))
            return
        
        # Create or get default tax rates
        standard_tax = None
        zero_tax = None
        
        if not dry_run:
            standard_tax, _ = Tax.objects.get_or_create(
                name='VAT 16%',
                defaults={
                    'rate': Decimal('16.00'),
                    'tax_type': 'standard',
                    'is_active': True,
                }
            )
            zero_tax, _ = Tax.objects.get_or_create(
                name='Zero Rated',
                defaults={
                    'rate': Decimal('0.00'),
                    'tax_type': 'zero',
                    'is_active': True,
                }
            )
        
        # Get superuser for created_by field
        superuser = User.objects.filter(is_superuser=True).first()
        
        total_categories_created = 0
        total_products_created = 0
        
        for business in businesses:
            self.stdout.write(f'\n📊 Processing: {business.name} (ID: {business.id})')
            
            if clear_existing and not dry_run:
                # Clear existing categories and related products
                deleted_categories = Category.objects.filter(business=business).count()
                Category.objects.filter(business=business).delete()
                self.stdout.write(self.style.WARNING(f'🗑️  Cleared {deleted_categories} existing categories'))
            
            # Create categories
            categories_created = self.create_categories_for_business(
                business, default_categories, dry_run
            )
            total_categories_created += categories_created
            
            if not dry_run:
                total_business_categories = Category.objects.filter(business=business).count()
                self.stdout.write(self.style.SUCCESS(f'✅ Added {categories_created} categories (Total: {total_business_categories})'))
            
            # Create sample products if requested
            if create_products and not dry_run:
                products_created = self.create_sample_products(
                    business, standard_tax, superuser, 
                    products_per_category, sample_products, sample_variants
                )
                total_products_created += products_created
                self.stdout.write(self.style.SUCCESS(f'🛍️  Added {products_created} sample products'))
        
        # Display summary
        self.stdout.write('\n' + self.style.MIGRATE_HEADING('📊 CREATION SUMMARY'))
        self.stdout.write(self.style.SUCCESS(f'✅ Total categories created/updated: {total_categories_created}'))
        self.stdout.write(self.style.SUCCESS(f'✅ Total products created: {total_products_created}'))
        self.stdout.write(self.style.SUCCESS(f'✅ Processed businesses: {len(businesses)}'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️  DRY RUN - No changes were made to the database'))
        
        # Display category tree for first business as example
        if businesses.exists() and not dry_run:
            business = businesses.first()
            self.display_category_tree(business)
    
    def create_categories_for_business(self, business, category_structure, dry_run=False):
        """Recursively create categories for a business"""
        categories_created = 0
        
        def create_category_recursive(category_data, parent=None, level=0):
            nonlocal categories_created
            
            # Create the category
            if not dry_run:
                category, created = Category.objects.get_or_create(
                    business=business,
                    name=category_data['name'],
                    defaults={
                        'description': category_data.get('description', ''),
                        'parent': parent,
                        'color': category_data.get('color', '#FF6B35'),
                        'is_active': True,
                    }
                )
            else:
                created = True  # For dry run, count as created
            
            if created:
                categories_created += 1
            
            indent = "  " * level
            icon = "📁" if category_data.get('subcategories') else "📄"
            
            if dry_run:
                status = "🟡"  # Yellow for dry run
            elif created:
                status = "✅"
            else:
                status = "📝"
            
            self.stdout.write(f'{indent}{status} {icon} {category_data["name"]}')
            
            # Create subcategories recursively
            for subcategory_data in category_data.get('subcategories', []):
                if not dry_run:
                    create_category_recursive(subcategory_data, category, level + 1)
                else:
                    create_category_recursive(subcategory_data, None, level + 1)
        
        # Start creating categories
        for category_data in category_structure:
            create_category_recursive(category_data)
        
        return categories_created
    
    def create_sample_products(self, business, tax, created_by, products_per_category, 
                             sample_products, sample_variants):
        """Create sample products for the business"""
        products_created = 0
        
        # Get all leaf categories (categories without subcategories)
        leaf_categories = Category.objects.filter(
            business=business,
            is_active=True,
            subcategories__isnull=True
        ).distinct()
        
        # Get shops for this business
        shops = Shop.objects.filter(business=business, is_active=True)
        if not shops.exists():
            self.stdout.write(self.style.WARNING(f'⚠️  No active shops found for {business.name}. Creating a default shop.'))
            shop, _ = Shop.objects.get_or_create(
                business=business,
                name=f'{business.name} Main Store',
                defaults={'is_active': True}
            )
            shops = [shop]
        
        # Track created SKUs to avoid duplicates
        created_skus = set()
        
        for category in leaf_categories:
            # Get sample products for this category
            category_products = sample_products.get(category.name, [])
            
            if not category_products:
                # Generate generic products for this category
                category_products = self.generate_generic_products(category, products_per_category)
            
            # Limit to products_per_category
            category_products = category_products[:products_per_category]
            
            for product_data in category_products:
                try:
                    # Generate unique SKU
                    base_sku = self.generate_unique_sku(
                        product_data['name'], category, created_skus
                    )
                    
                    # Calculate prices with margin
                    unit_price = product_data.get('unit_price', random.randint(50, 1000))
                    cost_price = round(unit_price * Decimal('0.6'), 2)  # 40% margin
                    selling_price = unit_price
                    wholesale_price = round(unit_price * Decimal('0.8'), 2)  # 20% discount for wholesale
                    
                    # Determine product type based on category
                    product_type = 'physical'
                    if category.name in ['Software', 'E-books', 'Digital Media']:
                        product_type = 'digital'
                    elif category.name in ['Services', 'Consulting']:
                        product_type = 'service'
                    
                    # Create the product
                    product = Product.objects.create(
                        business=business,
                        name=product_data['name'],
                        description=product_data.get('description', f'{product_data["name"]} - {category.name}'),
                        category=category,
                        product_type=product_type,
                        has_variants=product_data.get('has_variants', False),
                        variant_type='single' if product_data.get('has_variants', False) else 'none',
                        base_sku=base_sku,
                        base_barcode=f'200{base_sku}',
                        base_cost_price=cost_price,
                        base_selling_price=selling_price,
                        base_wholesale_price=wholesale_price,
                        tax=tax,
                        tax_inclusive=True,
                        unit_of_measure='pcs',
                        reorder_level=random.randint(5, 20),
                        is_trackable=True,
                        is_active=True,
                        created_by=created_by,
                    )
                    
                    products_created += 1
                    created_skus.add(base_sku)
                    
                    # Create inventory for each shop
                    for shop in shops:
                        Inventory.objects.create(
                            product=product,
                            shop=shop,
                            current_stock=random.randint(0, 100),
                            reserved_stock=0,
                            minimum_stock=random.randint(5, 20),
                            maximum_stock=random.randint(50, 200),
                            is_active=True,
                        )
                    
                    # Create variants if needed
                    if product_data.get('has_variants', False):
                        self.create_product_variants(
                            product, sample_variants, shops, cost_price, 
                            selling_price, wholesale_price
                        )
                    
                    self.stdout.write(f'  🛒 Created: {product.name} (SKU: {base_sku})')
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ❌ Error creating product: {e}'))
        
        return products_created
    
    def generate_generic_products(self, category, count):
        """Generate generic product names for a category"""
        products = []
        
        base_names = [
            f'Premium {category.name}',
            f'Standard {category.name}',
            f'Budget {category.name}',
            f'Deluxe {category.name}',
            f'Eco-Friendly {category.name}',
        ]
        
        for i in range(min(count, len(base_names))):
            products.append({
                'name': base_names[i],
                'unit_price': random.randint(100, 1000),
                'has_variants': random.choice([True, False]),
                'description': f'High quality {category.name.lower()} product'
            })
        
        return products
    
    def generate_unique_sku(self, product_name, category, existing_skus):
        """Generate a unique SKU for a product"""
        # Extract first letters from category and product
        category_code = ''.join([word[0].upper() for word in category.name.split()[:2]])
        product_code = ''.join([word[0].upper() for word in product_name.split()[:2]])
        
        base_sku = f'{category_code}{product_code}{random.randint(1000, 9999)}'
        
        # Ensure uniqueness
        while base_sku in existing_skus:
            base_sku = f'{category_code}{product_code}{random.randint(1000, 9999)}'
        
        return base_sku
    
    def create_product_variants(self, product, sample_variants, shops, 
                              base_cost, base_selling, base_wholesale):
        """Create variants for a product"""
        variant_attributes = random.choice(list(sample_variants.keys()))
        attribute_values = sample_variants[variant_attributes]
        
        # Create product attribute
        attribute = ProductAttribute.objects.create(
            product=product,
            name=variant_attributes.capitalize(),
            display_order=1,
            is_required=True,
        )
        
        # Create attribute values
        for i, value in enumerate(attribute_values[:3]):  # Limit to 3 variants
            attribute_value = ProductAttributeValue.objects.create(
                attribute=attribute,
                value=value,
                display_order=i,
            )
            
            # Generate variant SKU
            variant_sku = f'{product.base_sku}-{value[:3].upper()}'
            
            # Adjust prices for variants
            price_multiplier = Decimal('1.0') + Decimal(str((i * 0.1)))  # 10% increase per variant
            
            # Create variant
            variant = ProductVariant.objects.create(
                product=product,
                sku=variant_sku,
                barcode=f'300{variant_sku}',
                cost_price=round(base_cost * price_multiplier, 2),
                selling_price=round(base_selling * price_multiplier, 2),
                wholesale_price=round(base_wholesale * price_multiplier, 2),
                is_active=True,
                is_default=(i == 0),
            )
            
            # Link variant to attribute value
            ProductVariantAttribute.objects.create(
                variant=variant,
                attribute=attribute,
                value=attribute_value,
            )
            
            # Create inventory for each shop
            for shop in shops:
                Inventory.objects.create(
                    variant=variant,
                    shop=shop,
                    current_stock=random.randint(0, 50),
                    reserved_stock=0,
                    minimum_stock=random.randint(2, 10),
                    maximum_stock=random.randint(20, 100),
                    is_active=True,
                )
    
    def display_category_tree(self, business):
        """Display the category tree for a business"""
        self.stdout.write('\n' + self.style.MIGRATE_HEADING(f'🌳 CATEGORY TREE FOR {business.name.upper()}'))
        
        def print_category(category, level=0, prefix=""):
            indent = "  " * level
            icon = "📁" if category.subcategories.exists() else "📄"
            
            # Count products in this category
            product_count = category.products.count()
            product_info = f" ({product_count} products)" if product_count > 0 else ""
            
            self.stdout.write(f'{indent}{prefix}{icon} {category.name}{product_info}')
            
            # Print subcategories
            subcategories = category.subcategories.filter(is_active=True).order_by('name')
            for i, subcat in enumerate(subcategories):
                is_last = i == len(subcategories) - 1
                new_prefix = "└── " if is_last else "├── "
                print_category(subcat, level + 1, new_prefix)
        
        # Start with top-level categories (no parent)
        top_categories = Category.objects.filter(
            business=business, 
            parent__isnull=True, 
            is_active=True
        ).order_by('name')
        
        for i, category in enumerate(top_categories):
            is_last = i == len(top_categories) - 1
            prefix = "└── " if is_last else "├── "
            print_category(category, 0, prefix)
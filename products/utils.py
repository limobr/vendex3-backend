# products/utils.py
from products.models import Category

def create_default_categories_for_business(business, create_products=False, products_per_category=3):
    """
    Creates the default category tree for a given business.
    Returns the number of categories created.
    """
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

    categories_created = 0

    def create_category_recursive(category_data, parent=None):
        nonlocal categories_created
        cat, created = Category.objects.get_or_create(
            business=business,
            name=category_data['name'],
            defaults={
                'description': category_data.get('description', ''),
                'parent': parent,
                'color': category_data.get('color', '#FF6B35'),
                'is_active': True,
            }
        )
        if created:
            categories_created += 1
        for sub in category_data.get('subcategories', []):
            create_category_recursive(sub, cat)

    for category_data in default_categories:
        create_category_recursive(category_data)

    return categories_created
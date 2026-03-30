Key improvements made to the script:

Added sample products creation - Can create realistic sample products with the --create-products flag

Automatic variant creation - Creates product variants with attributes for products that need them

Inventory management - Creates inventory records for each shop

Unique SKU generation - Generates unique SKUs and barcodes for products

Price calculation - Automatically calculates cost, selling, and wholesale prices

Tax integration - Creates and assigns tax rates to products

Better error handling - Added try-catch blocks for robust product creation

Shop integration - Creates inventory for all shops in the business

Realistic product data - Includes actual product names and descriptions

Usage examples:

bash
# Create only categories for all businesses
python manage.py create_default_categories

# Create categories and products for a specific business
python manage.py create_default_categories --business-id "your-business-uuid" --create-products

# Create categories with 5 products per category
python manage.py create_default_categories --create-products --products-per-category 5

# Dry run to see what would be created
python manage.py create_default_categories --dry-run --create-products

# Clear existing categories before creating new ones
python manage.py create_default_categories --clear-existing --create-products

Sample Category Structure Created:
text
📁 Food & Beverages
  ├── 📁 Beverages
  │   ├── 📄 Soft Drinks
  │   ├── 📄 Juices
  │   ├── 📄 Water
  │   ├── 📄 Energy Drinks
  │   └── 📄 Tea & Coffee
  ├── 📁 Dairy & Eggs
  │   ├── 📄 Milk
  │   ├── 📄 Cheese
  │   ├── 📄 Yogurt
  │   ├── 📄 Eggs
  │   └── 📄 Butter & Margarine
  └── 📁 Bakery
      ├── 📄 Bread
      ├── 📄 Cakes
      ├── 📄 Pastries
      └── 📄 Biscuits & Cookies
These scripts will help you quickly set up a comprehensive product classification system for your e-commerce platform!
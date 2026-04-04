# products/views.py
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
import logging
from django.db import models
from shops.models import Business, Shop
from .models import (
    PriceHistory, Product, Category, ProductImage, StockMovement, Tax, Inventory, ProductAttribute, 
    ProductAttributeValue, ProductVariant, ProductVariantAttribute
)
from django.db import transaction
from django.contrib.auth.models import User
import uuid

logger = logging.getLogger(__name__)


# Category Views
class CategoryListView(APIView):
    """
    Get all categories for a business
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            business_id = request.query_params.get('business_id')
            
            if not business_id:
                return Response({
                    'success': False,
                    'error': 'business_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify business ownership
            business = get_object_or_404(Business, id=business_id, owner=request.user)
            
            categories = Category.objects.filter(business=business, is_active=True)
            
            category_list = []
            for category in categories:
                # Get product count for this category
                product_count = Product.objects.filter(
                    business=business, 
                    category=category, 
                    is_active=True
                ).count()
                
                category_list.append({
                    'id': str(category.id),
                    'business_id': str(category.business.id),
                    'name': category.name,
                    'description': category.description or '',
                    'parent_id': str(category.parent.id) if category.parent else None,
                    'parent_name': category.parent.name if category.parent else None,
                    'color': category.color,
                    'product_count': product_count,
                    'is_active': category.is_active,
                    'created_at': category.created_at.isoformat(),
                    'updated_at': category.updated_at.isoformat()
                })
            
            return Response({
                'success': True,
                'categories': category_list,
                'count': len(category_list)
            })
            
        except Exception as e:
            logger.error(f"❌ Error getting categories: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class CategoryCreateView(APIView):
    """
    Create a new category
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            data = request.data
            
            logger.info(f"📁 Creating category for user: {user.username}")
            
            # Validate required fields
            required_fields = ['business_id', 'name']
            for field in required_fields:
                if field not in data or not data[field]:
                    return Response({
                        'success': False,
                        'error': f'{field.replace("_", " ").title()} is required'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get business (ensure user owns it)
            business = get_object_or_404(Business, id=data['business_id'], owner=user)
            
            # Check if category with same name already exists for this business
            if Category.objects.filter(business=business, name=data['name'], is_active=True).exists():
                return Response({
                    'success': False,
                    'error': 'A category with this name already exists in this business'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Handle parent category
            parent = None
            if data.get('parent_id'):
                try:
                    parent = Category.objects.get(id=data['parent_id'], business=business)
                except Category.DoesNotExist:
                    return Response({
                        'success': False,
                        'error': 'Parent category not found or does not belong to this business'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create category
            category = Category.objects.create(
                business=business,
                name=data['name'],
                description=data.get('description', ''),
                parent=parent,
                color=data.get('color', '#FF6B35'),
                is_active=True
            )
            
            return Response({
                'success': True,
                'category': {
                    'id': str(category.id),
                    'business_id': str(category.business.id),
                    'name': category.name,
                    'description': category.description or '',
                    'parent_id': str(category.parent.id) if category.parent else None,
                    'color': category.color,
                    'is_active': category.is_active,
                    'created_at': category.created_at.isoformat(),
                    'updated_at': category.updated_at.isoformat()
                },
                'message': 'Category created successfully'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"❌ Error creating category: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


# Tax Views
class TaxListView(APIView):
    """
    Get all available taxes
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            taxes = Tax.objects.filter(is_active=True)
            
            tax_list = []
            for tax in taxes:
                tax_list.append({
                    'id': str(tax.id),
                    'name': tax.name,
                    'rate': float(tax.rate),
                    'tax_type': tax.tax_type,
                    'is_active': tax.is_active,
                    'created_at': tax.created_at.isoformat()
                })
            
            return Response({
                'success': True,
                'taxes': tax_list
            })
            
        except Exception as e:
            logger.error(f"❌ Error getting taxes: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


# Product Views
class ProductCreateView(APIView):
    """
    Create a new product with enhanced validation and autogenerated fields
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            data = request.data
            
            logger.info(f"📦 Creating product for user: {user.username}")
            
            # Enhanced validation: Check all required fields
            required_fields = ['business_id', 'name']
            
            # Check if product has variants to determine price requirements
            has_variants = data.get('has_variants', False)
            
            if not has_variants:
                # For products without variants, all prices are required
                required_fields.extend(['base_selling_price'])
                # Cost price is recommended but not mandatory
                if not data.get('base_cost_price'):
                    logger.warning("Cost price not provided for simple product")
            
            for field in required_fields:
                if field not in data or not data[field]:
                    return Response({
                        'success': False,
                        'error': f'{field.replace("_", " ").title()} is required'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get business (ensure user owns it)
            business = get_object_or_404(Business, id=data['business_id'], owner=user)
            
            # Validate that product name is provided before SKU generation
            if not data.get('name') or data['name'].strip() == '':
                return Response({
                    'success': False,
                    'error': 'Product name is required before generating SKU'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Auto-generate SKU if not provided
            base_sku = data.get('base_sku')
            if not base_sku or base_sku.strip() == '':
                # Generate SKU from product name (first 3 letters, uppercase, remove spaces)
                name = data['name'].strip()
                sku_base = ''.join([c.upper() for c in name[:3] if c.isalpha()]) or 'PRD'
                # Add timestamp to make it unique
                timestamp = str(int(timezone.now().timestamp()))[-6:]
                base_sku = f"{sku_base}{timestamp}"
                
                # Ensure uniqueness
                counter = 1
                original_sku = base_sku
                while Product.objects.filter(business=business, base_sku=base_sku, is_active=True).exists():
                    base_sku = f"{original_sku}_{counter}"
                    counter += 1
            
            # Check SKU uniqueness
            if Product.objects.filter(business=business, base_sku=base_sku, is_active=True).exists():
                return Response({
                    'success': False,
                    'error': 'A product with this SKU already exists in this business'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Handle barcode - generate if requested or validate if provided
            base_barcode = data.get('base_barcode')
            if not base_barcode or base_barcode.strip() == '':
                if data.get('auto_generate_barcode', False):
                    # Generate a simple barcode using timestamp and random number
                    timestamp = str(int(timezone.now().timestamp()))
                    random_part = str(uuid.uuid4().int)[:6]
                    base_barcode = f"BC{timestamp}{random_part}"
                else:
                    base_barcode = None
            elif Product.objects.filter(business=business, base_barcode=base_barcode, is_active=True).exists():
                return Response({
                    'success': False,
                    'error': 'A product with this barcode already exists in this business'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                # Get category if provided
                category = None
                if data.get('category_id'):
                    try:
                        category = Category.objects.get(id=data['category_id'], business=business)
                    except Category.DoesNotExist:
                        return Response({
                            'success': False,
                            'error': 'Category not found or does not belong to this business'
                        }, status=status.HTTP_400_BAD_REQUEST)
                
                # Get tax if provided
                tax = None
                if data.get('tax_id'):
                    try:
                        tax = Tax.objects.get(id=data['tax_id'], is_active=True)
                    except Tax.DoesNotExist:
                        return Response({
                            'success': False,
                            'error': 'Tax not found or is inactive'
                        }, status=status.HTTP_400_BAD_REQUEST)
                
                # Validate prices for variants
                if has_variants:
                    variants_list = data.get('variants', [])
                    
                    # Check if base prices are provided for autofilling variants
                    base_cost_price = data.get('base_cost_price')
                    base_selling_price = data.get('base_selling_price')
                    base_wholesale_price = data.get('base_wholesale_price')
                    
                    # If base prices are provided, use them to autofill variants
                    for variant_data in variants_list:
                        # Autofill prices from base if not provided in variant
                        if base_cost_price and not variant_data.get('cost_price'):
                            variant_data['cost_price'] = base_cost_price
                        if base_selling_price and not variant_data.get('selling_price'):
                            variant_data['selling_price'] = base_selling_price
                        if base_wholesale_price and not variant_data.get('wholesale_price'):
                            variant_data['wholesale_price'] = base_wholesale_price
                        
                        # Validate variant has required prices
                        if not variant_data.get('selling_price'):
                            return Response({
                                'success': False,
                                'error': f'Variant {variant_data.get("name", "unknown")} must have a selling price'
                            }, status=status.HTTP_400_BAD_REQUEST)
                else:
                    # For simple products, validate base prices
                    if not data.get('base_selling_price'):
                        return Response({
                            'success': False,
                            'error': 'Selling price is required for products without variants'
                        }, status=status.HTTP_400_BAD_REQUEST)
                
                # Create product
                product = Product.objects.create(
                    business=business,
                    name=data['name'].strip(),
                    description=data.get('description', '').strip(),
                    category=category,
                    product_type=data.get('product_type', 'physical'),
                    has_variants=has_variants,
                    variant_type=data.get('variant_type', 'none'),
                    base_barcode=base_barcode,
                    base_sku=base_sku,
                    base_cost_price=data.get('base_cost_price'),
                    base_selling_price=data.get('base_selling_price'),
                    base_wholesale_price=data.get('base_wholesale_price'),
                    tax=tax,
                    tax_inclusive=data.get('tax_inclusive', True),
                    unit_of_measure=data.get('unit_of_measure', 'pcs'),
                    reorder_level=data.get('reorder_level', 10),
                    is_trackable=data.get('is_trackable', True),
                    is_active=True,
                    created_by=user
                )
                
                # Handle variants if product has variants
                variants_data = []
                if has_variants:
                    # Create attributes
                    attributes_data = data.get('attributes', [])
                    attributes_map = {}
                    
                    for attr_data in attributes_data:
                        attribute = ProductAttribute.objects.create(
                            product=product,
                            name=attr_data['name'],
                            display_order=attr_data.get('display_order', 0),
                            is_required=attr_data.get('is_required', True)
                        )
                        
                        # Create attribute values
                        values = []
                        for value_data in attr_data.get('values', []):
                            value = ProductAttributeValue.objects.create(
                                attribute=attribute,
                                value=value_data['value'],
                                display_order=value_data.get('display_order', 0)
                            )
                            values.append({
                                'id': str(value.id),
                                'value': value.value,
                                'display_order': value.display_order
                            })
                        
                        attributes_map[attr_data['name']] = {
                            'attribute_id': str(attribute.id),
                            'values': values
                        }
                    
                    # Create variants
                    variants_list = data.get('variants', [])
                    variant_inventory = []
                    
                    for variant_data in variants_list:
                        # Auto-generate variant SKU if not provided
                        variant_sku = variant_data.get('sku')
                        if not variant_sku or variant_sku.strip() == '':
                            # Use product SKU as base
                            variant_sku = f"{base_sku}_{len(variants_data) + 1}"
                            
                            # Ensure uniqueness
                            counter = 1
                            original_variant_sku = variant_sku
                            while ProductVariant.objects.filter(sku=variant_sku).exists():
                                variant_sku = f"{original_variant_sku}_{counter}"
                                counter += 1
                        
                        # Auto-generate variant barcode if not provided
                        variant_barcode = variant_data.get('barcode')
                        if not variant_barcode or variant_barcode.strip() == '':
                            if variant_data.get('auto_generate_barcode', False):
                                timestamp = str(int(timezone.now().timestamp()))
                                random_part = str(uuid.uuid4().int)[:6]
                                variant_barcode = f"VBC{timestamp}{random_part}"
                            else:
                                variant_barcode = None
                        
                        # Create variant
                        variant = ProductVariant.objects.create(
                            product=product,
                            name=variant_data.get('name', ''),
                            sku=variant_sku,
                            barcode=variant_barcode,
                            cost_price=variant_data.get('cost_price'),
                            selling_price=variant_data.get('selling_price'),
                            wholesale_price=variant_data.get('wholesale_price'),
                            weight=variant_data.get('weight'),
                            dimensions=variant_data.get('dimensions'),
                            is_active=True,
                            is_default=variant_data.get('is_default', False)
                        )
                        
                        # Link variant to attribute values
                        for attr_value_data in variant_data.get('attribute_values', []):
                            attribute_name = attr_value_data['attribute_name']
                            value_value = attr_value_data['value']
                            
                            # Find the attribute and value
                            if attribute_name in attributes_map:
                                attribute = ProductAttribute.objects.get(
                                    id=attributes_map[attribute_name]['attribute_id']
                                )
                                value = ProductAttributeValue.objects.get(
                                    attribute=attribute,
                                    value=value_value
                                )
                                
                                ProductVariantAttribute.objects.create(
                                    variant=variant,
                                    attribute=attribute,
                                    value=value
                                )
                        
                        # Create inventory for variant if provided
                        if 'shop_inventory' in variant_data:
                            for shop_inv_data in variant_data['shop_inventory']:
                                shop_id = shop_inv_data.get('shop_id')
                                current_stock = shop_inv_data.get('current_stock', 0)
                                
                                try:
                                    shop = Shop.objects.get(id=shop_id, business=business)
                                    
                                    inventory = Inventory.objects.create(
                                        variant=variant,
                                        shop=shop,
                                        current_stock=current_stock,
                                        reserved_stock=0,
                                        minimum_stock=shop_inv_data.get('minimum_stock', 0),
                                        maximum_stock=shop_inv_data.get('maximum_stock'),
                                        is_active=True
                                    )
                                    
                                    variant_inventory.append({
                                        'variant_id': str(variant.id),
                                        'shop_id': str(shop.id),
                                        'shop_name': shop.name,
                                        'current_stock': inventory.current_stock,
                                        'minimum_stock': inventory.minimum_stock
                                    })
                                    
                                except Shop.DoesNotExist:
                                    logger.warning(f"Shop {shop_id} not found")
                        
                        variants_data.append({
                            'id': str(variant.id),
                            'name': variant.name,
                            'sku': variant.sku,
                            'barcode': variant.barcode,
                            'cost_price': float(variant.cost_price) if variant.cost_price else None,
                            'selling_price': float(variant.selling_price) if variant.selling_price else None,
                            'wholesale_price': float(variant.wholesale_price) if variant.wholesale_price else None,
                            'is_default': variant.is_default,
                            'is_active': variant.is_active
                        })
                
                else:
                    # Create inventory for simple product
                    shop_inventory = []
                    if data.get('shop_inventory'):
                        for shop_inv_data in data['shop_inventory']:
                            shop_id = shop_inv_data.get('shop_id')
                            current_stock = shop_inv_data.get('current_stock', 0)
                            
                            try:
                                shop = Shop.objects.get(id=shop_id, business=business)
                                
                                inventory = Inventory.objects.create(
                                    product=product,
                                    shop=shop,
                                    current_stock=current_stock,
                                    reserved_stock=0,
                                    minimum_stock=shop_inv_data.get('minimum_stock', 0),
                                    maximum_stock=shop_inv_data.get('maximum_stock'),
                                    is_active=True
                                )
                                
                                shop_inventory.append({
                                    'shop_id': str(shop.id),
                                    'shop_name': shop.name,
                                    'current_stock': inventory.current_stock,
                                    'minimum_stock': inventory.minimum_stock
                                })
                                
                            except Shop.DoesNotExist:
                                logger.warning(f"Shop {shop_id} not found")
                
                # Prepare response
                product_data = {
                    'id': str(product.id),
                    'business_id': str(product.business.id),
                    'name': product.name,
                    'description': product.description or '',
                    'category_id': str(product.category.id) if product.category else None,
                    'category_name': product.category.name if product.category else None,
                    'product_type': product.product_type,
                    'has_variants': product.has_variants,
                    'variant_type': product.variant_type,
                    'base_barcode': product.base_barcode,
                    'base_sku': product.base_sku,
                    'base_cost_price': float(product.base_cost_price) if product.base_cost_price else None,
                    'base_selling_price': float(product.base_selling_price) if product.base_selling_price else None,
                    'base_wholesale_price': float(product.base_wholesale_price) if product.base_wholesale_price else None,
                    'tax_id': str(product.tax.id) if product.tax else None,
                    'tax_name': product.tax.name if product.tax else None,
                    'tax_rate': float(product.tax.rate) if product.tax else None,
                    'tax_inclusive': product.tax_inclusive,
                    'unit_of_measure': product.unit_of_measure,
                    'reorder_level': product.reorder_level,
                    'is_trackable': product.is_trackable,
                    'is_active': product.is_active,
                    'created_by': {
                        'id': user.id,
                        'username': user.username,
                        'full_name': f"{user.first_name} {user.last_name}".strip() or user.username
                    },
                    'created_at': product.created_at.isoformat(),
                    'updated_at': product.updated_at.isoformat(),
                    'shop_inventory': shop_inventory if not has_variants else [],
                    'variants': variants_data if has_variants else [],
                    'attributes': attributes_map if has_variants else {}
                }
                
                return Response({
                    'success': True,
                    'product': product_data,
                    'message': 'Product created successfully'
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"❌ Error creating product: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class ProductListView(APIView):
    """
    Get all products for a business
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            business_id = request.query_params.get('business_id')
            shop_id = request.query_params.get('shop_id')
            category_id = request.query_params.get('category_id')
            search = request.query_params.get('search', '')
            include_variants = request.query_params.get('include_variants', 'false').lower() == 'true'
            
            if not business_id and not shop_id:
                return Response({
                    'success': False,
                    'error': 'Either business_id or shop_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Build query
            products_query = Product.objects.filter(is_active=True)
            
            if business_id:
                # Verify business ownership
                business = get_object_or_404(Business, id=business_id, owner=request.user)
                products_query = products_query.filter(business=business)
            elif shop_id:
                # Verify shop ownership through business
                shop = get_object_or_404(Shop, id=shop_id, business__owner=request.user)
                products_query = products_query.filter(business=shop.business)
            
            # Apply filters
            if category_id:
                products_query = products_query.filter(category_id=category_id)
            
            if search:
                products_query = products_query.filter(
                    models.Q(name__icontains=search) |
                    models.Q(description__icontains=search) |
                    models.Q(base_sku__icontains=search) |
                    models.Q(base_barcode__icontains=search)
                )
            
            products = products_query.select_related('category', 'tax', 'created_by')
            
            product_list = []
            for product in products:
                # Get inventory for the specific shop if provided
                inventory_data = None
                if shop_id:
                    try:
                        # For simple products
                        if not product.has_variants:
                            inventory = Inventory.objects.get(
                                product=product, 
                                shop_id=shop_id, 
                                is_active=True
                            )
                            inventory_data = {
                                'current_stock': inventory.current_stock,
                                'reserved_stock': inventory.reserved_stock,
                                'available_stock': inventory.available_stock(),
                                'minimum_stock': inventory.minimum_stock,
                                'maximum_stock': inventory.maximum_stock
                            }
                        # For products with variants
                        else:
                            # Get total stock across all variants
                            variants_inventory = Inventory.objects.filter(
                                variant__product=product,
                                shop_id=shop_id,
                                is_active=True
                            )
                            total_stock = sum(inv.current_stock for inv in variants_inventory)
                            total_reserved = sum(inv.reserved_stock for inv in variants_inventory)
                            
                            inventory_data = {
                                'current_stock': total_stock,
                                'reserved_stock': total_reserved,
                                'available_stock': total_stock - total_reserved,
                                'minimum_stock': product.reorder_level,
                                'maximum_stock': None
                            }
                    except Inventory.DoesNotExist:
                        inventory_data = None
                
                # Calculate tax amount
                tax_amount = 0
                if product.tax and product.tax_inclusive:
                    tax_rate = float(product.tax.rate) / 100
                    selling_price = float(product.base_selling_price) if product.base_selling_price else 0
                    tax_amount = selling_price - (selling_price / (1 + tax_rate))
                
                product_data = {
                    'id': str(product.id),
                    'business_id': str(product.business.id),
                    'name': product.name,
                    'description': product.description or '',
                    'category_id': str(product.category.id) if product.category else None,
                    'category_name': product.category.name if product.category else None,
                    'product_type': product.product_type,
                    'has_variants': product.has_variants,
                    'variant_type': product.variant_type,
                    'base_barcode': product.base_barcode,
                    'base_sku': product.base_sku,
                    'base_cost_price': float(product.base_cost_price) if product.base_cost_price else None,
                    'base_selling_price': float(product.base_selling_price) if product.base_selling_price else None,
                    'base_wholesale_price': float(product.base_wholesale_price) if product.base_wholesale_price else None,
                    'tax_id': str(product.tax.id) if product.tax else None,
                    'tax_name': product.tax.name if product.tax else None,
                    'tax_rate': float(product.tax.rate) if product.tax else None,
                    'tax_inclusive': product.tax_inclusive,
                    'tax_amount': round(tax_amount, 2),
                    'final_price': float(product.base_selling_price) if product.base_selling_price else 0,
                    'unit_of_measure': product.unit_of_measure,
                    'reorder_level': product.reorder_level,
                    'is_trackable': product.is_trackable,
                    'is_active': product.is_active,
                    'inventory': inventory_data,
                    'created_by': {
                        'id': product.created_by.id,
                        'username': product.created_by.username,
                        'full_name': f"{product.created_by.first_name} {product.created_by.last_name}".strip() or product.created_by.username
                    },
                    'created_at': product.created_at.isoformat(),
                    'updated_at': product.updated_at.isoformat()
                }
                
                # Include variants if requested
                if include_variants and product.has_variants:
                    variants = ProductVariant.objects.filter(
                        product=product, 
                        is_active=True
                    ).select_related('product')
                    
                    variant_list = []
                    for variant in variants:
                        variant_inventory = None
                        if shop_id:
                            try:
                                inv = Inventory.objects.get(
                                    variant=variant,
                                    shop_id=shop_id,
                                    is_active=True
                                )
                                variant_inventory = {
                                    'current_stock': inv.current_stock,
                                    'available_stock': inv.available_stock()
                                }
                            except Inventory.DoesNotExist:
                                variant_inventory = None
                        
                        variant_list.append({
                            'id': str(variant.id),
                            'name': variant.name,
                            'sku': variant.sku,
                            'barcode': variant.barcode,
                            'cost_price': float(variant.cost_price) if variant.cost_price else None,
                            'selling_price': float(variant.selling_price) if variant.selling_price else None,
                            'wholesale_price': float(variant.wholesale_price) if variant.wholesale_price else None,
                            'is_default': variant.is_default,
                            'inventory': variant_inventory
                        })
                    
                    product_data['variants'] = variant_list
                
                product_list.append(product_data)
            
            return Response({
                'success': True,
                'products': product_list,
                'count': len(product_list)
            })
            
        except Exception as e:
            logger.error(f"❌ Error getting products: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class ProductDetailView(APIView):
    """
    Get, update, or delete a product
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, product_id):
        try:
            logger.info(f"🔍 Fetching product details for ID: {product_id}")
            logger.info(f"🔍 Request user: {request.user.username}, ID: {request.user.id}")
            
            # First try to get the product by ID
            try:
                product = Product.objects.get(id=product_id, is_active=True)
                logger.info(f"✅ Found product: {product.name}")
            except Product.DoesNotExist:
                logger.error(f"❌ Product {product_id} not found or not active")
                return Response({
                    'success': False,
                    'error': 'Product not found or not active'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Check if user owns the business that owns this product
            if product.business.owner != request.user:
                logger.error(f"❌ User {request.user.id} does not own business {product.business.id}")
                return Response({
                    'success': False,
                    'error': 'You do not have permission to access this product'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Get inventory for this product across shops
            inventory_list = []
            if not product.has_variants:
                inventories = Inventory.objects.filter(
                    product=product, 
                    is_active=True
                ).select_related('shop')
                
                for inv in inventories:
                    inventory_list.append({
                        'shop_id': str(inv.shop.id),
                        'shop_name': inv.shop.name,
                        'current_stock': inv.current_stock,
                        'reserved_stock': inv.reserved_stock,
                        'available_stock': inv.available_stock(),
                        'minimum_stock': inv.minimum_stock,
                        'maximum_stock': inv.maximum_stock,
                        'last_restocked': inv.last_restocked.isoformat() if inv.last_restocked else None,
                        'is_active': inv.is_active
                    })
            else:
                # For products with variants, get inventory per variant
                inventories = Inventory.objects.filter(
                    variant__product=product,
                    is_active=True
                ).select_related('shop', 'variant')
                
                variant_inventory_map = {}
                for inv in inventories:
                    shop_id = str(inv.shop.id)
                    variant_id = str(inv.variant.id)
                    
                    if variant_id not in variant_inventory_map:
                        variant_inventory_map[variant_id] = {
                            'variant_id': variant_id,
                            'variant_name': inv.variant.name,
                            'shops': {}
                        }
                    
                    variant_inventory_map[variant_id]['shops'][shop_id] = {
                        'shop_id': shop_id,
                        'shop_name': inv.shop.name,
                        'current_stock': inv.current_stock,
                        'reserved_stock': inv.reserved_stock,
                        'available_stock': inv.available_stock(),
                        'minimum_stock': inv.minimum_stock,
                        'maximum_stock': inv.maximum_stock
                    }
                
                inventory_list = list(variant_inventory_map.values())
            
            # Get attributes and variants if product has variants
            attributes_data = []
            variants_data = []
            
            if product.has_variants:
                # Get attributes
                attributes = ProductAttribute.objects.filter(
                    product=product
                ).prefetch_related('values')
                
                for attr in attributes:
                    values = attr.values.all()
                    attributes_data.append({
                        'id': str(attr.id),
                        'name': attr.name,
                        'display_order': attr.display_order,
                        'is_required': attr.is_required,
                        'values': [{
                            'id': str(val.id),
                            'value': val.value,
                            'display_order': val.display_order
                        } for val in values]
                    })
                
                # Get variants
                variants = ProductVariant.objects.filter(
                    product=product,
                    is_active=True
                ).prefetch_related('attribute_values__attribute', 'attribute_values__value')
                
                for variant in variants:
                    # Get attribute values for this variant
                    variant_attributes = []
                    for v_attr in variant.attribute_values.all():
                        variant_attributes.append({
                            'attribute_id': str(v_attr.attribute.id),
                            'attribute_name': v_attr.attribute.name,
                            'value_id': str(v_attr.value.id),
                            'value': v_attr.value.value
                        })
                    
                    variants_data.append({
                        'id': str(variant.id),
                        'name': variant.name,
                        'sku': variant.sku,
                        'barcode': variant.barcode,
                        'cost_price': float(variant.cost_price) if variant.cost_price else None,
                        'selling_price': float(variant.selling_price) if variant.selling_price else None,
                        'wholesale_price': float(variant.wholesale_price) if variant.wholesale_price else None,
                        'weight': float(variant.weight) if variant.weight else None,
                        'dimensions': variant.dimensions,
                        'is_default': variant.is_default,
                        'is_active': variant.is_active,
                        'attribute_values': variant_attributes,
                        'created_at': variant.created_at.isoformat(),
                        'updated_at': variant.updated_at.isoformat()
                    })
            
            # Calculate tax amount
            tax_amount = 0
            if product.tax and product.tax_inclusive and product.base_selling_price:
                try:
                    tax_rate = float(product.tax.rate) / 100
                    selling_price = float(product.base_selling_price)
                    tax_amount = selling_price - (selling_price / (1 + tax_rate))
                except (TypeError, ValueError, ZeroDivisionError) as e:
                    logger.warning(f"⚠️ Error calculating tax for product {product.id}: {e}")
                    tax_amount = 0
            
            # Prepare created_by data safely
            created_by_data = None
            if product.created_by:
                try:
                    full_name = f"{product.created_by.first_name or ''} {product.created_by.last_name or ''}".strip()
                    if not full_name:
                        full_name = product.created_by.username
                    
                    created_by_data = {
                        'id': product.created_by.id,
                        'username': product.created_by.username,
                        'full_name': full_name
                    }
                except Exception as e:
                    logger.warning(f"⚠️ Error preparing created_by data for product {product.id}: {e}")
                    created_by_data = {
                        'id': None,
                        'username': 'Unknown',
                        'full_name': 'Unknown'
                    }
            
            # Prepare category data safely
            category_id = None
            category_name = None
            if product.category:
                category_id = str(product.category.id)
                category_name = product.category.name
            
            # Prepare tax data safely
            tax_id = None
            tax_name = None
            tax_rate = None
            tax_type = None
            if product.tax:
                tax_id = str(product.tax.id)
                tax_name = product.tax.name
                tax_rate = float(product.tax.rate) if product.tax.rate else None
                tax_type = product.tax.tax_type
            
            # Build response
            response_data = {
                'id': str(product.id),
                'business_id': str(product.business.id),
                'business_name': product.business.name,
                'name': product.name,
                'description': product.description or '',
                'category_id': category_id,
                'category_name': category_name,
                'product_type': product.product_type,
                'has_variants': product.has_variants,
                'variant_type': product.variant_type,
                'base_barcode': product.base_barcode,
                'base_sku': product.base_sku,
                'base_cost_price': float(product.base_cost_price) if product.base_cost_price else None,
                'base_selling_price': float(product.base_selling_price) if product.base_selling_price else None,
                'base_wholesale_price': float(product.base_wholesale_price) if product.base_wholesale_price else None,
                'tax_id': tax_id,
                'tax_name': tax_name,
                'tax_rate': tax_rate,
                'tax_type': tax_type,
                'tax_inclusive': product.tax_inclusive,
                'tax_amount': round(tax_amount, 2),
                'final_price': float(product.base_selling_price) if product.base_selling_price else 0,
                'unit_of_measure': product.unit_of_measure,
                'reorder_level': product.reorder_level,
                'is_trackable': product.is_trackable,
                'is_active': product.is_active,
                'created_by': created_by_data,
                'created_at': product.created_at.isoformat(),
                'updated_at': product.updated_at.isoformat(),
                'inventories': inventory_list,
                'attributes': attributes_data,
                'variants': variants_data
            }
            
            logger.info(f"✅ Successfully fetched product {product.name}")
            return Response({
                'success': True,
                'product': response_data
            })
            
        except Exception as e:
            logger.error(f"❌ Error getting product details: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': 'Failed to fetch product details. Please try again.'
            }, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, product_id):
        try:
            logger.info(f"🔄 Updating product: {product_id}")
            
            # Get the product
            try:
                product = Product.objects.get(id=product_id, is_active=True)
            except Product.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Product not found or not active'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Check ownership
            if product.business.owner != request.user:
                return Response({
                    'success': False,
                    'error': 'You do not have permission to update this product'
                }, status=status.HTTP_403_FORBIDDEN)
            
            data = request.data
            
            with transaction.atomic():
                # Update product fields
                update_fields = [
                    'name', 'description', 'category_id', 'product_type',
                    'has_variants', 'variant_type', 'base_barcode', 'base_sku',
                    'base_cost_price', 'base_selling_price', 'base_wholesale_price',
                    'tax_id', 'tax_inclusive', 'unit_of_measure', 'reorder_level',
                    'is_trackable', 'is_active'
                ]
                
                for field in update_fields:
                    if field in data:
                        if field == 'category_id':
                            if data[field]:
                                try:
                                    category = Category.objects.get(
                                        id=data[field], 
                                        business=product.business
                                    )
                                    product.category = category
                                except Category.DoesNotExist:
                                    return Response({
                                        'success': False,
                                        'error': 'Category not found or does not belong to this business'
                                    }, status=status.HTTP_400_BAD_REQUEST)
                            else:
                                product.category = None
                        elif field == 'tax_id':
                            if data[field]:
                                try:
                                    tax = Tax.objects.get(id=data[field], is_active=True)
                                    product.tax = tax
                                except Tax.DoesNotExist:
                                    return Response({
                                        'success': False,
                                        'error': 'Tax not found or is inactive'
                                    }, status=status.HTTP_400_BAD_REQUEST)
                            else:
                                product.tax = None
                        else:
                            # Handle decimal fields
                            if field in ['base_cost_price', 'base_selling_price', 'base_wholesale_price']:
                                if data[field] == '' or data[field] is None:
                                    setattr(product, field, None)
                                else:
                                    try:
                                        setattr(product, field, float(data[field]))
                                    except (ValueError, TypeError):
                                        return Response({
                                            'success': False,
                                            'error': f'{field.replace("_", " ").title()} must be a valid number'
                                        }, status=status.HTTP_400_BAD_REQUEST)
                            elif field == 'reorder_level':
                                try:
                                    setattr(product, field, int(data[field]))
                                except (ValueError, TypeError):
                                    return Response({
                                        'success': False,
                                        'error': 'Reorder level must be a valid integer'
                                    }, status=status.HTTP_400_BAD_REQUEST)
                            else:
                                setattr(product, field, data[field])
                
                product.updated_at = timezone.now()
                product.save()
                
                # Update inventory if provided (for simple products)
                if 'shop_inventory' in data and not product.has_variants:
                    for shop_inv_data in data['shop_inventory']:
                        shop_id = shop_inv_data.get('shop_id')
                        current_stock = shop_inv_data.get('current_stock')
                        
                        try:
                            shop = Shop.objects.get(id=shop_id, business=product.business)
                            inventory, created = Inventory.objects.update_or_create(
                                product=product,
                                shop=shop,
                                defaults={
                                    'current_stock': current_stock,
                                    'updated_at': timezone.now()
                                }
                            )
                        except Exception as e:
                            logger.error(f"Error updating inventory for shop {shop_id}: {str(e)}")
                
                # Update variants if provided
                if 'variants' in data and product.has_variants:
                    for variant_data in data['variants']:
                        variant_id = variant_data.get('id')
                        if variant_id:
                            try:
                                variant = ProductVariant.objects.get(
                                    id=variant_id,
                                    product=product
                                )
                                
                                # Update variant fields
                                variant_fields = [
                                    'name', 'sku', 'barcode', 'cost_price',
                                    'selling_price', 'wholesale_price', 'weight',
                                    'dimensions', 'is_default', 'is_active'
                                ]
                                
                                for field in variant_fields:
                                    if field in variant_data:
                                        if field in ['cost_price', 'selling_price', 'wholesale_price', 'weight']:
                                            if variant_data[field] == '' or variant_data[field] is None:
                                                setattr(variant, field, None)
                                            else:
                                                try:
                                                    setattr(variant, field, float(variant_data[field]))
                                                except (ValueError, TypeError):
                                                    logger.warning(f"Invalid value for {field} in variant {variant_id}")
                                        else:
                                            setattr(variant, field, variant_data[field])
                                
                                variant.save()
                                
                                # Update variant inventory if provided
                                if 'shop_inventory' in variant_data:
                                    for shop_inv_data in variant_data['shop_inventory']:
                                        shop_id = shop_inv_data.get('shop_id')
                                        current_stock = shop_inv_data.get('current_stock')
                                        
                                        try:
                                            shop = Shop.objects.get(id=shop_id, business=product.business)
                                            inventory, created = Inventory.objects.update_or_create(
                                                variant=variant,
                                                shop=shop,
                                                defaults={
                                                    'current_stock': current_stock,
                                                    'updated_at': timezone.now()
                                                }
                                            )
                                        except Exception as e:
                                            logger.error(f"Error updating inventory for variant {variant_id}, shop {shop_id}: {str(e)}")
                                
                            except ProductVariant.DoesNotExist:
                                logger.warning(f"Variant {variant_id} not found")
            
            return Response({
                'success': True,
                'product': {
                    'id': str(product.id),
                    'name': product.name,
                    'updated_at': product.updated_at.isoformat()
                },
                'message': 'Product updated successfully'
            })
            
        except Exception as e:
            logger.error(f"❌ Error updating product: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': str(e) if str(e) else 'Failed to update product'
            }, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, product_id):
        try:
            product = get_object_or_404(
                Product, 
                id=product_id, 
                business__owner=request.user
            )
            
            # Soft delete
            product.is_active = False
            product.updated_at = timezone.now()
            product.save()
            
            # Also soft delete related inventories and variants
            if product.has_variants:
                ProductVariant.objects.filter(product=product).update(is_active=False)
                Inventory.objects.filter(variant__product=product).update(is_active=False)
            else:
                Inventory.objects.filter(product=product).update(is_active=False)
            
            return Response({
                'success': True,
                'message': 'Product deleted successfully'
            })
            
        except Exception as e:
            logger.error(f"❌ Error deleting product: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


# Attribute and Variant Views
class ProductAttributeCreateView(APIView):
    """
    Create attributes for a product
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            data = request.data
            
            logger.info(f"🏷️ Creating attribute for user: {user.username}")
            
            # Validate required fields
            required_fields = ['product_id', 'name']
            for field in required_fields:
                if field not in data or not data[field]:
                    return Response({
                        'success': False,
                        'error': f'{field.replace("_", " ").title()} is required'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get product (ensure user owns the business)
            product = get_object_or_404(
                Product, 
                id=data['product_id'],
                business__owner=user
            )
            
            # Check if attribute with same name already exists for this product
            if ProductAttribute.objects.filter(product=product, name=data['name']).exists():
                return Response({
                    'success': False,
                    'error': 'An attribute with this name already exists for this product'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create attribute
            attribute = ProductAttribute.objects.create(
                product=product,
                name=data['name'],
                display_order=data.get('display_order', 0),
                is_required=data.get('is_required', True)
            )
            
            # Create attribute values if provided
            values_data = []
            if 'values' in data:
                for value_data in data['values']:
                    value = ProductAttributeValue.objects.create(
                        attribute=attribute,
                        value=value_data['value'],
                        display_order=value_data.get('display_order', 0)
                    )
                    values_data.append({
                        'id': str(value.id),
                        'value': value.value,
                        'display_order': value.display_order
                    })
            
            return Response({
                'success': True,
                'attribute': {
                    'id': str(attribute.id),
                    'product_id': str(attribute.product.id),
                    'name': attribute.name,
                    'display_order': attribute.display_order,
                    'is_required': attribute.is_required,
                    'values': values_data,
                    'created_at': attribute.created_at.isoformat(),
                    'updated_at': attribute.updated_at.isoformat()
                },
                'message': 'Attribute created successfully'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"❌ Error creating attribute: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class ProductVariantCreateView(APIView):
    """
    Create a variant for a product
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            data = request.data
            
            logger.info(f"🔄 Creating variant for user: {user.username}")
            
            # Validate required fields
            required_fields = ['product_id']
            for field in required_fields:
                if field not in data or not data[field]:
                    return Response({
                        'success': False,
                        'error': f'{field.replace("_", " ").title()} is required'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get product (ensure user owns the business)
            product = get_object_or_404(
                Product, 
                id=data['product_id'],
                business__owner=user
            )
            
            # Check if product supports variants
            if not product.has_variants:
                return Response({
                    'success': False,
                    'error': 'This product does not support variants'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                # Create variant
                variant = ProductVariant.objects.create(
                    product=product,
                    name=data.get('name', ''),
                    sku=data.get('sku', ''),
                    barcode=data.get('barcode', ''),
                    cost_price=data.get('cost_price'),
                    selling_price=data.get('selling_price'),
                    wholesale_price=data.get('wholesale_price'),
                    weight=data.get('weight'),
                    dimensions=data.get('dimensions'),
                    is_active=True,
                    is_default=data.get('is_default', False)
                )
                
                # Link variant to attribute values
                if 'attribute_values' in data:
                    for attr_value_data in data['attribute_values']:
                        attribute_id = attr_value_data.get('attribute_id')
                        value_id = attr_value_data.get('value_id')
                        
                        try:
                            attribute = ProductAttribute.objects.get(
                                id=attribute_id,
                                product=product
                            )
                            value = ProductAttributeValue.objects.get(
                                id=value_id,
                                attribute=attribute
                            )
                            
                            ProductVariantAttribute.objects.create(
                                variant=variant,
                                attribute=attribute,
                                value=value
                            )
                        except (ProductAttribute.DoesNotExist, ProductAttributeValue.DoesNotExist):
                            logger.warning(f"Attribute or value not found: {attribute_id}/{value_id}")
                
                # Create inventory for variant if provided
                if 'shop_inventory' in data:
                    for shop_inv_data in data['shop_inventory']:
                        shop_id = shop_inv_data.get('shop_id')
                        current_stock = shop_inv_data.get('current_stock', 0)
                        
                        try:
                            shop = Shop.objects.get(id=shop_id, business=product.business)
                            
                            Inventory.objects.create(
                                variant=variant,
                                shop=shop,
                                current_stock=current_stock,
                                reserved_stock=0,
                                minimum_stock=shop_inv_data.get('minimum_stock', 0),
                                maximum_stock=shop_inv_data.get('maximum_stock'),
                                is_active=True
                            )
                            
                        except Shop.DoesNotExist:
                            logger.warning(f"Shop {shop_id} not found")
                
                # Get attribute values for response
                variant_attributes = []
                for v_attr in variant.attribute_values.all():
                    variant_attributes.append({
                        'attribute_id': str(v_attr.attribute.id),
                        'attribute_name': v_attr.attribute.name,
                        'value_id': str(v_attr.value.id),
                        'value': v_attr.value.value
                    })
                
                return Response({
                    'success': True,
                    'variant': {
                        'id': str(variant.id),
                        'product_id': str(variant.product.id),
                        'name': variant.name,
                        'sku': variant.sku,
                        'barcode': variant.barcode,
                        'cost_price': float(variant.cost_price) if variant.cost_price else None,
                        'selling_price': float(variant.selling_price) if variant.selling_price else None,
                        'wholesale_price': float(variant.wholesale_price) if variant.wholesale_price else None,
                        'weight': float(variant.weight) if variant.weight else None,
                        'dimensions': variant.dimensions,
                        'is_default': variant.is_default,
                        'is_active': variant.is_active,
                        'attribute_values': variant_attributes,
                        'created_at': variant.created_at.isoformat(),
                        'updated_at': variant.updated_at.isoformat()
                    },
                    'message': 'Variant created successfully'
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"❌ Error creating variant: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class ProductSyncView(APIView):
    """
    Sync product data from mobile app
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            data = request.data
            
            logger.info(f"🔄 Syncing product data for user: {user.username}")
            
            operations = data.get('operations', [])
            synced_items = []
            
            for operation in operations:
                try:
                    op_type = operation.get('type')
                    table = operation.get('table')
                    local_id = operation.get('local_id')
                    item_data = operation.get('data', {})
                    
                    if table == 'products':
                        business_id = item_data.get('business_id')
                        if not business_id:
                            synced_items.append({
                                'table': 'products',
                                'local_id': local_id,
                                'success': False,
                                'error': 'business_id is required'
                            })
                            continue
                        
                        # Verify business ownership
                        try:
                            business = Business.objects.get(id=business_id, owner=user)
                        except Business.DoesNotExist:
                            synced_items.append({
                                'table': 'products',
                                'local_id': local_id,
                                'success': False,
                                'error': 'Business not found or access denied'
                            })
                            continue
                        
                        if op_type == 'create':
                            # Handle category
                            category = None
                            if item_data.get('category_id'):
                                try:
                                    category = Category.objects.get(
                                        id=item_data['category_id'],
                                        business=business
                                    )
                                except Category.DoesNotExist:
                                    pass
                            
                            # Handle tax
                            tax = None
                            if item_data.get('tax_id'):
                                try:
                                    tax = Tax.objects.get(
                                        id=item_data['tax_id'],
                                        is_active=True
                                    )
                                except Tax.DoesNotExist:
                                    pass
                            
                            # Create product
                            product = Product.objects.create(
                                business=business,
                                name=item_data.get('name', ''),
                                description=item_data.get('description', ''),
                                category=category,
                                product_type=item_data.get('product_type', 'physical'),
                                has_variants=item_data.get('has_variants', False),
                                variant_type=item_data.get('variant_type', 'none'),
                                base_barcode=item_data.get('base_barcode', ''),
                                base_sku=item_data.get('base_sku', ''),
                                base_cost_price=item_data.get('base_cost_price'),
                                base_selling_price=item_data.get('base_selling_price'),
                                base_wholesale_price=item_data.get('base_wholesale_price'),
                                tax=tax,
                                tax_inclusive=item_data.get('tax_inclusive', True),
                                unit_of_measure=item_data.get('unit_of_measure', 'pcs'),
                                reorder_level=item_data.get('reorder_level', 10),
                                is_trackable=item_data.get('is_trackable', True),
                                is_active=item_data.get('is_active', True),
                                created_by=user
                            )
                            
                            synced_items.append({
                                'table': 'products',
                                'local_id': local_id,
                                'server_id': str(product.id),
                                'success': True
                            })
                            
                        elif op_type == 'update':
                            product = get_object_or_404(
                                Product, 
                                id=item_data.get('server_id'),
                                business__owner=user
                            )
                            
                            # Update fields
                            update_fields = [
                                'name', 'description', 'product_type', 'has_variants',
                                'variant_type', 'base_barcode', 'base_sku',
                                'base_cost_price', 'base_selling_price', 'base_wholesale_price',
                                'tax_inclusive', 'unit_of_measure', 'reorder_level',
                                'is_trackable', 'is_active'
                            ]
                            
                            for field in update_fields:
                                if field in item_data:
                                    setattr(product, field, item_data[field])
                            
                            # Update category if provided
                            if 'category_id' in item_data:
                                if item_data['category_id']:
                                    try:
                                        category = Category.objects.get(
                                            id=item_data['category_id'],
                                            business=product.business
                                        )
                                        product.category = category
                                    except Category.DoesNotExist:
                                        product.category = None
                                else:
                                    product.category = None
                            
                            # Update tax if provided
                            if 'tax_id' in item_data:
                                if item_data['tax_id']:
                                    try:
                                        tax = Tax.objects.get(
                                            id=item_data['tax_id'],
                                            is_active=True
                                        )
                                        product.tax = tax
                                    except Tax.DoesNotExist:
                                        product.tax = None
                                else:
                                    product.tax = None
                            
                            product.updated_at = timezone.now()
                            product.save()
                            
                            synced_items.append({
                                'table': 'products',
                                'local_id': local_id,
                                'server_id': str(product.id),
                                'success': True
                            })
                            
                        elif op_type == 'delete':
                            product = get_object_or_404(
                                Product, 
                                id=item_data.get('server_id'),
                                business__owner=user
                            )
                            
                            # Soft delete
                            product.is_active = False
                            product.updated_at = timezone.now()
                            product.save()
                            
                            synced_items.append({
                                'table': 'products',
                                'local_id': local_id,
                                'server_id': str(product.id),
                                'success': True
                            })
                    
                    elif table == 'product_variants':
                        # Handle variant sync operations
                        product_id = item_data.get('product_id')
                        if not product_id:
                            synced_items.append({
                                'table': 'product_variants',
                                'local_id': local_id,
                                'success': False,
                                'error': 'product_id is required'
                            })
                            continue
                        
                        # Verify product ownership
                        try:
                            product = Product.objects.get(
                                id=product_id,
                                business__owner=user
                            )
                        except Product.DoesNotExist:
                            synced_items.append({
                                'table': 'product_variants',
                                'local_id': local_id,
                                'success': False,
                                'error': 'Product not found or access denied'
                            })
                            continue
                        
                        if op_type == 'create':
                            # Create variant
                            variant = ProductVariant.objects.create(
                                product=product,
                                name=item_data.get('name', ''),
                                sku=item_data.get('sku', ''),
                                barcode=item_data.get('barcode', ''),
                                cost_price=item_data.get('cost_price'),
                                selling_price=item_data.get('selling_price'),
                                wholesale_price=item_data.get('wholesale_price'),
                                is_active=True,
                                is_default=item_data.get('is_default', False)
                            )
                            
                            synced_items.append({
                                'table': 'product_variants',
                                'local_id': local_id,
                                'server_id': str(variant.id),
                                'success': True
                            })
                            
                        elif op_type == 'update':
                            variant = get_object_or_404(
                                ProductVariant,
                                id=item_data.get('server_id'),
                                product__business__owner=user
                            )
                            
                            # Update variant fields
                            update_fields = [
                                'name', 'sku', 'barcode', 'cost_price',
                                'selling_price', 'wholesale_price', 'is_default', 'is_active'
                            ]
                            
                            for field in update_fields:
                                if field in item_data:
                                    setattr(variant, field, item_data[field])
                            
                            variant.updated_at = timezone.now()
                            variant.save()
                            
                            synced_items.append({
                                'table': 'product_variants',
                                'local_id': local_id,
                                'server_id': str(variant.id),
                                'success': True
                            })
                            
                        elif op_type == 'delete':
                            variant = get_object_or_404(
                                ProductVariant,
                                id=item_data.get('server_id'),
                                product__business__owner=user
                            )
                            
                            # Soft delete
                            variant.is_active = False
                            variant.updated_at = timezone.now()
                            variant.save()
                            
                            synced_items.append({
                                'table': 'product_variants',
                                'local_id': local_id,
                                'server_id': str(variant.id),
                                'success': True
                            })
                    
                    elif table == 'inventory':
                        # Handle inventory sync operations
                        product_id = item_data.get('product_id')
                        variant_id = item_data.get('variant_id')
                        shop_id = item_data.get('shop_id')
                        
                        if not shop_id or (not product_id and not variant_id):
                            synced_items.append({
                                'table': 'inventory',
                                'local_id': local_id,
                                'success': False,
                                'error': 'shop_id and either product_id or variant_id are required'
                            })
                            continue
                        
                        try:
                            shop = Shop.objects.get(id=shop_id, business__owner=user)
                            
                            if product_id:
                                product = Product.objects.get(
                                    id=product_id,
                                    business__owner=user
                                )
                                
                                inventory, created = Inventory.objects.update_or_create(
                                    product=product,
                                    shop=shop,
                                    defaults={
                                        'current_stock': item_data.get('current_stock', 0),
                                        'minimum_stock': item_data.get('minimum_stock', 0),
                                        'updated_at': timezone.now()
                                    }
                                )
                                
                            elif variant_id:
                                variant = ProductVariant.objects.get(
                                    id=variant_id,
                                    product__business__owner=user
                                )
                                
                                inventory, created = Inventory.objects.update_or_create(
                                    variant=variant,
                                    shop=shop,
                                    defaults={
                                        'current_stock': item_data.get('current_stock', 0),
                                        'minimum_stock': item_data.get('minimum_stock', 0),
                                        'updated_at': timezone.now()
                                    }
                                )
                            
                            synced_items.append({
                                'table': 'inventory',
                                'local_id': local_id,
                                'server_id': str(inventory.id),
                                'success': True
                            })
                            
                        except (Product.DoesNotExist, ProductVariant.DoesNotExist, Shop.DoesNotExist):
                            synced_items.append({
                                'table': 'inventory',
                                'local_id': local_id,
                                'success': False,
                                'error': 'Product, variant, or shop not found'
                            })
                    
                except Exception as e:
                    logger.error(f"❌ Error processing operation: {str(e)}")
                    synced_items.append({
                        'table': table,
                        'local_id': local_id,
                        'success': False,
                        'error': str(e)
                    })
            
            return Response({
                'success': True,
                'synced_items': synced_items,
                'message': f'Synced {len([i for i in synced_items if i["success"]])}/{len(operations)} items'
            })
            
        except Exception as e:
            logger.error(f"❌ Product sync error: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        

class ProductDownloadAllView(APIView):
    """
    Download all product-related data for a user's businesses
    Used for initial offline data sync
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            logger.info(f"📦 Downloading all product data for user: {user.username}")

            # Get all businesses the user has access to
            businesses = Business.objects.filter(owner=user, is_active=True)
            
            if not businesses.exists():
                return Response({
                    'success': False,
                    'error': 'No businesses found for this user'
                }, status=status.HTTP_404_NOT_FOUND)

            all_data = {
                'timestamp': timezone.now().isoformat(),
                'user_id': str(user.id),
                'businesses': [],
                'taxes': [],
                'categories': [],
                'products': [],
                'attributes': [],
                'attribute_values': [],
                'variants': [],
                'variant_attributes': [],
                'inventory': [],
                'price_history': [],
                'product_images': []
            }

            # Get global taxes
            taxes = Tax.objects.filter(is_active=True)
            for tax in taxes:
                all_data['taxes'].append({
                    'id': str(tax.id),
                    'name': tax.name,
                    'rate': float(tax.rate),
                    'tax_type': tax.tax_type,
                    'created_at': tax.created_at.isoformat()
                })

            for business in businesses:
                # Get business details
                business_data = {
                    'id': str(business.id),
                    'name': business.name,
                    'owner_id': str(business.owner.id),
                    'shops': []
                }

                # Get shops for this business
                shops = Shop.objects.filter(business=business, is_active=True)
                for shop in shops:
                    business_data['shops'].append({
                        'id': str(shop.id),
                        'name': shop.name,
                        'location': shop.location,
                        'phone_number': shop.phone_number,
                        'tax_rate': float(shop.tax_rate) if shop.tax_rate else 0.0,
                        'currency': shop.currency
                    })

                all_data['businesses'].append(business_data)

                # Get categories for this business
                categories = Category.objects.filter(business=business, is_active=True)
                for category in categories:
                    all_data['categories'].append({
                        'id': str(category.id),
                        'business_id': str(category.business.id),
                        'name': category.name,
                        'description': category.description,
                        'parent_id': str(category.parent.id) if category.parent else None,
                        'color': category.color,
                        'created_at': category.created_at.isoformat(),
                        'updated_at': category.updated_at.isoformat()
                    })

                # Get products for this business
                products = Product.objects.filter(business=business, is_active=True).select_related(
                    'category', 'tax', 'created_by'
                )
                
                for product in products:
                    product_data = {
                        'id': str(product.id),
                        'business_id': str(product.business.id),
                        'name': product.name,
                        'description': product.description,
                        'category_id': str(product.category.id) if product.category else None,
                        'product_type': product.product_type,
                        'has_variants': product.has_variants,
                        'variant_type': product.variant_type,
                        'base_barcode': product.base_barcode,
                        'base_sku': product.base_sku,
                        'base_cost_price': float(product.base_cost_price) if product.base_cost_price else None,
                        'base_selling_price': float(product.base_selling_price) if product.base_selling_price else None,
                        'base_wholesale_price': float(product.base_wholesale_price) if product.base_wholesale_price else None,
                        'tax_id': str(product.tax.id) if product.tax else None,
                        'tax_inclusive': product.tax_inclusive,
                        'unit_of_measure': product.unit_of_measure,
                        'reorder_level': product.reorder_level,
                        'is_trackable': product.is_trackable,
                        'created_by_id': str(product.created_by.id) if product.created_by else None,
                        'created_at': product.created_at.isoformat(),
                        'updated_at': product.updated_at.isoformat()
                    }
                    all_data['products'].append(product_data)

                    # Get product attributes if product has variants
                    if product.has_variants:
                        attributes = ProductAttribute.objects.filter(product=product)
                        for attribute in attributes:
                            all_data['attributes'].append({
                                'id': str(attribute.id),
                                'product_id': str(attribute.product.id),
                                'name': attribute.name,
                                'display_order': attribute.display_order,
                                'is_required': attribute.is_required,
                                'created_at': attribute.created_at.isoformat(),
                                'updated_at': attribute.updated_at.isoformat()
                            })

                            # Get attribute values
                            values = ProductAttributeValue.objects.filter(attribute=attribute)
                            for value in values:
                                all_data['attribute_values'].append({
                                    'id': str(value.id),
                                    'attribute_id': str(value.attribute.id),
                                    'value': value.value,
                                    'display_order': value.display_order,
                                    'created_at': value.created_at.isoformat(),
                                    'updated_at': value.updated_at.isoformat()
                                })

                    # Get product variants
                    variants = ProductVariant.objects.filter(product=product, is_active=True)
                    for variant in variants:
                        variant_data = {
                            'id': str(variant.id),
                            'product_id': str(variant.product.id),
                            'name': variant.name,
                            'sku': variant.sku,
                            'barcode': variant.barcode,
                            'cost_price': float(variant.cost_price) if variant.cost_price else None,
                            'selling_price': float(variant.selling_price) if variant.selling_price else None,
                            'wholesale_price': float(variant.wholesale_price) if variant.wholesale_price else None,
                            'weight': float(variant.weight) if variant.weight else None,
                            'dimensions': variant.dimensions,
                            'is_default': variant.is_default,
                            'created_at': variant.created_at.isoformat(),
                            'updated_at': variant.updated_at.isoformat()
                        }
                        all_data['variants'].append(variant_data)

                        # Get variant attributes
                        variant_attrs = ProductVariantAttribute.objects.filter(variant=variant)
                        for v_attr in variant_attrs:
                            all_data['variant_attributes'].append({
                                'id': str(v_attr.id),
                                'variant_id': str(v_attr.variant.id),
                                'attribute_id': str(v_attr.attribute.id),
                                'value_id': str(v_attr.value.id)
                            })

                    # Get inventory (for simple products and variants)
                    if product.has_variants:
                        # Get inventory for variants
                        variant_inventory = Inventory.objects.filter(
                            variant__product=product,
                            is_active=True
                        ).select_related('shop', 'variant')
                        
                        for inv in variant_inventory:
                            all_data['inventory'].append({
                                'id': str(inv.id),
                                'variant_id': str(inv.variant.id),
                                'shop_id': str(inv.shop.id),
                                'current_stock': inv.current_stock,
                                'reserved_stock': inv.reserved_stock,
                                'minimum_stock': inv.minimum_stock,
                                'maximum_stock': inv.maximum_stock,
                                'last_restocked': inv.last_restocked.isoformat() if inv.last_restocked else None,
                                'created_at': inv.created_at.isoformat(),
                                'updated_at': inv.updated_at.isoformat()
                            })
                    else:
                        # Get inventory for simple product
                        inventory = Inventory.objects.filter(
                            product=product,
                            is_active=True
                        ).select_related('shop')
                        
                        for inv in inventory:
                            all_data['inventory'].append({
                                'id': str(inv.id),
                                'product_id': str(inv.product.id),
                                'shop_id': str(inv.shop.id),
                                'current_stock': inv.current_stock,
                                'reserved_stock': inv.reserved_stock,
                                'minimum_stock': inv.minimum_stock,
                                'maximum_stock': inv.maximum_stock,
                                'last_restocked': inv.last_restocked.isoformat() if inv.last_restocked else None,
                                'created_at': inv.created_at.isoformat(),
                                'updated_at': inv.updated_at.isoformat()
                            })

                    # Get price history
                    price_history = PriceHistory.objects.filter(
                        models.Q(product=product) | models.Q(variant__product=product)
                    ).select_related('changed_by')
                    
                    for history in price_history:
                        history_data = {
                            'id': str(history.id),
                            'product_id': str(history.product.id) if history.product else None,
                            'variant_id': str(history.variant.id) if history.variant else None,
                            'old_price': float(history.old_price),
                            'new_price': float(history.new_price),
                            'price_type': history.price_type,
                            'change_reason': history.change_reason,
                            'changed_by_id': str(history.changed_by.id) if history.changed_by else None,
                            'changed_at': history.changed_at.isoformat()
                        }
                        all_data['price_history'].append(history_data)

                    # Get product images
                    images = ProductImage.objects.filter(
                        models.Q(product=product) | models.Q(variant__product=product)
                    )
                    
                    for image in images:
                        image_data = {
                            'id': str(image.id),
                            'product_id': str(image.product.id) if image.product else None,
                            'variant_id': str(image.variant.id) if image.variant else None,
                            'image_url': request.build_absolute_uri(image.image.url) if image.image else None,
                            'caption': image.caption,
                            'display_order': image.display_order,
                            'is_primary': image.is_primary,
                            'created_at': image.created_at.isoformat(),
                            'updated_at': image.updated_at.isoformat()
                        }
                        all_data['product_images'].append(image_data)

            # Add summary
            summary = {
                'business_count': len(all_data['businesses']),
                'shop_count': sum(len(b['shops']) for b in all_data['businesses']),
                'tax_count': len(all_data['taxes']),
                'category_count': len(all_data['categories']),
                'product_count': len(all_data['products']),
                'variant_count': len(all_data['variants']),
                'inventory_count': len(all_data['inventory']),
                'total_records': sum(len(v) for v in all_data.values() if isinstance(v, list))
            }

            return Response({
                'success': True,
                'data': all_data,
                'summary': summary,
                'message': 'Product data downloaded successfully'
            })

        except Exception as e:
            logger.error(f"❌ Error downloading product data: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class ProductIncrementalSyncView(APIView):
    """
    Incremental sync - only get changes since last sync
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            data = request.data
            
            logger.info(f"🔄 Incremental product sync for user: {user.username}")
            
            last_sync = data.get('last_sync')
            if not last_sync:
                return Response({
                    'success': False,
                    'error': 'last_sync timestamp is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            last_sync_date = timezone.make_aware(
                timezone.datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
            )

            # Get all businesses the user has access to
            businesses = Business.objects.filter(owner=user, is_active=True)
            
            if not businesses.exists():
                return Response({
                    'success': True,
                    'data': {
                        'changes': {},
                        'deletions': {},
                        'timestamp': timezone.now().isoformat()
                    },
                    'message': 'No businesses found'
                })

            changes = {
                'taxes': [],
                'categories': [],
                'products': [],
                'attributes': [],
                'attribute_values': [],
                'variants': [],
                'variant_attributes': [],
                'inventory': [],
                'price_history': [],
                'product_images': []
            }

            deletions = {
                'taxes': [],
                'categories': [],
                'products': [],
                'attributes': [],
                'attribute_values': [],
                'variants': [],
                'variant_attributes': [],
                'inventory': [],
                'price_history': [],
                'product_images': []
            }

            # Get updated taxes
            updated_taxes = Tax.objects.filter(
                is_active=True,
                created_at__gte=last_sync_date
            )
            for tax in updated_taxes:
                changes['taxes'].append(str(tax.id))

            # Get deleted taxes
            deleted_taxes = Tax.objects.filter(
                is_active=False,
                created_at__lt=last_sync_date,
                updated_at__gte=last_sync_date
            )
            for tax in deleted_taxes:
                deletions['taxes'].append(str(tax.id))

            for business in businesses:
                # Get updated categories
                updated_categories = Category.objects.filter(
                    business=business,
                    is_active=True,
                    updated_at__gte=last_sync_date
                )
                for category in updated_categories:
                    changes['categories'].append(str(category.id))

                # Get deleted categories
                deleted_categories = Category.objects.filter(
                    business=business,
                    is_active=False,
                    created_at__lt=last_sync_date,
                    updated_at__gte=last_sync_date
                )
                for category in deleted_categories:
                    deletions['categories'].append(str(category.id))

                # Get updated products
                updated_products = Product.objects.filter(
                    business=business,
                    is_active=True,
                    updated_at__gte=last_sync_date
                )
                for product in updated_products:
                    changes['products'].append(str(product.id))

                # Get deleted products
                deleted_products = Product.objects.filter(
                    business=business,
                    is_active=False,
                    created_at__lt=last_sync_date,
                    updated_at__gte=last_sync_date
                )
                for product in deleted_products:
                    deletions['products'].append(str(product.id))

                # Get updated inventory
                updated_inventory = Inventory.objects.filter(
                    models.Q(product__business=business) | models.Q(variant__product__business=business),
                    is_active=True,
                    updated_at__gte=last_sync_date
                )
                for inv in updated_inventory:
                    changes['inventory'].append(str(inv.id))

                # Get deleted inventory
                deleted_inventory = Inventory.objects.filter(
                    models.Q(product__business=business) | models.Q(variant__product__business=business),
                    is_active=False,
                    created_at__lt=last_sync_date,
                    updated_at__gte=last_sync_date
                )
                for inv in deleted_inventory:
                    deletions['inventory'].append(str(inv.id))

            # Prepare detailed changes for requested items
            requested_changes = data.get('requested_changes', {})
            detailed_changes = {}

            if 'products' in requested_changes and requested_changes['products']:
                product_ids = requested_changes['products']
                products = Product.objects.filter(
                    id__in=product_ids,
                    business__owner=user,
                    is_active=True
                ).select_related('category', 'tax', 'created_by')
                
                detailed_changes['products'] = []
                for product in products:
                    detailed_changes['products'].append({
                        'id': str(product.id),
                        'name': product.name,
                        'description': product.description,
                        'base_selling_price': float(product.base_selling_price) if product.base_selling_price else None,
                        'updated_at': product.updated_at.isoformat()
                    })

            return Response({
                'success': True,
                'data': {
                    'changes': changes,
                    'deletions': deletions,
                    'detailed_changes': detailed_changes,
                    'timestamp': timezone.now().isoformat()
                },
                'message': 'Incremental sync completed'
            })

        except Exception as e:
            logger.error(f"❌ Error in incremental sync: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProductRestockView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        data = request.data
        if not isinstance(data, list):
            return Response({'success': False, 'error': 'Request must be a list'}, status=400)

        results = []
        errors = []
        with transaction.atomic():
            for idx, item in enumerate(data):
                try:
                    quantity = item.get('quantity')
                    if not quantity or int(quantity) <= 0:
                        errors.append({'index': idx, 'error': 'Invalid quantity'})
                        continue

                    shop_id = item.get('shop_id')
                    product_id = item.get('product_id')
                    variant_id = item.get('variant_id')

                    if not shop_id or (not product_id and not variant_id):
                        errors.append({'index': idx, 'error': 'shop_id and either product_id or variant_id required'})
                        continue

                    shop = Shop.objects.get(id=shop_id, business__owner=user)
                    if product_id:
                        product = Product.objects.get(id=product_id, business__owner=user, is_active=True)
                        if product.has_variants:
                            errors.append({'index': idx, 'error': 'Product has variants; specify variant_id'})
                            continue
                        inventory, _ = Inventory.objects.get_or_create(
                            product=product, shop=shop,
                            defaults={'current_stock': 0, 'minimum_stock': product.reorder_level}
                        )
                    else:
                        variant = ProductVariant.objects.get(id=variant_id, product__business__owner=user, is_active=True)
                        inventory, _ = Inventory.objects.get_or_create(
                            variant=variant, shop=shop,
                            defaults={'current_stock': 0, 'minimum_stock': variant.product.reorder_level}
                        )

                    inventory.current_stock += int(quantity)
                    inventory.last_restocked = timezone.now()
                    inventory.last_movement = timezone.now()
                    inventory.save()

                    StockMovement.objects.create(
                        inventory=inventory,
                        shop=shop,
                        product=product_id and inventory.product,
                        variant=variant_id and inventory.variant,
                        movement_type='in',
                        quantity=int(quantity),
                        reference=item.get('reference', ''),
                        reason=f"Restock from {item.get('supplier', 'supplier')}",
                        performed_by=user
                    )

                    results.append({
                        'index': idx,
                        'product_id': str(product_id) if product_id else None,
                        'variant_id': str(variant_id) if variant_id else None,
                        'new_stock': inventory.current_stock
                    })
                except Exception as e:
                    errors.append({'index': idx, 'error': str(e)})

            if errors:
                raise Exception("Rollback due to errors")

        return Response({'success': True, 'results': results})
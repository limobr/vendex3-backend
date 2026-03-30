# sync/views.py - Updated with notifications, messages, configuration, receipt templates
import logging
from decimal import Decimal
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from shops.models import Business, Shop, Employee
from products.models import Product, ProductVariant, Inventory, Category, Tax
from sales.models import Sale, SaleItem, Payment, Customer, ReceiptTemplate
from accounts.models import Permission, Role, Configuration, Notification, Message
from accounts.utils import (
    validate_offline_id,
    notify_sale_completed,
    notify_low_stock,
)

logger = logging.getLogger(__name__)


class FullSyncDownloadView(APIView):
    """
    Download ALL data relevant to the user for initial offline setup.
    Owners get full data; employees get scoped data for their assigned shop.
    Now includes: notifications, messages, configuration, receipt_templates.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            profile = user.profile
            logger.info(f"Full sync download for {user.username} ({profile.user_type})")

            data = {
                'businesses': [],
                'shops': [],
                'employees': [],
                'products': [],
                'categories': [],
                'taxes': [],
                'inventory': [],
                'customers': [],
                'sales': [],
                'permissions': [],
                'roles': [],
                'configurations': [],
                'notifications': [],
                'messages': [],
                'receipt_templates': [],
            }

            # ── Global data ──
            data['taxes'] = list(Tax.objects.filter(is_active=True).values(
                'id', 'name', 'rate', 'tax_type', 'created_at'
            ))
            for t in data['taxes']:
                t['id'] = str(t['id'])
                t['rate'] = float(t['rate'])

            data['permissions'] = list(Permission.objects.filter(is_active=True).values(
                'id', 'code', 'name', 'description', 'category'
            ))
            for p in data['permissions']:
                p['id'] = str(p['id'])

            for role in Role.objects.all().prefetch_related('permissions'):
                data['roles'].append({
                    'id': str(role.id), 'name': role.name, 'role_type': role.role_type,
                    'description': role.description, 'is_default': role.is_default,
                    'permission_ids': [str(p.id) for p in role.permissions.all()],
                })

            # ── Determine accessible businesses ──
            if profile.user_type == 'owner':
                businesses = Business.objects.filter(owner=user, is_active=True)
            else:
                emp_businesses = Employee.objects.filter(
                    user=user, is_active=True
                ).values_list('shop__business', flat=True).distinct()
                businesses = Business.objects.filter(id__in=emp_businesses, is_active=True)

            for biz in businesses:
                data['businesses'].append({
                    'id': str(biz.id), 'name': biz.name, 'owner_id': biz.owner_id,
                    'registration_number': biz.registration_number,
                    'phone_number': biz.phone_number, 'email': biz.email,
                    'address': biz.address, 'is_active': biz.is_active,
                    'created_at': biz.created_at.isoformat(),
                })

                # ── Configuration ──
                try:
                    cfg = biz.configuration
                    data['configurations'].append({
                        'id': str(cfg.id), 'business_id': str(biz.id),
                        'primary_color': cfg.primary_color, 'secondary_color': cfg.secondary_color,
                        'accent_color': cfg.accent_color, 'theme_mode': cfg.theme_mode,
                        'operation_mode': cfg.operation_mode,
                        'default_printer_width': cfg.default_printer_width,
                        'currency_symbol': cfg.currency_symbol,
                        'date_format': cfg.date_format, 'time_format': cfg.time_format,
                        'extra_settings': cfg.extra_settings,
                        'updated_at': cfg.updated_at.isoformat(),
                    })
                except Configuration.DoesNotExist:
                    pass

                # ── Shops ──
                if profile.user_type == 'owner':
                    shops = Shop.objects.filter(business=biz, is_active=True)
                else:
                    emp_shop_ids = Employee.objects.filter(
                        user=user, shop__business=biz, is_active=True
                    ).values_list('shop_id', flat=True)
                    shops = Shop.objects.filter(id__in=emp_shop_ids, is_active=True)

                for shop in shops:
                    data['shops'].append({
                        'id': str(shop.id), 'business_id': str(shop.business_id),
                        'name': shop.name, 'shop_type': shop.shop_type,
                        'location': shop.location, 'phone_number': shop.phone_number,
                        'email': shop.email, 'tax_rate': float(shop.tax_rate),
                        'currency': shop.currency, 'is_active': shop.is_active,
                        'created_at': shop.created_at.isoformat(),
                    })

                    # ── Receipt template ──
                    try:
                        tpl = shop.receipt_template
                        logo_url = None
                        if tpl.logo:
                            logo_url = request.build_absolute_uri(tpl.logo.url)
                        data['receipt_templates'].append({
                            'id': str(tpl.id), 'shop_id': str(shop.id),
                            'header_text': tpl.header_text, 'footer_text': tpl.footer_text,
                            'logo': logo_url, 'layout': tpl.layout,
                            'show_logo': tpl.show_logo, 'show_shop_address': tpl.show_shop_address,
                            'show_shop_phone': tpl.show_shop_phone,
                            'show_attendant_name': tpl.show_attendant_name,
                            'show_customer_name': tpl.show_customer_name,
                            'show_tax_breakdown': tpl.show_tax_breakdown,
                            'show_payment_method': tpl.show_payment_method,
                            'printer_width': tpl.printer_width,
                            'custom_fields': tpl.custom_fields,
                            'updated_at': tpl.updated_at.isoformat(),
                        })
                    except ReceiptTemplate.DoesNotExist:
                        pass

                # ── Employees ──
                emps = Employee.objects.filter(
                    shop__business=biz, is_active=True
                ).select_related('user', 'role', 'shop', 'user__profile')
                for emp in emps:
                    pic_url = None
                    if hasattr(emp.user, 'profile') and emp.user.profile.profile_picture:
                        pic_url = request.build_absolute_uri(emp.user.profile.profile_picture.url)
                    data['employees'].append({
                        'id': str(emp.id), 'user_id': emp.user_id,
                        'shop_id': str(emp.shop_id), 'business_id': str(biz.id),
                        'role_id': str(emp.role_id) if emp.role else None,
                        'first_name': emp.user.first_name, 'last_name': emp.user.last_name,
                        'email': emp.user.email,
                        'phone_number': emp.user.profile.phone_number if hasattr(emp.user, 'profile') else None,
                        'profile_picture': pic_url,
                        'employment_type': emp.employment_type,
                        'salary': float(emp.salary) if emp.salary else None,
                        'is_active': emp.is_active,
                        'is_invite_accepted': emp.is_invite_accepted,
                        'custom_permission_ids': [str(p.id) for p in emp.custom_permissions.all()],
                        'created_at': emp.created_at.isoformat(),
                    })

                # ── Categories ──
                for cat in Category.objects.filter(business=biz, is_active=True):
                    data['categories'].append({
                        'id': str(cat.id), 'business_id': str(cat.business_id),
                        'name': cat.name, 'description': cat.description or '',
                        'parent_id': str(cat.parent_id) if cat.parent_id else None,
                        'color': cat.color, 'created_at': cat.created_at.isoformat(),
                    })

                # ── Products ──
                for prod in Product.objects.filter(business=biz, is_active=True).select_related('category', 'tax'):
                    data['products'].append({
                        'id': str(prod.id), 'business_id': str(prod.business_id),
                        'name': prod.name, 'description': prod.description or '',
                        'category_id': str(prod.category_id) if prod.category_id else None,
                        'product_type': prod.product_type,
                        'has_variants': prod.has_variants, 'variant_type': prod.variant_type,
                        'base_barcode': prod.base_barcode, 'base_sku': prod.base_sku,
                        'base_cost_price': float(prod.base_cost_price) if prod.base_cost_price else None,
                        'base_selling_price': float(prod.base_selling_price) if prod.base_selling_price else None,
                        'base_wholesale_price': float(prod.base_wholesale_price) if prod.base_wholesale_price else None,
                        'tax_id': str(prod.tax_id) if prod.tax_id else None,
                        'tax_inclusive': prod.tax_inclusive,
                        'unit_of_measure': prod.unit_of_measure,
                        'reorder_level': prod.reorder_level,
                        'is_trackable': prod.is_trackable,
                        'created_at': prod.created_at.isoformat(),
                        'updated_at': prod.updated_at.isoformat(),
                    })

                # ── Inventory ──
                shop_ids = [s['id'] for s in data['shops']]
                for inv in Inventory.objects.filter(shop_id__in=shop_ids, is_active=True).select_related('product', 'variant'):
                    data['inventory'].append({
                        'id': str(inv.id),
                        'product_id': str(inv.product_id) if inv.product_id else None,
                        'variant_id': str(inv.variant_id) if inv.variant_id else None,
                        'shop_id': str(inv.shop_id),
                        'current_stock': inv.current_stock,
                        'reserved_stock': inv.reserved_stock,
                        'minimum_stock': inv.minimum_stock,
                        'maximum_stock': inv.maximum_stock,
                        'updated_at': inv.updated_at.isoformat(),
                    })

                # ── Customers ──
                for c in Customer.objects.filter(business=biz, is_active=True):
                    data['customers'].append({
                        'id': str(c.id), 'business_id': str(c.business_id),
                        'name': c.name, 'phone_number': c.phone_number,
                        'email': c.email, 'loyalty_points': c.loyalty_points,
                        'total_spent': float(c.total_spent),
                        'created_at': c.created_at.isoformat(),
                    })

            # ── Notifications (user-specific, last 100) ──
            notifs = Notification.objects.filter(
                Q(recipient=user) |
                Q(recipient_role=profile.user_type) |
                Q(recipient_role='all')
            ).order_by('-created_at')[:100]
            for n in notifs:
                data['notifications'].append({
                    'id': str(n.id), 'title': n.title, 'message': n.message,
                    'notification_type': n.notification_type, 'category': n.category,
                    'is_read': n.is_read,
                    'related_object_type': n.related_object_type,
                    'related_object_id': str(n.related_object_id) if n.related_object_id else None,
                    'created_at': n.created_at.isoformat(),
                })

            # ── Messages (user-specific, last 100 inbox) ──
            msgs = Message.objects.filter(
                Q(recipient=user) | Q(sender=user)
            ).select_related('sender', 'recipient', 'business').order_by('-created_at')[:100]
            for m in msgs:
                data['messages'].append({
                    'id': str(m.id),
                    'sender_id': m.sender_id,
                    'sender_name': m.sender.get_full_name() or m.sender.username,
                    'recipient_id': m.recipient_id,
                    'recipient_name': m.recipient.get_full_name() or m.recipient.username,
                    'business_id': str(m.business_id),
                    'message': m.message, 'is_read': m.is_read,
                    'created_at': m.created_at.isoformat(),
                })

            return Response({
                'success': True, 'data': data,
                'sync_timestamp': timezone.now().isoformat(),
                'summary': {k: len(v) for k, v in data.items()},
            })

        except Exception as e:
            logger.error(f"Full sync error: {str(e)}", exc_info=True)
            return Response({'success': False, 'error': str(e)}, status=500)


class PushSyncView(APIView):
    """
    Push local offline changes to server.
    Handles pending sales, inventory updates, customer changes.
    Uses offline_id for idempotency with UUID validation.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            operations = request.data.get('operations', [])
            results = []

            logger.info(f"Push sync: {len(operations)} operations from {user.username}")

            for op in operations:
                try:
                    op_type = op.get('type')
                    data = op.get('data', {})
                    local_id = op.get('local_id')

                    # Validate offline IDs
                    for id_field in ['offline_id', 'product_id', 'variant_id', 'shop_id', 'customer_id']:
                        val = data.get(id_field)
                        if val:
                            is_valid, _, err = validate_offline_id(val)
                            if not is_valid:
                                results.append({
                                    'success': False, 'local_id': local_id,
                                    'type': op_type, 'error': err,
                                })
                                continue

                    if op_type == 'sale':
                        result = self._sync_sale(user, data, local_id)
                    elif op_type == 'customer':
                        result = self._sync_customer(user, data, local_id)
                    elif op_type == 'inventory_update':
                        result = self._sync_inventory(user, data, local_id)
                    else:
                        result = {'success': False, 'error': f'Unknown type: {op_type}', 'local_id': local_id}

                    results.append(result)

                except Exception as e:
                    logger.error(f"Sync op error: {str(e)}")
                    results.append({
                        'success': False, 'local_id': op.get('local_id'),
                        'type': op.get('type'), 'error': str(e),
                    })

            success_count = sum(1 for r in results if r.get('success'))
            return Response({
                'success': True, 'results': results,
                'message': f'Synced {success_count}/{len(operations)} operations',
                'sync_timestamp': timezone.now().isoformat(),
            })

        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=400)

    def _sync_sale(self, user, data, local_id):
        """Sync a pending sale from offline"""
        offline_id = data.get('offline_id') or local_id

        # UUID validation
        is_valid, cleaned_id, err = validate_offline_id(offline_id)
        if not is_valid:
            return {'success': False, 'local_id': local_id, 'type': 'sale', 'error': err}
        offline_id = cleaned_id or offline_id

        # Idempotency
        existing = Sale.objects.filter(offline_id=offline_id).first()
        if existing:
            return {
                'success': True, 'local_id': local_id,
                'server_id': str(existing.id), 'type': 'sale',
                'message': 'Already synced',
            }

        shop = get_object_or_404(Shop, id=data['shop_id'], is_active=True)

        try:
            attendant = Employee.objects.get(user=user, shop=shop, is_active=True)
        except Employee.DoesNotExist:
            if shop.business.owner == user:
                attendant = Employee.objects.filter(shop=shop, is_active=True).first()
            else:
                return {'success': False, 'local_id': local_id, 'type': 'sale', 'error': 'Not authorized'}

        if not attendant:
            return {'success': False, 'local_id': local_id, 'type': 'sale', 'error': 'No attendant found'}

        with transaction.atomic():
            customer = None
            if data.get('customer_id'):
                customer = Customer.objects.filter(id=data['customer_id']).first()

            sale = Sale.objects.create(
                receipt_number=data.get('receipt_number', generate_receipt_number_static(shop)),
                offline_id=offline_id, shop=shop, attendant=attendant,
                customer=customer,
                subtotal=Decimal(str(data.get('subtotal', 0))),
                tax_amount=Decimal(str(data.get('tax_amount', 0))),
                discount_amount=Decimal(str(data.get('discount_amount', 0))),
                total_amount=Decimal(str(data.get('total_amount', 0))),
                amount_paid=Decimal(str(data.get('amount_paid', 0))),
                change_given=Decimal(str(data.get('change_given', 0))),
                status=data.get('status', 'completed'),
                sync_status='synced', is_offline=True,
                completed_at=timezone.now(),
            )

            for item_data in data.get('items', []):
                product = Product.objects.get(id=item_data['product_id'])
                SaleItem.objects.create(
                    sale=sale, product=product,
                    quantity=Decimal(str(item_data.get('quantity', 1))),
                    unit_price=Decimal(str(item_data.get('unit_price', 0))),
                    total_price=Decimal(str(item_data.get('total_price', 0))),
                    tax_amount=Decimal(str(item_data.get('tax_amount', 0))),
                    discount_amount=Decimal(str(item_data.get('discount_amount', 0))),
                    stock_deducted=True,
                )

                # Deduct stock on server
                if product.is_trackable:
                    try:
                        inv = Inventory.objects.get(product=product, shop=shop)
                        inv.current_stock -= int(item_data.get('quantity', 1))
                        inv.save()
                        # Check low stock
                        if inv.current_stock <= inv.minimum_stock:
                            notify_low_stock(inv)
                    except Inventory.DoesNotExist:
                        pass

            for pay_data in data.get('payments', []):
                Payment.objects.create(
                    sale=sale, method=pay_data.get('method', 'cash'),
                    amount=Decimal(str(pay_data.get('amount', 0))),
                    transaction_code=pay_data.get('transaction_code', ''),
                    status='completed',
                )

            # Notify owner
            if sale.status == 'completed':
                notify_sale_completed(sale)

        return {
            'success': True, 'local_id': local_id,
            'server_id': str(sale.id), 'type': 'sale',
            'receipt_number': sale.receipt_number,
        }

    def _sync_customer(self, user, data, local_id):
        """Sync a customer"""
        business = get_object_or_404(Business, id=data['business_id'])
        phone = data.get('phone_number')

        if phone:
            existing = Customer.objects.filter(business=business, phone_number=phone).first()
            if existing:
                return {
                    'success': True, 'local_id': local_id,
                    'server_id': str(existing.id), 'type': 'customer',
                }

        customer = Customer.objects.create(
            business=business, name=data.get('name', 'Walk-in'),
            phone_number=phone, email=data.get('email', ''),
            address=data.get('address', ''),
        )
        return {
            'success': True, 'local_id': local_id,
            'server_id': str(customer.id), 'type': 'customer',
        }

    def _sync_inventory(self, user, data, local_id):
        """Sync inventory adjustment"""
        shop = get_object_or_404(Shop, id=data['shop_id'])
        product_id = data.get('product_id')
        variant_id = data.get('variant_id')

        if product_id:
            inv = Inventory.objects.get(product_id=product_id, shop=shop)
        elif variant_id:
            inv = Inventory.objects.get(variant_id=variant_id, shop=shop)
        else:
            return {'success': False, 'local_id': local_id, 'error': 'No product/variant id'}

        adjustment = int(data.get('adjustment', 0))
        if data.get('set_absolute'):
            inv.current_stock = int(data['current_stock'])
        else:
            inv.current_stock += adjustment
        inv.save()

        # Check low stock
        if inv.current_stock <= inv.minimum_stock:
            notify_low_stock(inv)

        return {
            'success': True, 'local_id': local_id,
            'server_id': str(inv.id), 'type': 'inventory_update',
            'current_stock': inv.current_stock,
        }


class IncrementalSyncView(APIView):
    """Pull only changes since last sync timestamp"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            profile = user.profile
            last_sync = request.data.get('last_sync')
            if not last_sync:
                return Response({'success': False, 'error': 'last_sync required'}, status=400)

            changes = {
                'products': [], 'inventory': [], 'categories': [],
                'customers': [], 'employees': [],
                'notifications': [], 'messages': [],
                'configurations': [],
            }

            businesses = Business.objects.filter(owner=user, is_active=True)

            # Products changed since last sync
            for p in Product.objects.filter(business__in=businesses, updated_at__gte=last_sync, is_active=True):
                changes['products'].append({
                    'id': str(p.id), 'name': p.name,
                    'base_selling_price': float(p.base_selling_price) if p.base_selling_price else None,
                    'base_cost_price': float(p.base_cost_price) if p.base_cost_price else None,
                    'is_active': p.is_active, 'updated_at': p.updated_at.isoformat(),
                })

            # Inventory changes
            for inv in Inventory.objects.filter(
                shop__business__in=businesses, updated_at__gte=last_sync, is_active=True
            ):
                changes['inventory'].append({
                    'id': str(inv.id),
                    'product_id': str(inv.product_id) if inv.product_id else None,
                    'variant_id': str(inv.variant_id) if inv.variant_id else None,
                    'shop_id': str(inv.shop_id),
                    'current_stock': inv.current_stock,
                    'updated_at': inv.updated_at.isoformat(),
                })

            # Customers
            for c in Customer.objects.filter(business__in=businesses, updated_at__gte=last_sync):
                changes['customers'].append({
                    'id': str(c.id), 'name': c.name, 'phone_number': c.phone_number,
                    'loyalty_points': c.loyalty_points, 'total_spent': float(c.total_spent),
                })

            # New notifications since last sync
            notifs = Notification.objects.filter(
                Q(recipient=user) |
                Q(recipient_role=profile.user_type) |
                Q(recipient_role='all'),
                created_at__gte=last_sync,
            )
            for n in notifs:
                changes['notifications'].append({
                    'id': str(n.id), 'title': n.title, 'message': n.message,
                    'notification_type': n.notification_type, 'category': n.category,
                    'is_read': n.is_read, 'created_at': n.created_at.isoformat(),
                })

            # New messages since last sync
            msgs = Message.objects.filter(
                Q(recipient=user) | Q(sender=user),
                created_at__gte=last_sync,
            ).select_related('sender', 'recipient')
            for m in msgs:
                changes['messages'].append({
                    'id': str(m.id),
                    'sender_id': m.sender_id,
                    'sender_name': m.sender.get_full_name() or m.sender.username,
                    'recipient_id': m.recipient_id,
                    'message': m.message, 'is_read': m.is_read,
                    'created_at': m.created_at.isoformat(),
                })

            # Configuration changes
            for cfg in Configuration.objects.filter(
                business__in=businesses, updated_at__gte=last_sync
            ):
                changes['configurations'].append({
                    'id': str(cfg.id), 'business_id': str(cfg.business_id),
                    'primary_color': cfg.primary_color, 'secondary_color': cfg.secondary_color,
                    'accent_color': cfg.accent_color, 'theme_mode': cfg.theme_mode,
                    'operation_mode': cfg.operation_mode,
                    'updated_at': cfg.updated_at.isoformat(),
                })

            return Response({
                'success': True, 'changes': changes,
                'sync_timestamp': timezone.now().isoformat(),
                'summary': {k: len(v) for k, v in changes.items()},
            })

        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=500)


def generate_receipt_number_static(shop):
    """Static version for use outside views"""
    today = timezone.now().strftime('%Y%m%d')
    prefix = shop.name[:3].upper().replace(' ', '')
    count = Sale.objects.filter(shop=shop, sale_date__date=timezone.now().date()).count() + 1
    return f"{prefix}-{today}-{count:04d}"

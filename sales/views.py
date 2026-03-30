# sales/views.py - Complete implementation
import logging
import uuid
from decimal import Decimal
from django.db import transaction, models
from django.db.models import Sum, Count, Avg, F, Q
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from shops.models import Business, Shop, Employee
from products.models import Product, ProductVariant, Inventory
from .models import Sale, SaleItem, Payment, Customer
from accounts.utils import notify_sale_completed, notify_low_stock, validate_offline_id

logger = logging.getLogger(__name__)


def generate_receipt_number(shop):
    today = timezone.now().strftime('%Y%m%d')
    prefix = shop.name[:3].upper().replace(' ', '')
    count = Sale.objects.filter(shop=shop, sale_date__date=timezone.now().date()).count() + 1
    return f"{prefix}-{today}-{count:04d}"


class SaleCreateView(APIView):
    """Create a sale / process checkout with stock validation, payment, loyalty."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            data = request.data
            logger.info(f"Sale creation by {user.username}")

            # Idempotency check
            offline_id = data.get('offline_id')
            if offline_id:
                # Validate offline_id is a proper UUID
                is_valid, cleaned_id, err = validate_offline_id(offline_id)
                if not is_valid:
                    return Response({'success': False, 'error': err}, status=400)
                offline_id = cleaned_id

                existing = Sale.objects.filter(offline_id=offline_id).first()
                if existing:
                    return Response({
                        'success': True, 'sale': self._serialize_sale(existing),
                        'message': 'Sale already exists (idempotent)', 'duplicate': True,
                    })

            shop_id = data.get('shop_id')
            items = data.get('items', [])
            payments = data.get('payments', [])

            if not shop_id:
                return Response({'success': False, 'error': 'shop_id is required'}, status=400)
            if not items:
                return Response({'success': False, 'error': 'At least one item is required'}, status=400)

            shop = get_object_or_404(Shop, id=shop_id, is_active=True)

            # Resolve attendant
            try:
                attendant = Employee.objects.get(user=user, shop=shop, is_active=True)
            except Employee.DoesNotExist:
                if shop.business.owner == user:
                    attendant = Employee.objects.filter(shop=shop, is_active=True).first()
                    if not attendant:
                        return Response({'success': False, 'error': 'No active employee for this shop'}, status=400)
                else:
                    return Response({'success': False, 'error': 'You are not assigned to this shop'}, status=403)

            with transaction.atomic():
                sale_items_data = []
                subtotal = Decimal('0')
                total_tax = Decimal('0')
                total_discount = Decimal('0')

                for item_data in items:
                    product_id = item_data.get('product_id')
                    variant_id = item_data.get('variant_id')
                    quantity = Decimal(str(item_data.get('quantity', 1)))
                    unit_price = Decimal(str(item_data.get('unit_price', 0)))
                    discount = Decimal(str(item_data.get('discount_amount', 0)))

                    product = get_object_or_404(Product, id=product_id, is_active=True)

                    # Stock validation
                    variant = None
                    inv = None
                    if product.is_trackable:
                        if variant_id:
                            variant = get_object_or_404(ProductVariant, id=variant_id, is_active=True)
                            try:
                                inv = Inventory.objects.select_for_update().get(variant=variant, shop=shop, is_active=True)
                            except Inventory.DoesNotExist:
                                return Response({'success': False, 'error': f'No inventory for variant {variant.name}'}, status=400)
                        else:
                            try:
                                inv = Inventory.objects.select_for_update().get(product=product, shop=shop, is_active=True)
                            except Inventory.DoesNotExist:
                                return Response({'success': False, 'error': f'No inventory for {product.name}'}, status=400)

                        available = inv.current_stock - inv.reserved_stock
                        if quantity > available:
                            return Response({
                                'success': False,
                                'error': f'Insufficient stock for {product.name}. Available: {available}'
                            }, status=400)

                    # Tax calculation
                    item_tax = Decimal('0')
                    if product.tax:
                        rate = Decimal(str(product.tax.rate)) / Decimal('100')
                        if product.tax_inclusive:
                            item_tax = (unit_price * quantity) - ((unit_price * quantity) / (1 + rate))
                        else:
                            item_tax = unit_price * quantity * rate

                    line_total = unit_price * quantity - discount
                    subtotal += line_total
                    total_tax += item_tax
                    total_discount += discount

                    sale_items_data.append({
                        'product': product, 'variant': variant, 'inv': inv,
                        'quantity': quantity, 'unit_price': unit_price,
                        'total_price': line_total, 'tax_amount': item_tax,
                        'discount_amount': discount,
                    })

                total_amount = subtotal
                amount_paid = Decimal(str(data.get('amount_paid', total_amount)))
                change_given = max(amount_paid - total_amount, Decimal('0'))

                # Resolve customer
                customer = None
                customer_id = data.get('customer_id')
                if customer_id:
                    customer = Customer.objects.filter(id=customer_id, is_active=True).first()
                elif data.get('customer_name'):
                    phone = data.get('customer_phone')
                    if phone:
                        customer, _ = Customer.objects.get_or_create(
                            business=shop.business, phone_number=phone,
                            defaults={'name': data.get('customer_name', 'Walk-in')}
                        )
                    else:
                        customer = Customer.objects.create(
                            business=shop.business, name=data.get('customer_name', 'Walk-in')
                        )

                receipt_number = data.get('receipt_number') or generate_receipt_number(shop)
                sale = Sale.objects.create(
                    receipt_number=receipt_number, offline_id=offline_id, shop=shop,
                    attendant=attendant, customer=customer, subtotal=subtotal,
                    tax_amount=total_tax, discount_amount=total_discount,
                    total_amount=total_amount, amount_paid=amount_paid,
                    change_given=change_given, status=data.get('status', 'completed'),
                    sync_status='synced', is_offline=data.get('is_offline', False),
                    completed_at=timezone.now() if data.get('status', 'completed') == 'completed' else None,
                )

                # Create items and deduct stock
                for item in sale_items_data:
                    SaleItem.objects.create(
                        sale=sale, product=item['product'], quantity=item['quantity'],
                        unit_price=item['unit_price'], total_price=item['total_price'],
                        tax_amount=item['tax_amount'], discount_amount=item['discount_amount'],
                        stock_deducted=item['product'].is_trackable,
                    )
                    if item['product'].is_trackable and item['inv']:
                        item['inv'].current_stock -= int(item['quantity'])
                        item['inv'].save()

                # Create payments
                for pay in payments:
                    Payment.objects.create(
                        sale=sale, method=pay.get('method', 'cash'),
                        amount=Decimal(str(pay.get('amount', 0))),
                        transaction_code=pay.get('transaction_code', ''),
                        phone_number=pay.get('phone_number', ''),
                        card_last_four=pay.get('card_last_four', ''),
                        bank_name=pay.get('bank_name', ''),
                        status='completed', notes=pay.get('notes', ''),
                    )

                # Update customer loyalty
                points_earned = 0
                if customer:
                    customer.total_spent += total_amount
                    points_earned = int(total_amount / Decimal('100'))
                    customer.loyalty_points += points_earned
                    customer.save()

                # ── Notifications ──
                if sale.status == 'completed':
                    notify_sale_completed(sale)

                # Check for low stock alerts
                for item in sale_items_data:
                    if item['product'].is_trackable and item['inv']:
                        inv = item['inv']
                        if inv.current_stock <= inv.minimum_stock:
                            notify_low_stock(inv)

                return Response({
                    'success': True, 'sale': self._serialize_sale(sale),
                    'points_earned': points_earned, 'message': 'Sale created successfully',
                }, status=201)

        except Exception as e:
            logger.error(f"Error creating sale: {str(e)}", exc_info=True)
            return Response({'success': False, 'error': str(e)}, status=400)

    def _serialize_sale(self, sale):
        items = [{
            'id': str(i.id), 'product_id': str(i.product_id), 'product_name': i.product.name,
            'quantity': float(i.quantity), 'unit_price': float(i.unit_price),
            'total_price': float(i.total_price), 'tax_amount': float(i.tax_amount),
            'discount_amount': float(i.discount_amount),
        } for i in sale.items.all().select_related('product')]

        payments = [{
            'id': str(p.id), 'method': p.method, 'amount': float(p.amount),
            'transaction_code': p.transaction_code, 'status': p.status,
        } for p in sale.payments.all()]

        return {
            'id': str(sale.id), 'receipt_number': sale.receipt_number,
            'offline_id': sale.offline_id, 'shop_id': str(sale.shop_id),
            'shop_name': sale.shop.name,
            'attendant_id': str(sale.attendant_id),
            'customer_id': str(sale.customer_id) if sale.customer_id else None,
            'customer_name': sale.customer.name if sale.customer else 'Walk-in',
            'subtotal': float(sale.subtotal), 'tax_amount': float(sale.tax_amount),
            'discount_amount': float(sale.discount_amount), 'total_amount': float(sale.total_amount),
            'amount_paid': float(sale.amount_paid), 'change_given': float(sale.change_given),
            'status': sale.status, 'sync_status': sale.sync_status,
            'is_offline': sale.is_offline, 'items': items, 'payments': payments,
            'sale_date': sale.sale_date.isoformat(),
            'completed_at': sale.completed_at.isoformat() if sale.completed_at else None,
            'created_at': sale.created_at.isoformat(),
        }


class SaleListView(APIView):
    """List sales with filtering, pagination, and search"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            shop_id = request.query_params.get('shop_id')
            business_id = request.query_params.get('business_id')
            date_from = request.query_params.get('date_from')
            date_to = request.query_params.get('date_to')
            sale_status = request.query_params.get('status')
            payment_method = request.query_params.get('payment_method')
            search = request.query_params.get('search', '')
            employee_only = request.query_params.get('employee_only', 'false').lower() == 'true'
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 20))

            q = Sale.objects.all()
            if shop_id:
                q = q.filter(shop_id=shop_id)
            elif business_id:
                q = q.filter(shop__business_id=business_id)
            else:
                owned = Business.objects.filter(owner=user, is_active=True)
                q = q.filter(shop__business__in=owned)

            if employee_only:
                emp_ids = Employee.objects.filter(user=user, is_active=True).values_list('id', flat=True)
                q = q.filter(attendant_id__in=emp_ids)
            if date_from:
                q = q.filter(sale_date__date__gte=date_from)
            if date_to:
                q = q.filter(sale_date__date__lte=date_to)
            if sale_status:
                q = q.filter(status=sale_status)
            if payment_method:
                q = q.filter(payments__method=payment_method).distinct()
            if search:
                q = q.filter(Q(receipt_number__icontains=search) | Q(customer__name__icontains=search))

            total = q.count()
            sales = q.order_by('-sale_date').select_related(
                'shop', 'attendant__user', 'customer'
            )[(page-1)*page_size : page*page_size]

            sales_list = [{
                'id': str(s.id), 'receipt_number': s.receipt_number,
                'shop_name': s.shop.name,
                'attendant_name': s.attendant.user.get_full_name() or s.attendant.user.username,
                'customer_name': s.customer.name if s.customer else 'Walk-in',
                'total_amount': float(s.total_amount), 'status': s.status,
                'payment_methods': list(s.payments.values_list('method', flat=True)),
                'item_count': s.items.count(), 'sale_date': s.sale_date.isoformat(),
                'sync_status': s.sync_status,
            } for s in sales]

            agg = q.aggregate(
                total_revenue=Sum('total_amount'), total_tax=Sum('tax_amount'),
                total_discount=Sum('discount_amount'), avg_sale=Avg('total_amount'),
            )

            return Response({
                'success': True, 'sales': sales_list,
                'pagination': {
                    'total': total, 'page': page, 'page_size': page_size,
                    'total_pages': (total + page_size - 1) // page_size,
                },
                'summary': {
                    'total_revenue': float(agg['total_revenue'] or 0),
                    'total_tax': float(agg['total_tax'] or 0),
                    'total_discount': float(agg['total_discount'] or 0),
                    'average_sale': float(agg['avg_sale'] or 0),
                    'sale_count': total,
                },
            })
        except Exception as e:
            logger.error(f"Error listing sales: {str(e)}", exc_info=True)
            return Response({'success': False, 'error': str(e)}, status=400)


class SaleDetailView(APIView):
    """Get full sale detail"""
    permission_classes = [IsAuthenticated]

    def get(self, request, sale_id):
        try:
            sale = get_object_or_404(Sale, id=sale_id)
            if sale.shop.business.owner != request.user:
                emp = Employee.objects.filter(user=request.user, shop=sale.shop, is_active=True).first()
                if not emp:
                    return Response({'success': False, 'error': 'Access denied'}, status=403)

            items = [{
                'id': str(i.id), 'product_id': str(i.product_id), 'product_name': i.product.name,
                'quantity': float(i.quantity), 'unit_price': float(i.unit_price),
                'total_price': float(i.total_price), 'tax_amount': float(i.tax_amount),
                'discount_amount': float(i.discount_amount),
            } for i in sale.items.all().select_related('product')]

            payments = [{
                'id': str(p.id), 'method': p.method, 'amount': float(p.amount),
                'transaction_code': p.transaction_code, 'phone_number': p.phone_number,
                'card_last_four': p.card_last_four, 'status': p.status,
                'created_at': p.created_at.isoformat(),
            } for p in sale.payments.all()]

            return Response({
                'success': True,
                'sale': {
                    'id': str(sale.id), 'receipt_number': sale.receipt_number,
                    'offline_id': sale.offline_id,
                    'shop_id': str(sale.shop_id), 'shop_name': sale.shop.name,
                    'business_name': sale.shop.business.name,
                    'attendant_name': sale.attendant.user.get_full_name() or sale.attendant.user.username,
                    'customer': {
                        'id': str(sale.customer.id), 'name': sale.customer.name,
                        'phone': sale.customer.phone_number,
                        'loyalty_points': sale.customer.loyalty_points,
                    } if sale.customer else None,
                    'subtotal': float(sale.subtotal), 'tax_amount': float(sale.tax_amount),
                    'discount_amount': float(sale.discount_amount),
                    'total_amount': float(sale.total_amount),
                    'amount_paid': float(sale.amount_paid),
                    'change_given': float(sale.change_given),
                    'status': sale.status, 'items': items, 'payments': payments,
                    'sale_date': sale.sale_date.isoformat(),
                    'completed_at': sale.completed_at.isoformat() if sale.completed_at else None,
                },
            })
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=400)


class SaleRefundView(APIView):
    """Process full or partial refund"""
    permission_classes = [IsAuthenticated]

    def post(self, request, sale_id):
        try:
            sale = get_object_or_404(Sale, id=sale_id, status='completed')
            if sale.shop.business.owner != request.user:
                return Response({'success': False, 'error': 'Only owners can process refunds'}, status=403)

            data = request.data
            with transaction.atomic():
                total_refund = Decimal('0')
                for ref_item in data.get('items', []):
                    si = SaleItem.objects.get(id=ref_item['sale_item_id'], sale=sale)
                    qty = Decimal(str(ref_item.get('quantity', si.quantity)))
                    total_refund += si.unit_price * qty
                    if si.stock_deducted and si.product.is_trackable:
                        try:
                            inv = Inventory.objects.get(product=si.product, shop=sale.shop)
                            inv.current_stock += int(qty)
                            inv.save()
                        except Inventory.DoesNotExist:
                            pass

                if total_refund >= sale.total_amount:
                    sale.status = 'refunded'
                    sale.save()

                Payment.objects.create(
                    sale=sale, method=data.get('refund_method', 'cash'),
                    amount=-total_refund, status='completed',
                    notes=f"Refund: {data.get('reason', 'Customer request')}",
                )

                if sale.customer:
                    sale.customer.total_spent -= total_refund
                    sale.customer.loyalty_points = max(0, sale.customer.loyalty_points - int(total_refund / 100))
                    sale.customer.save()

            return Response({
                'success': True, 'refund_amount': float(total_refund),
                'sale_status': sale.status, 'message': 'Refund processed',
            })
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=400)


# ─── Customer Views ──────────────────────────────────────────────

class CustomerListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            business_id = request.query_params.get('business_id')
            search = request.query_params.get('search', '')
            if not business_id:
                return Response({'success': False, 'error': 'business_id required'}, status=400)

            business = get_object_or_404(Business, id=business_id, owner=request.user)
            customers = Customer.objects.filter(business=business, is_active=True)
            if search:
                customers = customers.filter(Q(name__icontains=search) | Q(phone_number__icontains=search))

            return Response({
                'success': True,
                'customers': [{
                    'id': str(c.id), 'name': c.name, 'phone_number': c.phone_number,
                    'email': c.email, 'address': c.address,
                    'loyalty_points': c.loyalty_points, 'total_spent': float(c.total_spent),
                    'created_at': c.created_at.isoformat(), 'updated_at': c.updated_at.isoformat(),
                } for c in customers.order_by('-updated_at')[:100]],
            })
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=400)


class CustomerCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = request.data
            business_id = data.get('business_id')
            if not business_id:
                return Response({'success': False, 'error': 'business_id required'}, status=400)

            business = get_object_or_404(Business, id=business_id, owner=request.user)
            phone = data.get('phone_number')
            if phone and Customer.objects.filter(business=business, phone_number=phone, is_active=True).exists():
                return Response({'success': False, 'error': 'Customer with this phone exists'}, status=400)

            customer = Customer.objects.create(
                business=business, name=data.get('name', 'Walk-in'),
                phone_number=phone, email=data.get('email', ''),
                address=data.get('address', ''),
            )
            return Response({
                'success': True,
                'customer': {
                    'id': str(customer.id), 'name': customer.name,
                    'phone_number': customer.phone_number, 'email': customer.email,
                    'loyalty_points': 0, 'total_spent': 0,
                    'created_at': customer.created_at.isoformat(),
                },
                'message': 'Customer created',
            }, status=201)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=400)


class CustomerDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, customer_id):
        try:
            c = get_object_or_404(Customer, id=customer_id, is_active=True)
            if c.business.owner != request.user:
                return Response({'success': False, 'error': 'Access denied'}, status=403)

            purchases = Sale.objects.filter(customer=c, status='completed').order_by('-sale_date')[:20]
            return Response({
                'success': True,
                'customer': {
                    'id': str(c.id), 'name': c.name, 'phone_number': c.phone_number,
                    'email': c.email, 'address': c.address,
                    'loyalty_points': c.loyalty_points, 'total_spent': float(c.total_spent),
                    'preferences': c.preferences,
                    'purchase_history': [{
                        'id': str(s.id), 'receipt_number': s.receipt_number,
                        'total_amount': float(s.total_amount), 'sale_date': s.sale_date.isoformat(),
                    } for s in purchases],
                    'created_at': c.created_at.isoformat(),
                },
            })
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=400)

    def put(self, request, customer_id):
        try:
            c = get_object_or_404(Customer, id=customer_id, is_active=True)
            if c.business.owner != request.user:
                return Response({'success': False, 'error': 'Access denied'}, status=403)
            data = request.data
            for field in ['name', 'phone_number', 'email', 'address']:
                if field in data:
                    setattr(c, field, data[field])
            if 'preferences' in data and isinstance(data['preferences'], dict):
                c.preferences = data['preferences']
            c.save()
            return Response({'success': True, 'message': 'Customer updated'})
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=400)

    def delete(self, request, customer_id):
        try:
            c = get_object_or_404(Customer, id=customer_id)
            if c.business.owner != request.user:
                return Response({'success': False, 'error': 'Access denied'}, status=403)
            c.is_active = False
            c.save()
            return Response({'success': True, 'message': 'Customer deactivated'})
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=400)


# ─── Reporting ────────────────────────────────────────────────────

class SalesReportView(APIView):
    """Comprehensive sales reporting with trend, top products, payment breakdown"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            business_id = request.query_params.get('business_id')
            shop_id = request.query_params.get('shop_id')
            period = request.query_params.get('period', 'daily')
            date_from = request.query_params.get('date_from')
            date_to = request.query_params.get('date_to')

            sales = Sale.objects.filter(status='completed')
            if shop_id:
                sales = sales.filter(shop_id=shop_id)
            elif business_id:
                sales = sales.filter(shop__business_id=business_id, shop__business__owner=user)
            else:
                sales = sales.filter(shop__business__owner=user)

            if date_from:
                sales = sales.filter(sale_date__date__gte=date_from)
            if date_to:
                sales = sales.filter(sale_date__date__lte=date_to)

            trunc_fn = {'weekly': TruncWeek, 'monthly': TruncMonth}.get(period, TruncDate)

            trend = sales.annotate(p=trunc_fn('sale_date')).values('p').annotate(
                revenue=Sum('total_amount'), count=Count('id'), avg=Avg('total_amount'),
            ).order_by('p')

            top_products = SaleItem.objects.filter(sale__in=sales).values(
                'product__id', 'product__name'
            ).annotate(qty=Sum('quantity'), rev=Sum('total_price')).order_by('-rev')[:10]

            payment_bd = Payment.objects.filter(
                sale__in=sales, status='completed', amount__gt=0
            ).values('method').annotate(total=Sum('amount'), count=Count('id')).order_by('-total')

            emp_stats = sales.values(
                'attendant__user__first_name', 'attendant__user__last_name', 'attendant__id'
            ).annotate(rev=Sum('total_amount'), cnt=Count('id'), avg=Avg('total_amount')).order_by('-rev')[:10]

            overall = sales.aggregate(
                revenue=Sum('total_amount'), tax=Sum('tax_amount'),
                discount=Sum('discount_amount'), count=Count('id'), avg=Avg('total_amount'),
            )

            return Response({
                'success': True,
                'report': {
                    'summary': {
                        'total_revenue': float(overall['revenue'] or 0),
                        'total_tax': float(overall['tax'] or 0),
                        'total_discount': float(overall['discount'] or 0),
                        'sale_count': overall['count'] or 0,
                        'average_sale': float(overall['avg'] or 0),
                    },
                    'trend': [{'period': t['p'].isoformat() if t['p'] else None, 'revenue': float(t['revenue'] or 0), 'count': t['count'], 'avg': float(t['avg'] or 0)} for t in trend],
                    'top_products': [{'product_id': str(p['product__id']), 'name': p['product__name'], 'qty': float(p['qty']), 'revenue': float(p['rev'])} for p in top_products],
                    'payment_breakdown': [{'method': p['method'], 'total': float(p['total']), 'count': p['count']} for p in payment_bd],
                    'employee_performance': [{'id': str(e['attendant__id']), 'name': f"{e['attendant__user__first_name'] or ''} {e['attendant__user__last_name'] or ''}".strip(), 'revenue': float(e['rev']), 'count': e['cnt']} for e in emp_stats],
                },
            })
        except Exception as e:
            logger.error(f"Report error: {str(e)}", exc_info=True)
            return Response({'success': False, 'error': str(e)}, status=400)


class DashboardView(APIView):
    """Dashboard summary for owners/employees"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            business_id = request.query_params.get('business_id')
            shop_id = request.query_params.get('shop_id')
            today = timezone.now().date()

            sales = Sale.objects.filter(status='completed')
            if shop_id:
                sales = sales.filter(shop_id=shop_id)
            elif business_id:
                sales = sales.filter(shop__business_id=business_id, shop__business__owner=user)
            else:
                sales = sales.filter(shop__business__owner=user)

            today_agg = sales.filter(sale_date__date=today).aggregate(revenue=Sum('total_amount'), count=Count('id'))
            week_start = today - timezone.timedelta(days=today.weekday())
            week_agg = sales.filter(sale_date__date__gte=week_start).aggregate(revenue=Sum('total_amount'), count=Count('id'))
            month_agg = sales.filter(sale_date__month=today.month, sale_date__year=today.year).aggregate(revenue=Sum('total_amount'), count=Count('id'))

            # Low stock
            inv_q = Inventory.objects.filter(is_active=True, current_stock__lte=F('minimum_stock'))
            if shop_id:
                inv_q = inv_q.filter(shop_id=shop_id)
            elif business_id:
                inv_q = inv_q.filter(shop__business_id=business_id)
            else:
                inv_q = inv_q.filter(shop__business__owner=user)

            low_stock = [{
                'product_name': inv.variant.name if inv.variant else (inv.product.name if inv.product else '?'),
                'shop_name': inv.shop.name, 'current_stock': inv.current_stock,
                'minimum_stock': inv.minimum_stock,
            } for inv in inv_q.select_related('product', 'variant', 'shop')[:10]]

            recent = [{
                'id': str(s.id), 'receipt_number': s.receipt_number,
                'total_amount': float(s.total_amount), 'sale_date': s.sale_date.isoformat(),
                'customer_name': s.customer.name if s.customer else 'Walk-in',
            } for s in sales.order_by('-sale_date')[:5]]

            return Response({
                'success': True,
                'dashboard': {
                    'today': {'revenue': float(today_agg['revenue'] or 0), 'count': today_agg['count'] or 0},
                    'this_week': {'revenue': float(week_agg['revenue'] or 0), 'count': week_agg['count'] or 0},
                    'this_month': {'revenue': float(month_agg['revenue'] or 0), 'count': month_agg['count'] or 0},
                    'low_stock_alerts': low_stock,
                    'recent_sales': recent,
                },
            })
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=400)


class SalesDownloadView(APIView):
    """Download sales+customers data for offline sync"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            shop_id = request.query_params.get('shop_id')
            business_id = request.query_params.get('business_id')
            since = request.query_params.get('since')

            q = Sale.objects.all()
            if shop_id:
                q = q.filter(shop_id=shop_id)
            elif business_id:
                q = q.filter(shop__business_id=business_id, shop__business__owner=user)
            else:
                q = q.filter(shop__business__owner=user)
            if since:
                q = q.filter(updated_at__gte=since)

            sales_data = []
            for sale in q.select_related('shop', 'attendant', 'customer').prefetch_related('items', 'payments'):
                sales_data.append({
                    'id': str(sale.id), 'receipt_number': sale.receipt_number,
                    'offline_id': sale.offline_id, 'shop_id': str(sale.shop_id),
                    'attendant_id': str(sale.attendant_id),
                    'customer_id': str(sale.customer_id) if sale.customer_id else None,
                    'subtotal': float(sale.subtotal), 'tax_amount': float(sale.tax_amount),
                    'discount_amount': float(sale.discount_amount),
                    'total_amount': float(sale.total_amount),
                    'amount_paid': float(sale.amount_paid), 'change_given': float(sale.change_given),
                    'status': sale.status, 'sync_status': sale.sync_status,
                    'is_offline': sale.is_offline,
                    'items': [{'id': str(i.id), 'product_id': str(i.product_id), 'quantity': float(i.quantity), 'unit_price': float(i.unit_price), 'total_price': float(i.total_price)} for i in sale.items.all()],
                    'payments': [{'id': str(p.id), 'method': p.method, 'amount': float(p.amount), 'transaction_code': p.transaction_code or ''} for p in sale.payments.all()],
                    'sale_date': sale.sale_date.isoformat(),
                    'created_at': sale.created_at.isoformat(),
                    'updated_at': sale.updated_at.isoformat(),
                })

            cq = Customer.objects.filter(is_active=True)
            if business_id:
                cq = cq.filter(business_id=business_id)
            else:
                cq = cq.filter(business__owner=user)
            if since:
                cq = cq.filter(updated_at__gte=since)

            customers_data = [{
                'id': str(c.id), 'business_id': str(c.business_id), 'name': c.name,
                'phone_number': c.phone_number, 'email': c.email,
                'loyalty_points': c.loyalty_points, 'total_spent': float(c.total_spent),
                'created_at': c.created_at.isoformat(), 'updated_at': c.updated_at.isoformat(),
            } for c in cq]

            return Response({
                'success': True,
                'data': {'sales': sales_data, 'customers': customers_data},
                'count': {'sales': len(sales_data), 'customers': len(customers_data)},
                'sync_timestamp': timezone.now().isoformat(),
            })
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=500)

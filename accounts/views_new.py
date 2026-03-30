# accounts/views_new.py
# New endpoints: employee login, onboarding, configuration, notifications, messages, verification
import logging
from datetime import timedelta

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Configuration, Message, Notification, UserProfile
from .utils import (
    create_notification,
    generate_verification_code,
    notify_employee_joined,
    validate_offline_id,
)
from shops.models import Business, Employee, Shop

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Employee Login – detects temp password, triggers onboarding
# ──────────────────────────────────────────────────────────
class EmployeeLoginView(APIView):
    """
    Employee login endpoint.
    - If the user still has a temporary password → flag requires_onboarding.
    - If first login not complete → flag requires_setup.
    - Otherwise proceed normally.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({"detail": "Username/email and password required"}, status=400)

        user = authenticate(username=username, password=password)
        if not user:
            return Response({"detail": "Invalid username/email or password"}, status=401)

        profile = user.profile
        refresh = RefreshToken.for_user(user)

        # Check if this is a temp-password login
        employee_records = Employee.objects.filter(user=user, is_active=True)
        using_temp_password = employee_records.filter(
            temporary_password__isnull=False
        ).exclude(temporary_password='').exists()

        # Check password expiry
        expired_password = employee_records.filter(
            password_expiry__isnull=False,
            password_expiry__lt=timezone.now()
        ).exists()

        if expired_password and using_temp_password:
            return Response({
                "detail": "Your temporary password has expired. Please ask your manager to resend credentials.",
                "password_expired": True,
            }, status=403)

        requires_onboarding = using_temp_password and not profile.has_changed_temp_password
        requires_setup = not profile.is_first_login_complete

        # Determine assigned shops
        shops = []
        for emp in employee_records.select_related('shop', 'role'):
            shops.append({
                'employee_id': str(emp.id),
                'shop_id': str(emp.shop.id),
                'shop_name': emp.shop.name,
                'business_id': str(emp.shop.business.id),   # ← ADD THIS
                'business_name': emp.shop.business.name,    # ← ADD THIS
                'role_id': str(emp.role.id),
                'role_name': emp.role.name,
            })

        # Get business configuration for theme inheritance
        config_data = None
        if employee_records.exists():
            biz = employee_records.first().shop.business
            try:
                cfg = biz.configuration
                config_data = {
                    'primary_color': cfg.primary_color,
                    'secondary_color': cfg.secondary_color,
                    'accent_color': cfg.accent_color,
                    'theme_mode': cfg.theme_mode,
                    'operation_mode': cfg.operation_mode,
                    'currency_symbol': cfg.currency_symbol,
                }
            except Configuration.DoesNotExist:
                pass

        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "user_type": profile.user_type,
                "phone_number": profile.phone_number,
                "is_verified": profile.is_verified,
            },
            "requires_onboarding": requires_onboarding,
            "requires_setup": requires_setup,
            "assigned_shops": shops,
            "configuration": config_data,
        })


# ──────────────────────────────────────────────────────────
# Complete Onboarding
# ──────────────────────────────────────────────────────────
class CompleteOnboardingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        data = request.data
        profile = user.profile

        # Change password
        new_password = data.get('new_password')
        if new_password:
            if len(new_password) < 8:
                return Response({'error': 'Password must be at least 8 characters'}, status=400)
            user.set_password(new_password)
            user.save()
            profile.has_changed_temp_password = True

            # Clear temporary passwords and mark invite as accepted on all active employee records
            Employee.objects.filter(user=user, is_active=True).update(
                temporary_password=None,
                password_expiry=None,
                is_invite_accepted=True   # Mark invitation as fully accepted
            )

        # Update profile fields
        if data.get('first_name'):
            user.first_name = data['first_name']
        if data.get('last_name'):
            user.last_name = data['last_name']
        if data.get('phone_number'):
            profile.phone_number = data['phone_number']
        user.save()

        profile.is_first_login_complete = True
        profile.onboarding_completed_at = timezone.now()
        profile.save()

        # Notify business owners (optional)
        for emp in Employee.objects.filter(user=user, is_active=True).select_related('shop__business'):
            notify_employee_joined(emp, emp.shop.business)

        # Issue fresh tokens
        refresh = RefreshToken.for_user(user)

        # Build user profile data to return
        user_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'user_type': profile.user_type,
            'phone_number': profile.phone_number,
            'is_verified': profile.is_verified,
            'has_changed_temp_password': profile.has_changed_temp_password,
            'is_first_login_complete': profile.is_first_login_complete,
        }

        return Response({
            'success': True,
            'message': 'Onboarding completed successfully',
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': user_data,   # Include updated user data
        })


# ──────────────────────────────────────────────────────────
# Change Temporary Password
# ──────────────────────────────────────────────────────────
class ChangeTempPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        new_password = request.data.get('new_password')
        if not new_password or len(new_password) < 8:
            return Response({'error': 'Password must be at least 8 characters'}, status=400)

        user.set_password(new_password)
        user.save()
        user.profile.has_changed_temp_password = True
        user.profile.save()

        Employee.objects.filter(user=user, is_active=True).update(
            temporary_password=None, password_expiry=None
        )

        refresh = RefreshToken.for_user(user)
        return Response({
            'success': True,
            'message': 'Password changed successfully',
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })


# ──────────────────────────────────────────────────────────
# Verify Invitation Code
# ──────────────────────────────────────────────────────────
class VerifyInviteCodeView(APIView):
    """Verify the 6-digit code sent with the employee invite."""
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').lower().strip()
        code = request.data.get('verification_code', '').strip()

        if not email or not code:
            return Response({'error': 'Email and verification code are required'}, status=400)

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response({'error': 'No account found with this email'}, status=404)

        emp = Employee.objects.filter(
            user=user, is_active=True,
            verification_code=code,
        ).first()

        if not emp:
            return Response({'error': 'Invalid verification code'}, status=400)

        if emp.verification_code_expiry and emp.verification_code_expiry < timezone.now():
            return Response({'error': 'Verification code has expired. Please request a new invite.'}, status=400)

        emp.is_invite_accepted = True
        emp.verification_code = None
        emp.verification_code_expiry = None
        emp.save()

        return Response({
            'success': True,
            'message': 'Verification successful',
            'user_id': user.id,
            'employee_id': str(emp.id),
        })


# ──────────────────────────────────────────────────────────
# Configuration (Business Theme)
# ──────────────────────────────────────────────────────────
class ConfigurationView(APIView):
    """Get or update business configuration / theme."""
    permission_classes = [IsAuthenticated]

    def get(self, request, business_id):
        business = get_object_or_404(Business, id=business_id)
        # Allow owner or employees of the business to read config
        cfg, created = Configuration.objects.get_or_create(business=business)
        return Response({
            'success': True,
            'configuration': self._serialize(cfg),
        })

    def put(self, request, business_id):
        business = get_object_or_404(Business, id=business_id, owner=request.user)
        cfg, _ = Configuration.objects.get_or_create(business=business)
        data = request.data

        updatable = [
            'primary_color', 'secondary_color', 'accent_color', 'theme_mode',
            'operation_mode', 'default_printer_width', 'currency_symbol',
            'date_format', 'time_format', 'extra_settings',
        ]
        for field in updatable:
            if field in data:
                setattr(cfg, field, data[field])
        cfg.save()

        # Notify employees of config change
        create_notification(
            title='App Settings Updated',
            message=f'The app theme and settings for {business.name} have been updated by the owner.',
            recipient_role='all',
            business=business,
            notification_type='system',
            category='general',
        )

        return Response({
            'success': True,
            'configuration': self._serialize(cfg),
            'message': 'Configuration updated successfully',
        })

    @staticmethod
    def _serialize(cfg):
        return {
            'id': str(cfg.id),
            'business_id': str(cfg.business_id),
            'primary_color': cfg.primary_color,
            'secondary_color': cfg.secondary_color,
            'accent_color': cfg.accent_color,
            'theme_mode': cfg.theme_mode,
            'operation_mode': cfg.operation_mode,
            'default_printer_width': cfg.default_printer_width,
            'currency_symbol': cfg.currency_symbol,
            'date_format': cfg.date_format,
            'time_format': cfg.time_format,
            'extra_settings': cfg.extra_settings,
            'updated_at': cfg.updated_at.isoformat(),
        }


# ──────────────────────────────────────────────────────────
# Notifications
# ──────────────────────────────────────────────────────────
class NotificationListView(APIView):
    """List notifications for the current user (paginated)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = user.profile
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))

        # Notifications targeted to this user directly OR to their role
        qs = Notification.objects.filter(
            Q(recipient=user) |
            Q(recipient_role=profile.user_type) |
            Q(recipient_role='all')
        )

        # Optional filter by business
        business_id = request.query_params.get('business_id')
        if business_id:
            qs = qs.filter(business_id=business_id)

        total = qs.count()
        unread = qs.filter(is_read=False).count()
        start = (page - 1) * page_size
        notifications = qs[start:start + page_size]

        data = []
        for n in notifications:
            data.append({
                'id': str(n.id),
                'title': n.title,
                'message': n.message,
                'notification_type': n.notification_type,
                'category': n.category,
                'is_read': n.is_read,
                'related_object_type': n.related_object_type,
                'related_object_id': str(n.related_object_id) if n.related_object_id else None,
                'created_at': n.created_at.isoformat(),
            })

        return Response({
            'success': True,
            'notifications': data,
            'total': total,
            'unread': unread,
            'page': page,
            'page_size': page_size,
        })


class NotificationMarkReadView(APIView):
    """Mark a single notification as read."""
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        notif = get_object_or_404(Notification, id=notification_id, recipient=request.user)
        notif.is_read = True
        notif.read_at = timezone.now()
        notif.save()
        return Response({'success': True, 'message': 'Notification marked as read'})


class NotificationMarkAllReadView(APIView):
    """Mark all notifications as read."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        profile = user.profile
        count = Notification.objects.filter(
            Q(recipient=user) | Q(recipient_role=profile.user_type) | Q(recipient_role='all'),
            is_read=False,
        ).update(is_read=True, read_at=timezone.now())
        return Response({'success': True, 'message': f'{count} notifications marked as read'})


# ──────────────────────────────────────────────────────────
# Messages
# ──────────────────────────────────────────────────────────
class MessageListView(APIView):
    """List messages for the current user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        folder = request.query_params.get('folder', 'inbox')  # inbox | sent

        if folder == 'sent':
            qs = Message.objects.filter(sender=user)
        else:
            qs = Message.objects.filter(recipient=user)

        business_id = request.query_params.get('business_id')
        if business_id:
            qs = qs.filter(business_id=business_id)

        total = qs.count()
        unread = Message.objects.filter(recipient=user, is_read=False).count()
        start = (page - 1) * page_size
        messages = qs.select_related('sender', 'recipient', 'business')[start:start + page_size]

        data = []
        for m in messages:
            data.append({
                'id': str(m.id),
                'sender_id': m.sender_id,
                'sender_name': m.sender.get_full_name() or m.sender.username,
                'recipient_id': m.recipient_id,
                'recipient_name': m.recipient.get_full_name() or m.recipient.username,
                'business_id': str(m.business_id),
                'business_name': m.business.name,
                'message': m.message,
                'is_read': m.is_read,
                'created_at': m.created_at.isoformat(),
            })

        return Response({
            'success': True,
            'messages': data,
            'total': total,
            'unread': unread,
            'page': page,
            'page_size': page_size,
        })


class MessageSendView(APIView):
    """Send a message to another user within the same business."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sender = request.user
        recipient_id = request.data.get('recipient_id')
        business_id = request.data.get('business_id')
        text = request.data.get('message', '').strip()

        if not recipient_id or not business_id or not text:
            return Response({'error': 'recipient_id, business_id, and message are required'}, status=400)

        business = get_object_or_404(Business, id=business_id)
        recipient = get_object_or_404(User, id=recipient_id)

        # Verify both users belong to the business
        sender_in_biz = (
            business.owner == sender or
            Employee.objects.filter(user=sender, shop__business=business, is_active=True).exists()
        )
        recipient_in_biz = (
            business.owner == recipient or
            Employee.objects.filter(user=recipient, shop__business=business, is_active=True).exists()
        )
        if not sender_in_biz or not recipient_in_biz:
            return Response({'error': 'Both users must belong to the same business'}, status=403)

        msg = Message.objects.create(
            business=business,
            sender=sender,
            recipient=recipient,
            message=text,
        )

        # Create a notification for the recipient
        create_notification(
            title='New Message',
            message=f'You have a new message from {sender.get_full_name() or sender.username}.',
            recipient=recipient,
            business=business,
            notification_type='info',
            category='general',
        )

        return Response({
            'success': True,
            'message_id': str(msg.id),
            'message': 'Message sent successfully',
        }, status=201)


class MessageMarkReadView(APIView):
    """Mark a message as read."""
    permission_classes = [IsAuthenticated]

    def post(self, request, message_id):
        msg = get_object_or_404(Message, id=message_id, recipient=request.user)
        msg.is_read = True
        msg.read_at = timezone.now()
        msg.save()
        return Response({'success': True})


class RequestResendCredentialsView(APIView):
    """
    Public endpoint for an employee to request a new temporary password if their previous one expired.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').lower().strip()
        if not email:
            return Response({'error': 'Email is required'}, status=400)

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response({'error': 'No account found with this email'}, status=404)

        employees = Employee.objects.filter(user=user, is_active=True)
        if not employees.exists():
            return Response({'error': 'This account is not associated with any employee role'}, status=400)

        # Check if any employee record has an expired temporary password
        expired_emp = employees.filter(
            password_expiry__isnull=False,
            password_expiry__lt=timezone.now()
        ).first()
        if not expired_emp:
            return Response({'error': 'Your temporary password is still valid or not expired. If you forgot, please contact your manager.'}, status=400)

        # Generate new temporary password
        from shops.serializers import EmployeeCreateSerializer
        serializer = EmployeeCreateSerializer()
        new_temp_password = serializer.generate_temporary_password()
        new_expiry = timezone.now() + timedelta(hours=24)

        # Update all active employee records for this user
        employees.update(
            temporary_password=new_temp_password,
            password_expiry=new_expiry,
            verification_code=generate_verification_code(),
            verification_code_expiry=timezone.now() + timedelta(minutes=30),
            is_invite_accepted=False
        )

        # Update user's password
        user.set_password(new_temp_password)
        user.save()

        # Reset profile flags
        profile = user.profile
        profile.has_changed_temp_password = False
        profile.save()

        # Send email
        self.send_credentials_email(user, new_temp_password, expired_emp.shop, expired_emp.role)

        return Response({
            'success': True,
            'message': 'New credentials have been sent to your email. Please check your inbox.'
        })

    def send_credentials_email(self, user, temporary_password, shop, role):
        from django.core.mail import EmailMultiAlternatives
        from django.conf import settings

        subject = f"Your new login credentials for {shop.business.name}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>New Login Credentials</title>
        </head>
        <body>
            <div style="max-width: 600px; margin: 0 auto; background: #ffffff; font-family: Arial, sans-serif;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px 30px; text-align: center;">
                    <div style="font-size: 24px; font-weight: 600; margin-bottom: 10px;">{shop.business.name}</div>
                    <div style="opacity: 0.9; font-size: 14px;">New Login Credentials</div>
                </div>

                <div style="padding: 40px 30px;">
                    <h2 style="font-size: 20px; font-weight: 600; color: #2d3748; margin-bottom: 25px;">
                        Hello {user.first_name or user.username},
                    </h2>

                    <p>Your previous temporary password has expired. Please use the new temporary password below to log in.</p>

                    <div style="background: #ebf8ff; border: 1px solid #bee3f8; border-radius: 8px; padding: 25px; margin: 25px 0;">
                        <strong>🔐 New Temporary Password</strong>
                        <div style="display: inline-block; background: #2d3748; color: #68d391; font-family: 'Courier New', monospace; font-size: 18px; font-weight: 600; padding: 12px 20px; border-radius: 6px; letter-spacing: 1px; margin: 10px 0;">
                            {temporary_password}
                        </div>
                        <small style="color: #718096;">Valid for 24 hours</small>
                    </div>

                    <div style="background: #fff5f5; border: 1px solid #fc8181; border-left: 4px solid #e53e3e; color: #c53030; padding: 18px; border-radius: 0 4px 4px 0; margin: 25px 0; font-size: 14px;">
                        ⚠️ <strong>Security Notice:</strong> For your protection, please change your password immediately after logging in for the first time. Do not share these credentials with anyone.
                    </div>

                    <div style="margin: 30px 0;">
                        <strong>🚀 Getting Started</strong>
                        <div style="display: flex; margin-bottom: 20px;">
                            <div style="background: #4299e1; color: white; width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 15px; flex-shrink: 0; font-weight: 600;">1</div>
                            <div>Open the ShopSync app</div>
                        </div>
                        <div style="display: flex; margin-bottom: 20px;">
                            <div style="background: #4299e1; color: white; width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 15px; flex-shrink: 0; font-weight: 600;">2</div>
                            <div>Tap "Login" and enter your email and this temporary password</div>
                        </div>
                        <div style="display: flex; margin-bottom: 20px;">
                            <div style="background: #4299e1; color: white; width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 15px; flex-shrink: 0; font-weight: 600;">3</div>
                            <div>Follow the prompts to set up your secure password</div>
                        </div>
                    </div>

                    <div style="text-align: center; color: #718096; font-size: 14px; margin-top: 40px; padding-top: 25px; border-top: 1px solid #e2e8f0;">
                        <p>This is an automated message from {shop.business.name}'s employee management system.</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        plain_text = f"""
Hello {user.first_name or user.username},

Your previous temporary password for {shop.business.name} has expired.
Please use the following new temporary password to log in:

Temporary Password: {temporary_password}
Valid for 24 hours.

After logging in, you will be prompted to set a new password.

Best regards,
{shop.business.name} Management Team
"""

        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send()


# ──────────────────────────────────────────────────────────
# Receipt Template CRUD
# ──────────────────────────────────────────────────────────
class ReceiptTemplateView(APIView):
    """Get or update receipt template for a shop."""
    permission_classes = [IsAuthenticated]

    def get(self, request, shop_id):
        shop = get_object_or_404(Shop, id=shop_id)
        from sales.models import ReceiptTemplate
        try:
            tpl = shop.receipt_template
        except Exception:
            tpl = ReceiptTemplate.objects.create(shop=shop)
        return Response({'success': True, 'template': self._serialize(tpl, request)})

    def put(self, request, shop_id):
        shop = get_object_or_404(Shop, id=shop_id, business__owner=request.user)
        from sales.models import ReceiptTemplate
        tpl, _ = ReceiptTemplate.objects.get_or_create(shop=shop)
        data = request.data

        fields = [
            'header_text', 'footer_text', 'layout', 'show_logo', 'show_shop_address',
            'show_shop_phone', 'show_attendant_name', 'show_customer_name',
            'show_tax_breakdown', 'show_payment_method', 'printer_width', 'custom_fields',
        ]
        for f in fields:
            if f in data:
                setattr(tpl, f, data[f])

        # Handle logo upload
        if 'logo' in request.FILES:
            tpl.logo = request.FILES['logo']

        tpl.save()

        create_notification(
            title='Receipt Template Updated',
            message=f'Receipt template for {shop.name} has been updated.',
            recipient=request.user,
            business=shop.business,
            notification_type='success',
            category='receipt',
        )

        return Response({
            'success': True,
            'template': self._serialize(tpl, request),
            'message': 'Receipt template updated',
        })

    @staticmethod
    def _serialize(tpl, request=None):
        logo_url = None
        if tpl.logo:
            logo_url = request.build_absolute_uri(tpl.logo.url) if request else tpl.logo.url
        return {
            'id': str(tpl.id),
            'shop_id': str(tpl.shop_id),
            'header_text': tpl.header_text,
            'footer_text': tpl.footer_text,
            'logo': logo_url,
            'layout': tpl.layout,
            'show_logo': tpl.show_logo,
            'show_shop_address': tpl.show_shop_address,
            'show_shop_phone': tpl.show_shop_phone,
            'show_attendant_name': tpl.show_attendant_name,
            'show_customer_name': tpl.show_customer_name,
            'show_tax_breakdown': tpl.show_tax_breakdown,
            'show_payment_method': tpl.show_payment_method,
            'printer_width': tpl.printer_width,
            'custom_fields': tpl.custom_fields,
            'updated_at': tpl.updated_at.isoformat(),
        }

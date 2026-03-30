# accounts/views.py
import base64
import logging
import uuid
from django.conf import settings
from django.core.files.base import ContentFile
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes
from django.utils import timezone
from shops.models import Employee, Shop
from .models import Permission, Role, UserProfile

logger = logging.getLogger(__name__)

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data

        username = data.get('username')
        password = data.get('password')
        email = data.get('email', '')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        phone_number = data.get('phone_number', '')

        if not username or not password:
            return Response({"detail": "Username and password are required"}, status=400)

        if User.objects.filter(username=username).exists():
            return Response({"detail": "Username already taken"}, status=400)

        if email and User.objects.filter(email=email).exists():
            return Response({"detail": "Email already registered"}, status=400)

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        profile = user.profile
        profile.phone_number = phone_number
        profile.user_type = data.get('user_type', 'owner')
        profile.save()

        refresh = RefreshToken.for_user(user)

        return Response({
            "message": "User created successfully",
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "user_type": profile.user_type
            }
        }, status=201)


class CustomLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({"detail": "Username/email and password required"}, status=400)

        user = authenticate(username=username, password=password)
        if not user:
            return Response({"detail": "Invalid username/email or password"}, status=401)

        refresh = RefreshToken.for_user(user)
        profile = user.profile

        # --- Profile picture URL ---
        profile_picture_url = None
        if profile.profile_picture:
            profile_picture_url = get_absolute_media_url(request, profile.profile_picture.url)

        # --- Employee data ---
        employee_records = Employee.objects.filter(user=user, is_active=True)

        # Determine if temp password is in use
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
        requires_setup = not profile.is_first_login_complete and profile.user_type == 'employee'

        # --- Build assigned shops list (INCLUDING BUSINESS DETAILS) ---
        assigned_shops = []
        for emp in employee_records.select_related('shop', 'role', 'shop__business'):
            assigned_shops.append({
                'employee_id': str(emp.id),
                'shop_id': str(emp.shop.id),
                'shop_name': emp.shop.name,
                'business_id': str(emp.shop.business.id),   # ← ADDED
                'business_name': emp.shop.business.name,    # ← ADDED
                'role_id': str(emp.role.id),
                'role_name': emp.role.name,
            })

        # --- Business configuration for theme ---
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
            except Exception:
                pass

        # --- Unread counts ---
        from accounts.models import Notification, Message
        from django.db.models import Q
        unread_notifications = Notification.objects.filter(
            Q(recipient=user) |
            Q(recipient_role=profile.user_type) |
            Q(recipient_role='all'),
            is_read=False,
        ).count()
        unread_messages = Message.objects.filter(recipient=user, is_read=False).count()

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
                "date_of_birth": profile.date_of_birth,
                "profile_picture": profile_picture_url,
                "is_verified": profile.is_verified,
                "is_active": user.is_active,
                "last_login": user.last_login,
                "date_joined": user.date_joined,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
                "is_first_login_complete": profile.is_first_login_complete,
                "has_changed_temp_password": profile.has_changed_temp_password,
            },
            "requires_onboarding": requires_onboarding,
            "requires_setup": requires_setup,
            "assigned_shops": assigned_shops,          # ← Now includes business_id/name
            "configuration": config_data,
            "unread_notifications": unread_notifications,
            "unread_messages": unread_messages,
        })
    
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sync_accounts_data(request):
    """
    Endpoint to get all accounts data for syncing to local DB
    Returns users, profiles, permissions, roles, and employee assignments
    """
    user = request.user
    
    print(f"📱 Syncing accounts data for user: {user.username}")
    
    # Get all users in the system
    users_list = []
    for user_obj in User.objects.filter(is_active=True).select_related('profile'):
        profile = user_obj.profile
        
        # Get absolute URL for profile picture
        profile_picture_url = None
        if profile.profile_picture:
            profile_picture_url = get_absolute_media_url(request, profile.profile_picture.url)
        
        # Build comprehensive user data
        user_data = {
            'id': user_obj.id,
            'username': user_obj.username,
            'email': user_obj.email,
            'first_name': user_obj.first_name,
            'last_name': user_obj.last_name,
            'is_active': user_obj.is_active,
            'last_login': user_obj.last_login,
            'date_joined': user_obj.date_joined,
            # Include profile data
            'user_type': profile.user_type,
            'phone_number': profile.phone_number,
            'date_of_birth': profile.date_of_birth,
            'profile_picture': profile_picture_url,  # Absolute URL
            'is_verified': profile.is_verified,
            'pin_hash': profile.pin_hash,
            'fcm_token': profile.fcm_token,
            'preferences': profile.preferences,
            'created_at': profile.created_at,
            'updated_at': profile.updated_at,
        }
        users_list.append(user_data)
    
    # Get all permissions
    permissions = Permission.objects.filter(is_active=True).values(
        'id', 'code', 'name', 'description', 'category', 'is_active', 'created_at'
    )
    
    # Get all roles
    roles_data = []
    for role in Role.objects.all():
        roles_data.append({
            'id': str(role.id),
            'name': role.name,
            'role_type': role.role_type,
            'description': role.description,
            'is_default': role.is_default,
            'permission_ids': [str(perm.id) for perm in role.permissions.all()],
            'created_at': role.created_at,
            'updated_at': role.updated_at
        })
    
    # FIXED: Get ALL employee assignments for businesses owned by current user
    employee_assignments = []
    seen_employee_ids = set()  # Track duplicates
    
    # Strategy 1: Get employees from businesses owned by user
    from shops.models import Business
    owned_businesses = Business.objects.filter(owner=user, is_active=True)
    
    for business in owned_businesses:
        # Get all shops in this business
        shops = business.shops.filter(is_active=True)
        
        for shop in shops:
            # Get all active employees in this shop
            employees = Employee.objects.filter(shop=shop, is_active=True).select_related('user', 'role', 'user__profile')
            
            for emp in employees:
                emp_id = str(emp.id)
                if emp_id in seen_employee_ids:
                    continue
                    
                seen_employee_ids.add(emp_id)
                
                # Get user details for this employee
                user_obj = emp.user
                profile = user_obj.profile if hasattr(user_obj, 'profile') else None
                
                # Get profile picture URL
                profile_picture_url = None
                if profile and profile.profile_picture:
                    profile_picture_url = get_absolute_media_url(request, profile.profile_picture.url)
                
                employee_assignments.append({
                    'id': emp_id,
                    'user_id': user_obj.id,
                    'business_id': str(business.id),
                    'shop_id': str(shop.id),
                    'role_id': str(emp.role.id) if emp.role else None,
                    # User details for employee table
                    'first_name': user_obj.first_name or "",
                    'last_name': user_obj.last_name or "",
                    'email': user_obj.email or "",
                    'phone_number': profile.phone_number if profile else None,
                    'profile_picture': profile_picture_url,
                    # Employment details
                    'employment_type': emp.employment_type,
                    'salary': float(emp.salary) if emp.salary else None,
                    'is_active': emp.is_active,
                    'employment_date': emp.employment_date.isoformat() if emp.employment_date else None,
                    'termination_date': emp.termination_date.isoformat() if emp.termination_date else None,
                    'created_at': emp.created_at.isoformat(),
                    'updated_at': emp.updated_at.isoformat(),
                    'custom_permission_ids': [str(perm.id) for perm in emp.custom_permissions.all()],
                })
    
    # Strategy 2: Also get employee assignments where current user IS the employee
    # (in case they're an employee in another business)
    current_user_employees = Employee.objects.filter(user=user, is_active=True).select_related('shop', 'role', 'shop__business', 'user__profile')
    
    for emp in current_user_employees:
        emp_id = str(emp.id)
        if emp_id in seen_employee_ids:
            continue
            
        seen_employee_ids.add(emp_id)
        
        # Get user details
        user_obj = emp.user
        profile = user_obj.profile if hasattr(user_obj, 'profile') else None
        
        # Get profile picture URL
        profile_picture_url = None
        if profile and profile.profile_picture:
            profile_picture_url = get_absolute_media_url(request, profile.profile_picture.url)
        
        employee_assignments.append({
            'id': emp_id,
            'user_id': user_obj.id,
            'business_id': str(emp.shop.business.id) if emp.shop and emp.shop.business else None,
            'shop_id': str(emp.shop.id) if emp.shop else None,
            'role_id': str(emp.role.id) if emp.role else None,
            # User details for employee table
            'first_name': user_obj.first_name or "",
            'last_name': user_obj.last_name or "",
            'email': user_obj.email or "",
            'phone_number': profile.phone_number if profile else None,
            'profile_picture': profile_picture_url,
            # Employment details
            'employment_type': emp.employment_type,
            'salary': float(emp.salary) if emp.salary else None,
            'is_active': emp.is_active,
            'employment_date': emp.employment_date.isoformat() if emp.employment_date else None,
            'termination_date': emp.termination_date.isoformat() if emp.termination_date else None,
            'created_at': emp.created_at.isoformat(),
            'updated_at': emp.updated_at.isoformat(),
            'custom_permission_ids': [str(perm.id) for perm in emp.custom_permissions.all()],
        })
    
    print(f"👥 Found {len(employee_assignments)} employee assignments for user {user.username}")
    
    return Response({
        'users': users_list,
        'permissions': list(permissions),
        'roles': roles_data,
        'employees': employee_assignments,
        'sync_timestamp': timezone.now().isoformat()
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sync_employees_data(request):
    """
    Get ALL employees for user's businesses
    """
    user = request.user
    
    # Get businesses owned by current user
    from shops.models import Business, Shop, Employee
    owned_businesses = Business.objects.filter(owner=user, is_active=True)
    
    employee_assignments = []
    
    for business in owned_businesses:
        # Get all employees in this business (across all shops)
        employees = Employee.objects.filter(
            shop__business=business, 
            is_active=True
        ).select_related('user', 'role', 'shop')
        
        for emp in employees:
            employee_assignments.append({
                'id': str(emp.id),
                'user_id': emp.user.id,
                'business_id': str(business.id),
                'shop_id': str(emp.shop.id),
                'role_id': str(emp.role.id) if emp.role else None,
                'first_name': emp.user.first_name,
                'last_name': emp.user.last_name,
                'email': emp.user.email,
                'phone_number': emp.user.profile.phone_number if hasattr(emp.user, 'profile') else None,
                'employment_type': emp.employment_type,
                'salary': float(emp.salary) if emp.salary else None,
                'is_active': emp.is_active,
                'employment_date': emp.employment_date.isoformat() if emp.employment_date else None,
                'termination_date': emp.termination_date.isoformat() if emp.termination_date else None,
                'created_at': emp.created_at.isoformat(),
                'updated_at': emp.updated_at.isoformat(),
            })
    
    return Response({
        'employees': employee_assignments,
        'count': len(employee_assignments),
        'sync_timestamp': timezone.now().isoformat()
    })

class LogoutView(APIView):
    """
    Logout view that blacklists refresh token
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            return Response({
                "message": "Successfully logged out"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "error": "Invalid token"
            }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def verify_auth(request):
    """
    Verify if user is authenticated and get basic user info
    Useful for checking token validity
    """
    user = request.user
    profile = user.profile
    
    return Response({
        "authenticated": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "user_type": profile.user_type,
            "phone_number": profile.phone_number,
            "date_of_birth": profile.date_of_birth,
            "profile_picture": profile.profile_picture.url if profile.profile_picture else None,
            "is_verified": profile.is_verified,
            "is_active": user.is_active,
            "last_login": user.last_login,
            "date_joined": user.date_joined,
        }
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def verify_token(request):
    """
    Simple endpoint to verify if token is valid
    Returns basic user info if token is valid
    """
    user = request.user
    return Response({
        "authenticated": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
        }
    })

class CompleteUserSyncView(APIView):
    """
    Endpoint to get complete user data including all profile fields
    This is specifically for mobile app to ensure all data is synced
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            profile = user.profile
            
            # Get all user data including profile
            user_data = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_active": user.is_active,
                "last_login": user.last_login,
                "date_joined": user.date_joined,
                "user_type": profile.user_type,
                "phone_number": profile.phone_number,
                "date_of_birth": profile.date_of_birth,
                "profile_picture": profile.profile_picture.url if profile.profile_picture else None,
                "is_verified": profile.is_verified,
                "pin_hash": profile.pin_hash,
                "fcm_token": profile.fcm_token,
                "preferences": profile.preferences,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
            }
            
            return Response({
                "success": True,
                "user": user_data,
                "message": "Complete user data retrieved successfully"
            })
        except Exception as e:
            return Response({
                "success": False,
                "error": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
class UserProfileUpdateView(APIView):
    """
    Update user profile data from mobile app sync
    """
    permission_classes = [IsAuthenticated]

    def put(self, request):
        try:
            user = request.user
            data = request.data
            
            print(f"📱 Updating profile for user: {user.username}")
            
            # Update User model fields
            if 'first_name' in data:
                user.first_name = data['first_name']
            if 'last_name' in data:
                user.last_name = data['last_name']
            if 'email' in data:
                user.email = data['email']
            
            user.save()
            
            # Update UserProfile model fields
            profile = user.profile
            
            if 'phone_number' in data:
                profile.phone_number = data['phone_number']
            if 'date_of_birth' in data:
                profile.date_of_birth = data['date_of_birth']
            if 'profile_picture' in data:
                profile.profile_picture = data['profile_picture']
            
            # Mark as verified if syncing from app (assuming app users are verified)
            profile.is_verified = True
            profile.updated_at = timezone.now()
            profile.save()
            
            return Response({
                'success': True,
                'message': 'Profile updated successfully',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'user_type': profile.user_type,
                    'phone_number': profile.phone_number,
                    'date_of_birth': profile.date_of_birth,
                    'profile_picture': profile.profile_picture.url if profile.profile_picture else None,
                    'is_verified': profile.is_verified,
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class UserProfileDetailView(APIView):
    """
    Get current user's profile data
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            profile = user.profile
            
            return Response({
                'success': True,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'user_type': profile.user_type,
                    'phone_number': profile.phone_number,
                    'date_of_birth': profile.date_of_birth,
                    'profile_picture': profile.profile_picture.url if profile.profile_picture else None,
                    'is_verified': profile.is_verified,
                    'created_at': profile.created_at,
                    'updated_at': profile.updated_at,
                }
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class BulkSyncView(APIView):
    """
    Bulk sync endpoint for mobile app to push multiple updates
    Handles users, profiles, shops, employees with proper image URL handling
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            updates = request.data.get('updates', [])
            synced_updates = []
            
            logger.info(f"🔄 Bulk sync request from {user.username} with {len(updates)} updates")
            logger.info(f"🔍 Raw update data: {request.data}")

            for update in updates:
                try:
                    table = update.get('table')
                    local_id = update.get('local_id')
                    server_id = update.get('server_id')
                    data = update.get('data', {})
                    
                    logger.info(f"🔄 Processing {table} update with local_id: {local_id}, server_id: {server_id}")
                    logger.info(f"📝 Update data: {data}")
                    
                    if table == 'users':
                        result = self._process_user_update(update, user)
                        synced_updates.append(result)
                        
                    elif table == 'user_profiles':
                        result = self._process_profile_update(update, user)
                        synced_updates.append(result)
                    
                    elif table == 'shops':
                        result = self._process_shop_update(update, user)
                        synced_updates.append(result)
                    
                    elif table == 'employees':
                        result = self._process_employee_update(update, user)
                        synced_updates.append(result)
                    
                    else:
                        raise Exception(f"Unknown table: {table}")
                    
                except Exception as e:
                    logger.error(f"❌ Error processing update for {update.get('table')}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    synced_updates.append({
                        'table': update.get('table'),
                        'local_id': update.get('local_id'),
                        'success': False,
                        'error': str(e)
                    })
            
            success_count = len([u for u in synced_updates if u.get('success', False)])
            
            return Response({
                'success': True,
                'synced_updates': synced_updates,
                'message': f'Synced {success_count}/{len(updates)} updates'
            })
            
        except Exception as e:
            logger.error(f"❌ Bulk sync error: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def _process_user_update(self, update, current_user):
        """Process user update"""
        try:
            # Update user model fields
            user_to_update = current_user  # Default to current user
            
            # If we have a server_id, try to find that user
            server_id = update.get('server_id')
            if server_id and str(server_id) != str(current_user.id):
                # Only allow updating other users if user is admin/owner
                if current_user.profile.user_type in ['owner', 'admin']:
                    user_to_update = User.objects.get(id=server_id)
                else:
                    raise PermissionError("Not authorized to update other users")
            
            # Update user fields
            data = update.get('data', {})
            
            logger.info(f"📝 Updating user {user_to_update.username} with data: {data}")
            
            if 'first_name' in data:
                user_to_update.first_name = data['first_name']
            if 'last_name' in data:
                user_to_update.last_name = data['last_name']
            if 'email' in data and data['email']:
                user_to_update.email = data['email']
            
            user_to_update.save()
            
            # Update phone number in profile if provided
            if 'phone_number' in data:
                profile = user_to_update.profile
                old_phone = profile.phone_number
                profile.phone_number = data['phone_number']
                profile.save()
                logger.info(f"📞 Updated phone number for {user_to_update.username}: {old_phone} -> {data['phone_number']}")
            
            return {
                'table': 'users',
                'local_id': update.get('local_id'),
                'server_id': user_to_update.id,
                'success': True,
                'updated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing user update: {str(e)}")
            raise
    
    def _process_profile_update(self, update, current_user):
        """Process user profile update with image URL handling"""
        try:
            # Get user for this profile
            user_id = update.get('user_server_id') or update.get('user_local_id')
            if not user_id:
                user_for_profile = current_user
            else:
                try:
                    user_for_profile = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    raise Exception(f"User with ID {user_id} not found")
            
            # Update user profile
            profile = user_for_profile.profile
            data = update.get('data', {})
            
            logger.info(f"📝 Updating profile data for user {user_for_profile.username}")
            logger.info(f"📊 Profile data received: {data}")
            
            # Debug log current profile state
            logger.info(f"🔍 Current profile state - date_of_birth: {profile.date_of_birth}, phone: {profile.phone_number}")
            
            # Update profile fields
            if 'date_of_birth' in data:
                old_dob = profile.date_of_birth
                profile.date_of_birth = data['date_of_birth']
                logger.info(f"🎂 Updated date_of_birth for {user_for_profile.username}: {old_dob} -> {data['date_of_birth']}")
            
            # Handle profile picture - only accept uploaded URLs, not local URIs
            if 'profile_picture' in data and data['profile_picture']:
                picture_url = data['profile_picture']
                logger.info(f"🖼️ Processing profile picture URL: {picture_url}")
                
                # Only update if it's a valid server URL
                if (picture_url.startswith('http://') or picture_url.startswith('https://')):
                    # Check if this URL is from our media server
                    if picture_url.startswith(settings.MEDIA_URL) or 'profile_pics' in picture_url:
                        # Extract filename from URL
                        filename = picture_url.split('/')[-1]
                        # Update the ImageField with just the filename, Django will prepend MEDIA_URL
                        profile.profile_picture.name = f'profile_pics/{filename}'
                        logger.info(f"✅ Updated profile picture with filename: {filename}")
                    else:
                        # External URL - store as is
                        profile.profile_picture = picture_url
                        logger.info(f"✅ Updated profile picture with external URL")
                else:
                    # Log but don't save local URIs
                    logger.warning(f"⚠️ Skipping local file URI: {picture_url}")
                    # Don't update profile picture with local URI
            
            if 'pin_hash' in data:
                profile.pin_hash = data['pin_hash']
                logger.info(f"🔑 Updated pin_hash for {user_for_profile.username}")
            
            if 'fcm_token' in data:
                profile.fcm_token = data['fcm_token']
                logger.info(f"📱 Updated fcm_token for {user_for_profile.username}")
            
            if 'preferences' in data:
                if isinstance(data['preferences'], dict):
                    profile.preferences = data['preferences']
                    logger.info(f"⚙️ Updated preferences for {user_for_profile.username}")
            
            if 'phone_number' in data:
                old_phone = profile.phone_number
                profile.phone_number = data['phone_number']
                logger.info(f"📞 Updated phone in profile for {user_for_profile.username}: {old_phone} -> {data['phone_number']}")
            
            profile.updated_at = timezone.now()
            profile.save()
            
            # Verify the update
            profile.refresh_from_db()
            logger.info(f"✅ Profile updated successfully for user: {user_for_profile.username}")
            logger.info(f"✅ Final profile state - date_of_birth: {profile.date_of_birth}, phone: {profile.phone_number}")
            
            return {
                'table': 'user_profiles',
                'local_id': update.get('local_id'),
                'server_id': profile.id,
                'success': True,
                'updated_at': profile.updated_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing profile update: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    def _process_shop_update(self, update, current_user):
        """Process shop update"""
        try:
            server_id = update.get('server_id')
            data = update.get('data', {})
            action = update.get('action', 'update')
            
            if action == 'create' or not server_id:
                # Create new shop
                shop = Shop.objects.create(
                    name=data.get('name', ''),
                    shop_type=data.get('shop_type', 'retail'),
                    location=data.get('location', ''),
                    phone_number=data.get('phone_number', ''),
                    email=data.get('email', ''),
                    tax_rate=data.get('tax_rate', 0.0),
                    currency=data.get('currency', 'KES'),
                    is_active=data.get('is_active', True),
                    created_by=current_user
                )
                server_id = shop.id
                logger.info(f"🏪 Created new shop: {shop.name}")
            else:
                # Update existing shop
                shop = Shop.objects.get(id=server_id)
                if 'name' in data:
                    shop.name = data['name']
                if 'shop_type' in data:
                    shop.shop_type = data['shop_type']
                if 'location' in data:
                    shop.location = data['location']
                if 'phone_number' in data:
                    shop.phone_number = data['phone_number']
                if 'email' in data:
                    shop.email = data['email']
                if 'tax_rate' in data:
                    shop.tax_rate = data['tax_rate']
                if 'currency' in data:
                    shop.currency = data['currency']
                if 'is_active' in data:
                    shop.is_active = data['is_active']
                shop.save()
                logger.info(f"🏪 Updated shop: {shop.name}")
            
            return {
                'table': 'shops',
                'local_id': update.get('local_id'),
                'server_id': server_id,
                'success': True,
                'updated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing shop update: {str(e)}")
            raise
    
    def _process_employee_update(self, update, current_user):
        """Process employee update"""
        try:
            server_id = update.get('server_id')
            data = update.get('data', {})
            action = update.get('action', 'update')
            
            # Get user for employee
            user_id = data.get('user_id')
            if user_id:
                try:
                    employee_user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    raise Exception(f"User with ID {user_id} not found")
            else:
                employee_user = current_user
            
            # Get shop for employee
            shop_id = data.get('shop_id')
            if shop_id:
                try:
                    shop = Shop.objects.get(id=shop_id)
                except Shop.DoesNotExist:
                    raise Exception(f"Shop with ID {shop_id} not found")
            else:
                raise Exception("Shop ID is required for employee")
            
            if action == 'create' or not server_id:
                # Create new employee
                employee = Employee.objects.create(
                    user=employee_user,
                    shop=shop,
                    role_type=data.get('role_type', 'employee'),
                    role_name=data.get('role_name', ''),
                    is_active=data.get('is_active', True),
                    employment_date=data.get('employment_date'),
                    termination_date=data.get('termination_date'),
                    created_by=current_user
                )
                server_id = employee.id
                logger.info(f"👤 Created new employee: {employee_user.username} at {shop.name}")
            else:
                # Update existing employee
                employee = Employee.objects.get(id=server_id)
                if 'role_type' in data:
                    employee.role_type = data['role_type']
                if 'role_name' in data:
                    employee.role_name = data['role_name']
                if 'is_active' in data:
                    employee.is_active = data['is_active']
                if 'employment_date' in data:
                    employee.employment_date = data['employment_date']
                if 'termination_date' in data:
                    employee.termination_date = data['termination_date']
                employee.save()
                logger.info(f"👤 Updated employee: {employee_user.username}")
            
            return {
                'table': 'employees',
                'local_id': update.get('local_id'),
                'server_id': server_id,
                'success': True,
                'updated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing employee update: {str(e)}")
            raise


class ProfilePictureUploadView(APIView):
    """
    Upload profile picture and return server URL
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        try:
            user = request.user
            profile = user.profile
            
            logger.info(f"📸 Uploading profile picture for user: {user.username}")
            
            if 'profile_picture' not in request.FILES:
                return Response({
                    'success': False,
                    'error': 'No image file provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            image_file = request.FILES['profile_picture']
            
            # Validate file type
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if image_file.content_type not in allowed_types:
                return Response({
                    'success': False,
                    'error': f'Invalid file type: {image_file.content_type}. Allowed: JPEG, PNG, GIF, WEBP'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate file size (max 5MB)
            max_size = 5 * 1024 * 1024  # 5MB
            if image_file.size > max_size:
                return Response({
                    'success': False,
                    'error': 'File too large. Maximum size is 5MB'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Generate unique filename
            file_extension = image_file.name.split('.')[-1]
            filename = f"profile_{user.id}_{uuid.uuid4().hex[:8]}.{file_extension}"
            
            # Save the file
            profile.profile_picture.save(filename, image_file)
            profile.save()
            
            # Get the correct URL
            # Use the actual URL from the ImageField, not build_absolute_uri
            if profile.profile_picture:
                # In Django, the ImageField's url property returns the relative URL
                relative_url = profile.profile_picture.url
                
                # Build the full URL manually to ensure correctness
                if settings.DEBUG:
                    # For development, use the current request's host
                    host = request.get_host()
                    scheme = 'http' if not request.is_secure() else 'https'
                    picture_url = f"{scheme}://{host}{relative_url}"
                else:
                    # For production, you might want to use your domain
                    # Alternatively, you can configure MEDIA_URL with full domain in production
                    picture_url = f"{settings.MEDIA_URL}{relative_url.lstrip('/')}"
                
                logger.info(f"✅ Profile picture uploaded. Relative URL: {relative_url}")
                logger.info(f"✅ Full picture URL: {picture_url}")
                
                # Test if the file actually exists
                import os
                file_path = profile.profile_picture.path
                if os.path.exists(file_path):
                    logger.info(f"✅ File exists at: {file_path}")
                else:
                    logger.error(f"❌ File does NOT exist at: {file_path}")
                    return Response({
                        'success': False,
                        'error': 'File was saved but cannot be found on server'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
                return Response({
                    'success': True,
                    'picture_url': picture_url,
                    'relative_url': relative_url,
                    'filename': filename,
                    'message': 'Profile picture uploaded successfully'
                })
            else:
                raise Exception('Profile picture was not saved correctly')
            
        except Exception as e:
            logger.error(f"❌ Profile picture upload error: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class Base64ImageUploadView(APIView):
    """
    Upload profile picture using base64 encoded string
    (Alternative for when FormData/multipart isn't available)
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        try:
            user = request.user
            profile = user.profile
            
            logger.info(f"📸 Uploading base64 profile picture for user: {user.username}")
            
            base64_string = request.data.get('image_base64')
            if not base64_string:
                return Response({
                    'success': False,
                    'error': 'No base64 image data provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if it's a data URL (starts with data:image/)
            if base64_string.startswith('data:image/'):
                # Extract the base64 part
                format, imgstr = base64_string.split(';base64,')
                ext = format.split('/')[-1]
            else:
                # Assume it's raw base64
                imgstr = base64_string
                ext = 'jpg'  # default extension
            
            # Decode base64 string
            try:
                image_data = base64.b64decode(imgstr)
            except Exception:
                return Response({
                    'success': False,
                    'error': 'Invalid base64 image data'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Generate unique filename
            filename = f"profile_{user.id}_{uuid.uuid4().hex[:8]}.{ext}"
            
            # Create ContentFile from decoded data
            image_file = ContentFile(image_data, name=filename)
            
            # Save to profile
            profile.profile_picture.save(filename, image_file)
            profile.save()
            
            # Get the URL
            picture_url = request.build_absolute_uri(profile.profile_picture.url)
            
            logger.info(f"✅ Base64 profile picture uploaded: {picture_url}")
            
            return Response({
                'success': True,
                'picture_url': picture_url,
                'filename': filename,
                'message': 'Profile picture uploaded successfully'
            })
            
        except Exception as e:
            logger.error(f"❌ Base64 image upload error: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        
@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint to test if server is running and media files are accessible
    """
    try:
        # Test media directory
        import os
        media_root = settings.MEDIA_ROOT
        media_exists = os.path.exists(media_root)
        
        # Test database connection
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_ok = True
            
        return Response({
            'status': 'healthy',
            'server_time': timezone.now().isoformat(),
            'debug': settings.DEBUG,
            'media_root': media_root,
            'media_exists': media_exists,
            'media_url': settings.MEDIA_URL,
            'database': 'connected' if db_ok else 'disconnected',
        })
    except Exception as e:
        return Response({
            'status': 'unhealthy',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def test_media(request):
    """
    Test if media files are being served correctly
    """
    try:
        # List files in media directory
        import os
        media_path = settings.MEDIA_ROOT
        profile_pics_path = os.path.join(media_path, 'profile_pics')
        
        files = []
        if os.path.exists(profile_pics_path):
            for filename in os.listdir(profile_pics_path):
                file_path = os.path.join(profile_pics_path, filename)
                if os.path.isfile(file_path):
                    files.append({
                        'name': filename,
                        'path': file_path,
                        'url': f"{settings.MEDIA_URL}profile_pics/{filename}",
                        'size': os.path.getsize(file_path),
                        'exists': os.path.exists(file_path),
                    })
        
        return Response({
            'media_root': media_path,
            'profile_pics_path': profile_pics_path,
            'profile_pics_exists': os.path.exists(profile_pics_path),
            'files': files,
            'test_url': f"http://{request.get_host()}{settings.MEDIA_URL}profile_pics/" if files else None,
        })
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

class DeleteProfilePictureView(APIView):
    """
    Delete old profile picture from server
    """
    permission_classes = [IsAuthenticated]
    
    def delete(self, request):
        try:
            filename = request.GET.get('filename')
            if not filename:
                return Response({
                    'success': False,
                    'error': 'No filename provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Security check: ensure it's a profile picture
            if not filename.startswith('profile_'):
                return Response({
                    'success': False,
                    'error': 'Invalid filename'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get the user's current profile
            user = request.user
            profile = user.profile
            
            # Check if this is the current user's picture
            current_filename = None
            if profile.profile_picture:
                current_parts = profile.profile_picture.name.split('/')
                if len(current_parts) > 0:
                    current_filename = current_parts[-1]
            
            # Only delete if it's not the current picture
            if filename != current_filename:
                # Construct file path
                file_path = os.path.join(settings.MEDIA_ROOT, 'profile_pics', filename)
                
                # Check if file exists
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"🗑️ Deleted old profile picture: {filename}")
                    return Response({
                        'success': True,
                        'message': f'Deleted {filename}'
                    })
                else:
                    return Response({
                        'success': False,
                        'error': 'File not found'
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                return Response({
                    'success': False,
                    'error': 'Cannot delete current profile picture'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"❌ Error deleting profile picture: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        
class UploadAndSyncProfilePicture(APIView):
    """
    Upload profile picture and immediately sync to profile
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        try:
            user = request.user
            profile = user.profile
            
            logger.info(f"📸 Uploading and syncing profile picture for user: {user.username}")
            
            if 'profile_picture' not in request.FILES:
                return Response({
                    'success': False,
                    'error': 'No image file provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            image_file = request.FILES['profile_picture']
            
            # Validate file type
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if image_file.content_type not in allowed_types:
                return Response({
                    'success': False,
                    'error': f'Invalid file type: {image_file.content_type}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate file size (max 5MB)
            max_size = 5 * 1024 * 1024
            if image_file.size > max_size:
                return Response({
                    'success': False,
                    'error': 'File too large. Maximum size is 5MB'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Generate unique filename
            file_extension = image_file.name.split('.')[-1]
            filename = f"{user.id}_{uuid.uuid4().hex[:8]}.{file_extension}"
            
            # Save the file
            profile.profile_picture.save(filename, image_file)
            profile.save()
            
            # Get the absolute URL
            if profile.profile_picture:
                if hasattr(settings, 'MEDIA_URL') and settings.MEDIA_URL:
                    picture_url = f"http://{request.get_host()}{settings.MEDIA_URL}profile_pics/{filename}"
                else:
                    picture_url = f"http://{request.get_host()}/media/profile_pics/{filename}"
                
                logger.info(f"✅ Profile picture uploaded: {picture_url}")
                
                return Response({
                    'success': True,
                    'profile_picture': picture_url,
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'profile_picture': picture_url
                    },
                    'message': 'Profile picture uploaded and synced successfully'
                })
            else:
                raise Exception('Profile picture was not saved correctly')
            
        except Exception as e:
            logger.error(f"❌ Profile picture upload error: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

# Add this helper function
def get_absolute_media_url(request, relative_path):
    """
    Convert relative media URL to absolute URL
    """
    if not relative_path:
        return None
    
    if relative_path.startswith('http://') or relative_path.startswith('https://'):
        return relative_path
    
    # Build absolute URL using request
    return request.build_absolute_uri(relative_path)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sync_user_data(request):
    """Return only data relevant to the requesting user"""
    try:
        user = request.user
        response_data = {
            'users': [],
            'permissions': [],
            'roles': [],
            'employees': []
        }
        
        # 1. Get the current user's data
        user_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
            'last_login': user.last_login,
            'date_joined': user.date_joined,
            'user_type': user.profile.user_type,
            'phone_number': user.profile.phone_number,
            'date_of_birth': user.profile.date_of_birth,
            'profile_picture': user.profile.profile_picture.url if user.profile.profile_picture else None,
            'is_verified': user.profile.is_verified,
        }
        response_data['users'].append(user_data)
        
        # 2. Get user's businesses and their employees
        from shops.models import Business, Employee, Shop
        
        # Get businesses owned by user
        owned_businesses = Business.objects.filter(owner=user, is_active=True)
        
        # Get businesses where user is employed
        employed_businesses = Employee.objects.filter(
            user=user, is_active=True
        ).values_list('business', flat=True)
        
        all_business_ids = list(owned_businesses.values_list('id', flat=True)) + list(employed_businesses)
        
        # Get all employees in user's businesses
        employees = Employee.objects.filter(
            business__id__in=all_business_ids,
            is_active=True
        ).select_related('user', 'shop', 'role')
        
        for emp in employees:
            # Add employee user to users list
            if emp.user.id != user.id:
                emp_user_data = {
                    'id': emp.user.id,
                    'username': emp.user.username,
                    'email': emp.user.email,
                    'first_name': emp.user.first_name,
                    'last_name': emp.user.last_name,
                    'is_active': emp.user.is_active,
                    'user_type': emp.user.profile.user_type,
                    'phone_number': emp.user.profile.phone_number,
                    'profile_picture': emp.user.profile.profile_picture.url if emp.user.profile.profile_picture else None,
                    'is_verified': emp.user.profile.is_verified,
                }
                response_data['users'].append(emp_user_data)
            
            # Add employee assignment
            emp_data = {
                'id': emp.id,
                'user_id': emp.user.id,
                'business_id': emp.business.id if emp.business else None,
                'shop_id': emp.shop.id if emp.shop else None,
                'role_id': emp.role.id if emp.role else None,
                'is_active': emp.is_active,
                'employment_date': emp.employment_date,
                'termination_date': emp.termination_date,
                'created_at': emp.created_at,
                'updated_at': emp.updated_at,
            }
            response_data['employees'].append(emp_data)
        
        # 3. Get permissions and roles (all of them for now)
        permissions = Permission.objects.filter(is_active=True).values(
            'id', 'code', 'name', 'description', 'category', 'is_active', 'created_at'
        )
        response_data['permissions'] = list(permissions)
        
        roles = Role.objects.all().values(
            'id', 'name', 'role_type', 'description', 'is_default', 'created_at', 'updated_at'
        )
        response_data['roles'] = list(roles)
        
        return Response({
            'success': True,
            'data': response_data,
            'message': 'User-specific data retrieved successfully'
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)
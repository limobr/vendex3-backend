from datetime import timedelta

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
import logging
from .models import Business, Shop, Employee
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.hashers import make_password
from .serializers import EmployeeCreateSerializer
from django.db import transaction
from accounts.models import Role, UserProfile
from accounts.utils import (
    generate_verification_code,
    notify_employee_invited,
    notify_invite_resent,
    notify_role_changed,
)
from django.contrib.auth.models import User
import secrets
import re
import threading

logger = logging.getLogger(__name__)

# shops/views.py - Update BusinessCreateView
class BusinessCreateView(APIView):
    """
    Create a new business
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            data = request.data
            
            logger.info(f"🏢 Creating business for user: {user.username}")
            
            # Validate required fields
            required_fields = ['name']
            for field in required_fields:
                if field not in data or not data[field]:
                    return Response({
                        'success': False,
                        'error': f'{field.replace("_", " ").title()} is required'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create business
            business = Business.objects.create(
                owner=user,
                name=data['name'],
                registration_number=data.get('registration_number', ''),
                phone_number=data.get('phone_number', ''),
                email=data.get('email', ''),
                address=data.get('address', ''),
                is_active=True
            )
            
            # Return business data
            return Response({
                'success': True,
                'business': {
                    'id': str(business.id),
                    'name': business.name,
                    'registration_number': business.registration_number,
                    'phone_number': business.phone_number,
                    'email': business.email,
                    'address': business.address,
                    'is_active': business.is_active,
                    'created_at': business.created_at.isoformat(),
                    'updated_at': business.updated_at.isoformat()
                },
                'message': 'Business created successfully'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"❌ Error creating business: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

class BusinessUpdateView(APIView):
    """
    Update an existing business
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, business_id):
        try:
            user = request.user
            data = request.data
            
            logger.info(f"📝 Updating business {business_id} for user: {user.username}")
            
            # Get business (ensure user owns it)
            business = get_object_or_404(Business, id=business_id, owner=user)
            
            # Update fields
            update_fields = ['name', 'registration_number', 'phone_number', 'email', 'address', 'is_active']
            for field in update_fields:
                if field in data:
                    setattr(business, field, data[field])
            
            business.updated_at = timezone.now()
            business.save()
            
            return Response({
                'success': True,
                'business': {
                    'id': business.id,
                    'name': business.name,
                    'registration_number': business.registration_number,
                    'phone_number': business.phone_number,
                    'email': business.email,
                    'address': business.address,
                    'is_active': business.is_active,
                    'created_at': business.created_at,
                    'updated_at': business.updated_at
                },
                'message': 'Business updated successfully'
            })
            
        except Exception as e:
            logger.error(f"❌ Error updating business: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class BusinessDeleteView(APIView):
    """
    Delete a business (soft delete)
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, business_id):
        try:
            user = request.user
            
            logger.info(f"🗑️ Deleting business {business_id} for user: {user.username}")
            
            # Get business (ensure user owns it)
            business = get_object_or_404(Business, id=business_id, owner=user)
            
            # Soft delete
            business.is_active = False
            business.updated_at = timezone.now()
            business.save()
            
            return Response({
                'success': True,
                'message': 'Business deleted successfully'
            })
            
        except Exception as e:
            logger.error(f"❌ Error deleting business: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class BusinessListView(APIView):
    """
    Get all businesses for current user
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            
            logger.info(f"📋 Getting businesses for user: {user.username}")
            
            businesses = Business.objects.filter(owner=user, is_active=True)
            
            business_list = []
            for business in businesses:
                # Get shop count
                shop_count = Shop.objects.filter(business=business, is_active=True).count()
                
                business_list.append({
                    'id': business.id,
                    'name': business.name,
                    'registration_number': business.registration_number,
                    'phone_number': business.phone_number,
                    'email': business.email,
                    'address': business.address,
                    'shop_count': shop_count,
                    'created_at': business.created_at,
                    'updated_at': business.updated_at
                })
            
            return Response({
                'success': True,
                'businesses': business_list,
                'count': len(business_list)
            })
            
        except Exception as e:
            logger.error(f"❌ Error getting businesses: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class BusinessSyncView(APIView):
    """
    Sync business data from mobile app
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            data = request.data
            
            logger.info(f"🔄 Syncing business data for user: {user.username}")
            
            operations = data.get('operations', [])
            synced_items = []
            
            for operation in operations:
                try:
                    op_type = operation.get('type')
                    table = operation.get('table')
                    local_id = operation.get('local_id')
                    item_data = operation.get('data', {})
                    
                    if table == 'businesses':
                        if op_type == 'create':
                            # Create new business
                            business = Business.objects.create(
                                owner=user,
                                name=item_data.get('name', ''),
                                registration_number=item_data.get('registration_number', ''),
                                phone_number=item_data.get('phone_number', ''),
                                email=item_data.get('email', ''),
                                address=item_data.get('address', ''),
                                is_active=item_data.get('is_active', True)
                            )
                            
                            synced_items.append({
                                'table': 'businesses',
                                'local_id': local_id,
                                'server_id': str(business.id),
                                'success': True
                            })
                            
                        elif op_type == 'update':
                            # Update existing business
                            business = get_object_or_404(
                                Business, 
                                id=item_data.get('server_id'), 
                                owner=user
                            )
                            
                            update_fields = ['name', 'registration_number', 'phone_number', 'email', 'address', 'is_active']
                            for field in update_fields:
                                if field in item_data:
                                    setattr(business, field, item_data[field])
                            
                            business.updated_at = timezone.now()
                            business.save()
                            
                            synced_items.append({
                                'table': 'businesses',
                                'local_id': local_id,
                                'server_id': str(business.id),
                                'success': True
                            })
                            
                        elif op_type == 'delete':
                            # Soft delete business
                            business = get_object_or_404(
                                Business, 
                                id=item_data.get('server_id'), 
                                owner=user
                            )
                            
                            business.is_active = False
                            business.save()
                            
                            synced_items.append({
                                'table': 'businesses',
                                'local_id': local_id,
                                'server_id': str(business.id),
                                'success': True
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
            logger.error(f"❌ Business sync error: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


# shops/views.py - Updated UserBusinessDataView
class UserBusinessDataView(APIView):
    """
    Get all business data for user (for initial app load)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            
            logger.info(f"📥 Getting all business data for user: {user.username}")
            
            # Get all businesses
            businesses = Business.objects.filter(owner=user, is_active=True)
            business_list = []
            
            for business in businesses:
                business_list.append({
                    'id': str(business.id),
                    'name': business.name,
                    'registration_number': business.registration_number or '',
                    'phone_number': business.phone_number or '',
                    'email': business.email or '',
                    'address': business.address or '',
                    'is_active': business.is_active,
                    'created_at': business.created_at.isoformat(),
                    'updated_at': business.updated_at.isoformat(),
                })
            
            # Get all shops for these businesses
            shops = Shop.objects.filter(business__owner=user, is_active=True)
            shop_list = []
            
            for shop in shops:
                shop_list.append({
                    'id': str(shop.id),
                    'business_id': str(shop.business.id),
                    'name': shop.name,
                    'shop_type': shop.shop_type,
                    'location': shop.location or '',
                    'phone_number': shop.phone_number or '',
                    'email': shop.email or '',
                    'tax_rate': float(shop.tax_rate),
                    'currency': shop.currency,
                    'is_active': shop.is_active,
                    'created_at': shop.created_at.isoformat(),
                    'updated_at': shop.updated_at.isoformat(),
                })
            
            return Response({
                'success': True,
                'businesses': business_list,
                'shops': shop_list,
                'sync_timestamp': timezone.now().isoformat(),
                'message': f'Found {len(business_list)} businesses and {len(shop_list)} shops'
            })
            
        except Exception as e:
            logger.error(f"❌ Error getting business data: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)        

# shops

# shops/views.py (add these after Business views)
class ShopCreateView(APIView):
    """
    Create a new shop for a business
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            data = request.data
            
            logger.info(f"🏪 Creating shop for user: {user.username}")
            
            # Validate required fields
            required_fields = ['business_id', 'name', 'shop_type', 'location']
            for field in required_fields:
                if field not in data or not data[field]:
                    return Response({
                        'success': False,
                        'error': f'{field.replace("_", " ").title()} is required'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get business (ensure user owns it)
            business = get_object_or_404(Business, id=data['business_id'], owner=user)
            
            # Check if shop with same name already exists for this business
            if Shop.objects.filter(business=business, name=data['name'], is_active=True).exists():
                return Response({
                    'success': False,
                    'error': 'A shop with this name already exists in this business'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create shop
            shop = Shop.objects.create(
                business=business,
                name=data['name'],
                shop_type=data['shop_type'],
                location=data['location'],
                phone_number=data.get('phone_number', ''),
                email=data.get('email', ''),
                tax_rate=data.get('tax_rate', 0.0),
                currency=data.get('currency', 'KES'),
                is_active=True
            )
            
            # Return shop data
            return Response({
                'success': True,
                'shop': {
                    'id': shop.id,
                    'business_id': str(shop.business.id),
                    'name': shop.name,
                    'shop_type': shop.shop_type,
                    'location': shop.location,
                    'phone_number': shop.phone_number,
                    'email': shop.email,
                    'tax_rate': float(shop.tax_rate),
                    'currency': shop.currency,
                    'is_active': shop.is_active,
                    'created_at': shop.created_at,
                    'updated_at': shop.updated_at
                },
                'message': 'Shop created successfully'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"❌ Error creating shop: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class ShopUpdateView(APIView):
    """
    Update an existing shop
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, shop_id):
        try:
            user = request.user
            data = request.data
            
            logger.info(f"📝 Updating shop {shop_id} for user: {user.username}")
            
            # Get shop (ensure user owns the business)
            shop = get_object_or_404(Shop, id=shop_id, business__owner=user)
            
            # Update fields
            update_fields = ['name', 'shop_type', 'location', 'phone_number', 'email', 
                           'tax_rate', 'currency', 'is_active']
            for field in update_fields:
                if field in data:
                    if field == 'tax_rate' and data[field] is not None:
                        setattr(shop, field, float(data[field]))
                    else:
                        setattr(shop, field, data[field])
            
            shop.updated_at = timezone.now()
            shop.save()
            
            return Response({
                'success': True,
                'shop': {
                    'id': shop.id,
                    'business_id': str(shop.business.id),
                    'name': shop.name,
                    'shop_type': shop.shop_type,
                    'location': shop.location,
                    'phone_number': shop.phone_number,
                    'email': shop.email,
                    'tax_rate': float(shop.tax_rate),
                    'currency': shop.currency,
                    'is_active': shop.is_active,
                    'created_at': shop.created_at,
                    'updated_at': shop.updated_at
                },
                'message': 'Shop updated successfully'
            })
            
        except Exception as e:
            logger.error(f"❌ Error updating shop: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class ShopDeleteView(APIView):
    """
    Delete a shop (soft delete)
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, shop_id):
        try:
            user = request.user
            
            logger.info(f"🗑️ Deleting shop {shop_id} for user: {user.username}")
            
            # Get shop (ensure user owns the business)
            shop = get_object_or_404(Shop, id=shop_id, business__owner=user)
            
            # Soft delete
            shop.is_active = False
            shop.updated_at = timezone.now()
            shop.save()
            
            return Response({
                'success': True,
                'message': 'Shop deleted successfully'
            })
            
        except Exception as e:
            logger.error(f"❌ Error deleting shop: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class ShopListView(APIView):
    """
    Get all shops for a business
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            business_id = request.query_params.get('business_id')
            
            if not business_id:
                return Response({
                    'success': False,
                    'error': 'business_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            logger.info(f"📋 Getting shops for business {business_id} and user: {user.username}")
            
            # Get business (ensure user owns it)
            business = get_object_or_404(Business, id=business_id, owner=user)
            
            shops = Shop.objects.filter(business=business, is_active=True)
            
            shop_list = []
            for shop in shops:
                # Get employee count
                employee_count = Employee.objects.filter(shop=shop, is_active=True).count()
                
                shop_list.append({
                    'id': shop.id,
                    'business_id': str(shop.business.id),
                    'name': shop.name,
                    'shop_type': shop.shop_type,
                    'location': shop.location,
                    'phone_number': shop.phone_number,
                    'email': shop.email,
                    'tax_rate': float(shop.tax_rate),
                    'currency': shop.currency,
                    'employee_count': employee_count,
                    'created_at': shop.created_at,
                    'updated_at': shop.updated_at
                })
            
            return Response({
                'success': True,
                'shops': shop_list,
                'count': len(shop_list)
            })
            
        except Exception as e:
            logger.error(f"❌ Error getting shops: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class ShopDetailView(APIView):
    """
    Get details of a specific shop
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, shop_id):
        try:
            user = request.user
            
            logger.info(f"🔍 Getting details for shop {shop_id} for user: {user.username}")
            
            # Get shop (ensure user owns the business)
            shop = get_object_or_404(Shop, id=shop_id, business__owner=user)
            
            # Get employee count
            employee_count = Employee.objects.filter(shop=shop, is_active=True).count()
            
            # Get business info
            business = shop.business
            
            return Response({
                'success': True,
                'shop': {
                    'id': shop.id,
                    'business_id': str(shop.business.id),
                    'name': shop.name,
                    'shop_type': shop.shop_type,
                    'location': shop.location,
                    'phone_number': shop.phone_number,
                    'email': shop.email,
                    'tax_rate': float(shop.tax_rate),
                    'currency': shop.currency,
                    'is_active': shop.is_active,
                    'employee_count': employee_count,
                    'business_name': business.name,
                    'created_at': shop.created_at,
                    'updated_at': shop.updated_at
                }
            })
            
        except Exception as e:
            logger.error(f"❌ Error getting shop details: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        

# Employee Management Views
class RoleListView(APIView):
    """
    Get all available roles for employee assignment
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # CHANGE THIS: Remove is_active filter since Role model doesn't have that field
            roles = Role.objects.all()  # Changed from Role.objects.filter(is_active=True)
            
            role_list = []
            for role in roles:
                role_list.append({
                    'id': str(role.id),
                    'name': role.name,
                    'role_type': role.role_type,
                    'description': role.description,
                    'is_default': role.is_default,
                    'created_at': role.created_at
                })
            
            return Response({
                'success': True,
                'roles': role_list
            })
            
        except Exception as e:
            logger.error(f"❌ Error getting roles: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

class EmployeeCreateView(APIView):
    """
    Create a new employee and send login credentials via email
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            print("📨 Request data:", request.data)
            print("📨 User:", request.user.id)

            # Log the raw role_id value for debugging
            if 'role_id' in request.data:
                print(f"📝 Raw role_id from request: {request.data['role_id']} (type: {type(request.data['role_id'])}")

            serializer = EmployeeCreateSerializer(data=request.data)

            if not serializer.is_valid():
                print("❌ Serializer errors:", serializer.errors)
                return Response({
                    'success': False,
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

            data = serializer.validated_data
            user = request.user
            print("✅ Validated data:", data)

            # Get shop and verify ownership
            try:
                shop = Shop.objects.get(id=data['shop_id'], business__owner=user)
                print(f"✅ Shop found: {shop.name}")
            except Shop.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Shop not found or you do not have permission'
                }, status=status.HTTP_404_NOT_FOUND)

            # Get role with improved error handling
            try:
                role_id = data['role_id']
                print(f"🔍 Looking for role with UUID: {role_id}")

                # Handle UUID format variations
                if isinstance(role_id, str):
                    role_id_str = role_id.replace('-', '')
                    if len(role_id_str) == 32:  # UUID without hyphens
                        formatted_uuid = f"{role_id_str[:8]}-{role_id_str[8:12]}-{role_id_str[12:16]}-{role_id_str[16:20]}-{role_id_str[20:]}"
                        role = Role.objects.get(id=formatted_uuid)
                    else:
                        role = Role.objects.get(id=role_id)
                else:
                    role = Role.objects.get(id=role_id)

                print(f"✅ Role found: {role.name} (ID: {role.id})")
            except Role.DoesNotExist:
                print(f"❌ Role not found with ID: {data['role_id']}")
                available_roles = list(Role.objects.all().values('id', 'name'))
                print(f"📋 Available roles: {available_roles}")
                return Response({
                    'success': False,
                    'error': f'Role not found. Available roles: {available_roles}'
                }, status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                print(f"❌ Error getting role: {str(e)}")
                return Response({
                    'success': False,
                    'error': f'Invalid role ID format: {str(e)}'
                }, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                # Check if user with email already exists
                existing_user = User.objects.filter(email__iexact=data['email']).first()

                if existing_user:
                    # Check if employee already exists for this shop
                    if Employee.objects.filter(user=existing_user, shop=shop, is_active=True).exists():
                        return Response({
                            'success': False,
                            'error': 'This employee is already assigned to this shop'
                        }, status=status.HTTP_400_BAD_REQUEST)

                    # Use existing user
                    employee_user = existing_user
                    temporary_password = None
                    password_expiry = None

                    # Ensure profile exists
                    if not hasattr(employee_user, 'profile'):
                        UserProfile.objects.create(user=employee_user)
                        print(f"✅ Created profile for existing user")
                else:
                    # Create new user with temporary password
                    temporary_password = serializer.generate_temporary_password()
                    # Create a username from email
                    email_prefix = data['email'].split('@')[0]
                    clean_prefix = re.sub(r'[^a-zA-Z0-9]', '', email_prefix)[:20]
                    username = clean_prefix + str(secrets.randbelow(1000))

                    print(f"✅ Creating new user with username: {username}")

                    employee_user = User.objects.create(
                        username=username,
                        email=data['email'],
                        first_name=data['first_name'],
                        last_name=data['last_name'],
                        is_active=True
                    )
                    employee_user.set_password(temporary_password)
                    employee_user.save()

                    # Update user profile with phone number
                    profile = employee_user.profile
                    if data.get('phone_number'):
                        profile.phone_number = data['phone_number']
                        profile.save()
                        print(f"✅ Set phone number: {data['phone_number']}")

                    # Set password expiry to 24 hours from now
                    password_expiry = timezone.now() + timedelta(hours=24)

                # Create employee record with temporary password and expiry (if any)
                employee = Employee.objects.create(
                    user=employee_user,
                    shop=shop,
                    role=role,
                    is_active=True,
                    employment_type=data.get('employment_type', 'full_time'),
                    salary=data.get('salary'),
                    temporary_password=temporary_password,
                    password_expiry=password_expiry
                )

                # Generate and store verification code (valid 30 minutes)
                if temporary_password:
                    v_code = generate_verification_code()
                    employee.verification_code = v_code
                    employee.verification_code_expiry = timezone.now() + timedelta(minutes=30)
                    employee.save(update_fields=['verification_code', 'verification_code_expiry'])

                # Notify owner about the new invite
                notify_employee_invited(employee, shop.business)

                print(f"✅ Employee record created with ID: {employee.id}")

                # Send credentials email if requested and temporary password exists
                if data.get('send_credentials', True) and temporary_password:
                    self.send_employee_credentials_async(
                        employee_user,
                        temporary_password,
                        shop,
                        role,
                        user  # Shop owner
                    )

                # Prepare response data
                employee_data = {
                    'success': True,
                    'employee': {
                        'id': str(employee.id),
                        'user': {
                            'id': employee_user.id,
                            'first_name': employee_user.first_name,
                            'last_name': employee_user.last_name,
                            'email': employee_user.email,
                            'phone_number': employee_user.profile.phone_number if hasattr(employee_user, 'profile') else ''
                        },
                        'shop': {
                            'id': str(shop.id),
                            'name': shop.name,
                            'business_name': shop.business.name
                        },
                        'role': {
                            'id': str(role.id),
                            'name': role.name,
                            'type': role.role_type
                        },
                        'employment_type': employee.employment_type,
                        'salary': float(employee.salary) if employee.salary else None,
                        'employment_date': employee.employment_date,
                        'created_at': employee.created_at,
                        'message': 'New account created' if temporary_password else 'Existing user assigned'
                    },
                    'message': 'Employee added successfully.' + (' Login credentials have been sent via email.' if temporary_password else '')
                }

                print(f"✅ Response prepared, sending...")

                return Response(employee_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"❌ Error creating employee: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    def send_employee_credentials_async(self, employee_user, temporary_password, shop, role, owner):
        """
        Send credentials email in a background thread to avoid blocking the request.
        """
        def send_email_thread():
            try:
                from django.core.mail import EmailMultiAlternatives

                subject = f"Welcome to {shop.business.name} - Your Account Credentials"

                # HTML email template
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Welcome to {shop.business.name}</title>
                </head>
                <body>
                    <div style="max-width: 600px; margin: 0 auto; background: #ffffff; font-family: Arial, sans-serif;">
                        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px 30px; text-align: center;">
                            <div style="font-size: 24px; font-weight: 600; margin-bottom: 10px;">{shop.business.name}</div>
                            <div style="opacity: 0.9; font-size: 14px;">Employee Onboarding Portal</div>
                        </div>

                        <div style="padding: 40px 30px;">
                            <h2 style="font-size: 20px; font-weight: 600; color: #2d3748; margin-bottom: 25px;">
                                Welcome aboard, {employee_user.first_name}!
                            </h2>

                            <p>We're excited to have you join our team at <strong>{shop.business.name}</strong> as a <strong>{role.name}</strong>.</p>

                            <div style="background: #f8fafc; border-left: 4px solid #4299e1; padding: 20px; margin: 25px 0;">
                                <strong>📋 Your Assignment Details</strong><br><br>
                                <strong>Shop:</strong> {shop.name}<br>
                                <strong>Role:</strong> {role.name}<br>
                                <strong>Onboarding Manager:</strong> {owner.get_full_name() or owner.username}
                            </div>

                            <div style="background: #ebf8ff; border: 1px solid #bee3f8; border-radius: 8px; padding: 25px; margin: 25px 0;">
                                <strong>🔐 Account Credentials</strong>
                                <p>Use these credentials to access your account:</p>

                                <div style="display: flex; align-items: center; margin-bottom: 15px;">
                                    <span style="width: 20px; margin-right: 12px;">📧</span>
                                    <div>
                                        <strong>Email Address:</strong><br>
                                        {employee_user.email}
                                    </div>
                                </div>

                                <div style="display: flex; align-items: center; margin-bottom: 15px;">
                                    <span style="width: 20px; margin-right: 12px;">🔑</span>
                                    <div>
                                        <strong>Temporary Password:</strong><br>
                                        <div style="display: inline-block; background: #2d3748; color: #68d391; font-family: 'Courier New', monospace; font-size: 18px; font-weight: 600; padding: 12px 20px; border-radius: 6px; letter-spacing: 1px; margin: 10px 0;">
                                            {temporary_password}
                                        </div>
                                        <small style="color: #718096;">Valid for 24 hours</small>
                                    </div>
                                </div>
                            </div>

                            <div style="background: #fff5f5; border: 1px solid #fc8181; border-left: 4px solid #e53e3e; color: #c53030; padding: 18px; border-radius: 0 4px 4px 0; margin: 25px 0; font-size: 14px;">
                                ⚠️ <strong>Security Notice:</strong> For your protection, please change your password immediately after logging in for the first time. Do not share these credentials with anyone.
                            </div>

                            <div style="margin: 30px 0;">
                                <strong>🚀 Getting Started</strong>
                                <div style="display: flex; margin-bottom: 20px;">
                                    <div style="background: #4299e1; color: white; width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 15px; flex-shrink: 0; font-weight: 600;">1</div>
                                    <div>Download the ShopSync app from your device's app store</div>
                                </div>
                                <div style="display: flex; margin-bottom: 20px;">
                                    <div style="background: #4299e1; color: white; width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 15px; flex-shrink: 0; font-weight: 600;">2</div>
                                    <div>Open the app and tap "Login"</div>
                                </div>
                                <div style="display: flex; margin-bottom: 20px;">
                                    <div style="background: #4299e1; color: white; width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 15px; flex-shrink: 0; font-weight: 600;">3</div>
                                    <div>Enter your email and temporary password</div>
                                </div>
                                <div style="display: flex; margin-bottom: 20px;">
                                    <div style="background: #4299e1; color: white; width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 15px; flex-shrink: 0; font-weight: 600;">4</div>
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

                # Plain text fallback
                plain_text = f"""
WELCOME TO {shop.business.name.upper()}

Hello {employee_user.first_name} {employee_user.last_name},

Welcome to {shop.business.name}! You have been added as a {role.name} at {shop.name}.

YOUR ACCOUNT CREDENTIALS:
Email: {employee_user.email}
Temporary Password: {temporary_password}
(Valid for 24 hours)

GETTING STARTED:
1. Download the ShopSync mobile app
2. Open the app and tap "Login"
3. Enter your email and temporary password
4. Create a new secure password when prompted

IMPORTANT SECURITY:
• Change your password immediately after first login
• Do not share your credentials with anyone

Best regards,
{shop.business.name} Management Team
"""

                # Send email with both HTML and plain text versions
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=plain_text,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[employee_user.email],
                )
                email.attach_alternative(html_content, "text/html")
                email.send()

                logger.info(f"✅ Professional onboarding email sent to {employee_user.email} in background")

            except Exception as e:
                logger.error(f"❌ Background email sending failed: {str(e)}")
                # Don't re-raise, as this is a background task

        # Start the email sending in a separate thread
        thread = threading.Thread(target=send_email_thread)
        thread.daemon = True  # Allows the thread to exit when main process ends
        thread.start()
        logger.info(f"📧 Queued credentials email for {employee_user.email}")



class EmployeeListView(APIView):
    """
    Get all employees for a shop
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            shop_id = request.query_params.get('shop_id')
            business_id = request.query_params.get('business_id')
            
            if not shop_id and not business_id:
                return Response({
                    'success': False,
                    'error': 'Either shop_id or business_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get employees based on shop or business
            if shop_id:
                # Verify shop ownership
                shop = get_object_or_404(Shop, id=shop_id, business__owner=request.user)
                employees = Employee.objects.filter(shop=shop, is_active=True)
            else:
                # Verify business ownership
                business = get_object_or_404(Business, id=business_id, owner=request.user)
                employees = Employee.objects.filter(shop__business=business, is_active=True)
            
            employee_list = []
            for emp in employees.select_related('user', 'role', 'shop', 'shop__business'):
                employee_list.append({
                    'id': str(emp.id),
                    'user': {
                        'id': emp.user.id,
                        'first_name': emp.user.first_name,
                        'last_name': emp.user.last_name,
                        'email': emp.user.email,
                        'phone_number': emp.user.profile.phone_number,
                        'is_active': emp.user.is_active
                    },
                    'shop': {
                        'id': str(emp.shop.id),
                        'name': emp.shop.name,
                        'location': emp.shop.location
                    },
                    'business': {
                        'id': str(emp.shop.business.id),
                        'name': emp.shop.business.name
                    },
                    'role': {
                        'id': str(emp.role.id),
                        'name': emp.role.name,
                        'type': emp.role.role_type
                    },
                    'employment_type': emp.employment_type,
                    'salary': float(emp.salary) if emp.salary else None,
                    'employment_date': emp.employment_date,
                    'created_at': emp.created_at,
                    'is_active': emp.is_active
                })
            
            return Response({
                'success': True,
                'employees': employee_list,
                'count': len(employee_list)
            })
            
        except Exception as e:
            logger.error(f"❌ Error getting employees: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class EmployeeDetailView(APIView):
    """
    Get, update, or delete an employee
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id):
        try:
            employee = get_object_or_404(
                Employee, 
                id=employee_id, 
                shop__business__owner=request.user
            )
            
            return Response({
                'success': True,
                'employee': {
                    'id': str(employee.id),
                    'user': {
                        'id': employee.user.id,
                        'first_name': employee.user.first_name,
                        'last_name': employee.user.last_name,
                        'email': employee.user.email,
                        'phone_number': employee.user.profile.phone_number,
                        'is_active': employee.user.is_active
                    },
                    'shop': {
                        'id': str(employee.shop.id),
                        'name': employee.shop.name,
                        'location': employee.shop.location
                    },
                    'business': {
                        'id': str(employee.shop.business.id),
                        'name': employee.shop.business.name
                    },
                    'role': {
                        'id': str(employee.role.id),
                        'name': employee.role.name,
                        'type': employee.role.role_type
                    },
                    'employment_type': employee.employment_type,
                    'salary': float(employee.salary) if employee.salary else None,
                    'employment_date': employee.employment_date,
                    'termination_date': employee.termination_date,
                    'created_at': employee.created_at,
                    'updated_at': employee.updated_at,
                    'is_active': employee.is_active
                }
            })
            
        except Exception as e:
            logger.error(f"❌ Error getting employee details: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, employee_id):
        try:
            employee = get_object_or_404(
                Employee, 
                id=employee_id, 
                shop__business__owner=request.user
            )
            
            data = request.data
            
            # Update employee fields
            if 'role_id' in data:
                old_role_name = employee.role.name
                role = get_object_or_404(Role, id=data['role_id'])
                employee.role = role
                # Notify employee of role change
                if old_role_name != role.name:
                    notify_role_changed(employee, old_role_name, role.name, employee.shop.business)
            
            if 'employment_type' in data:
                employee.employment_type = data['employment_type']
            
            if 'salary' in data:
                employee.salary = data['salary']
            
            if 'is_active' in data:
                employee.is_active = data['is_active']
                if not data['is_active']:
                    employee.termination_date = timezone.now().date()
            
            employee.save()
            
            return Response({
                'success': True,
                'employee': {
                    'id': str(employee.id),
                    'role': {
                        'id': str(employee.role.id),
                        'name': employee.role.name
                    },
                    'employment_type': employee.employment_type,
                    'salary': float(employee.salary) if employee.salary else None,
                    'is_active': employee.is_active,
                    'updated_at': employee.updated_at
                },
                'message': 'Employee updated successfully'
            })
            
        except Exception as e:
            logger.error(f"❌ Error updating employee: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, employee_id):
        try:
            employee = get_object_or_404(
                Employee, 
                id=employee_id, 
                shop__business__owner=request.user
            )
            
            # Soft delete
            employee.is_active = False
            employee.termination_date = timezone.now().date()
            employee.save()
            
            return Response({
                'success': True,
                'message': 'Employee removed successfully'
            })
            
        except Exception as e:
            logger.error(f"❌ Error removing employee: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class ResendEmployeeCredentialsView(APIView):
    """
    Resend login credentials to an employee
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, employee_id):
        try:
            employee = get_object_or_404(
                Employee, 
                id=employee_id, 
                shop__business__owner=request.user
            )
            
            # Generate new temporary password
            temporary_password = EmployeeCreateSerializer().generate_temporary_password()
            employee.user.set_password(temporary_password)
            employee.user.save()

            # Refresh verification code (valid 30 minutes)
            employee.temporary_password = temporary_password
            employee.password_expiry = timezone.now() + timedelta(hours=24)
            employee.verification_code = generate_verification_code()
            employee.verification_code_expiry = timezone.now() + timedelta(minutes=30)
            employee.is_invite_accepted = False
            employee.save()

            # Notify
            notify_invite_resent(employee, employee.shop.business)
            
            # Send credentials email
            EmployeeCreateView().send_employee_credentials_async(
                employee.user,
                temporary_password,
                employee.shop,
                employee.role,
                request.user
            )
            
            return Response({
                'success': True,
                'message': 'New credentials have been sent to the employee'
            })
            
        except Exception as e:
            logger.error(f"❌ Error resending credentials: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
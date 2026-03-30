# backend/health/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from django.utils import timezone
from django.db import connection
import psutil
import os
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class HealthCheckView(APIView):
    """
    Comprehensive health check endpoint that checks:
    - Database connectivity
    - Disk space
    - Memory usage
    - Server time
    - API status
    """
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            health_data = {
                'status': 'healthy',
                'timestamp': timezone.now().isoformat(),
                'services': {}
            }

            # Check database
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    health_data['services']['database'] = {
                        'status': 'healthy',
                        'message': 'Database connection successful'
                    }
            except Exception as e:
                health_data['services']['database'] = {
                    'status': 'unhealthy',
                    'message': f'Database error: {str(e)}'
                }
                health_data['status'] = 'unhealthy'

            # Check disk space
            try:
                disk = psutil.disk_usage('/')
                health_data['services']['disk'] = {
                    'status': 'healthy',
                    'total_gb': round(disk.total / (1024**3), 2),
                    'used_gb': round(disk.used / (1024**3), 2),
                    'free_gb': round(disk.free / (1024**3), 2),
                    'percent_used': disk.percent,
                    'message': f'{disk.free / (1024**3):.2f}GB free'
                }
                
                # Warning if disk is almost full
                if disk.percent > 90:
                    health_data['services']['disk']['status'] = 'warning'
                    health_data['services']['disk']['message'] = f'Disk space running low: {disk.percent}% used'
            except Exception as e:
                health_data['services']['disk'] = {
                    'status': 'unhealthy',
                    'message': f'Disk check failed: {str(e)}'
                }

            # Check memory
            try:
                memory = psutil.virtual_memory()
                health_data['services']['memory'] = {
                    'status': 'healthy',
                    'total_gb': round(memory.total / (1024**3), 2),
                    'available_gb': round(memory.available / (1024**3), 2),
                    'used_percent': memory.percent,
                    'message': f'{memory.percent}% used'
                }
                
                if memory.percent > 90:
                    health_data['services']['memory']['status'] = 'warning'
                    health_data['services']['memory']['message'] = f'Memory usage high: {memory.percent}% used'
            except Exception as e:
                health_data['services']['memory'] = {
                    'status': 'unhealthy',
                    'message': f'Memory check failed: {str(e)}'
                }

            # API version info
            health_data['api'] = {
                'version': '1.0.0',
                'name': 'Vendex POS API',
                'environment': settings.DEBUG and 'development' or 'production',
                'uptime': self.get_uptime()
            }

            # Authentication status (if authenticated)
            if request.user.is_authenticated:
                health_data['user'] = {
                    'id': request.user.id,
                    'username': request.user.username,
                    'authenticated': True
                }

            status_code = status.HTTP_200_OK if health_data['status'] == 'healthy' else status.HTTP_503_SERVICE_UNAVAILABLE
            
            return Response(health_data, status=status_code)
            
        except Exception as e:
            logger.error(f"Health check error: {str(e)}")
            return Response({
                'status': 'error',
                'message': f'Health check failed: {str(e)}',
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_uptime(self):
        """Get server uptime in human readable format"""
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
                days = uptime_seconds // (24 * 3600)
                hours = (uptime_seconds % (24 * 3600)) // 3600
                minutes = (uptime_seconds % 3600) // 60
                seconds = uptime_seconds % 60
                
                if days > 0:
                    return f"{int(days)}d {int(hours)}h {int(minutes)}m"
                elif hours > 0:
                    return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
                else:
                    return f"{int(minutes)}m {int(seconds)}s"
        except:
            return "unknown"


class ServerInfoView(APIView):
    """
    Server information and configuration endpoint
    """
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            info = {
                'server': {
                    'name': 'Vendex POS Backend',
                    'version': '1.0.0',
                    'framework': 'Django REST Framework',
                    'python_version': os.sys.version,
                    'django_version': self.get_django_version(),
                    'timezone': str(settings.TIME_ZONE),
                    'debug_mode': settings.DEBUG,
                    'allowed_hosts': settings.ALLOWED_HOSTS,
                    'cors_allowed_origins': getattr(settings, 'CORS_ALLOWED_ORIGINS', []),
                },
                'features': {
                    'authentication': True,
                    'jwt_tokens': True,
                    'database': True,
                    'file_uploads': True,
                    'cors_enabled': hasattr(settings, 'CORS_ALLOWED_ORIGINS'),
                    'offline_sync': True,
                    'backup_restore': True,
                },
                'endpoints': {
                    'auth': {
                        'login': '/auth/login/',
                        'register': '/auth/register/',
                        'refresh': '/auth/refresh/',
                        'logout': '/auth/logout/',
                    },
                    'health': {
                        'health_check': '/health/',
                        'server_info': '/health/info/',
                        'database_status': '/health/db/',
                    },
                    'sync': {
                        'sync_all': '/sync/all/',
                        'sync_products': '/sync/products/',
                        'sync_sales': '/sync/sales/',
                        'sync_customers': '/sync/customers/',
                    },
                    'api': {
                        'products': '/api/products/',
                        'sales': '/api/sales/',
                        'customers': '/api/customers/',
                        'shops': '/api/shops/',
                        'employees': '/api/employees/',
                    }
                },
                'limits': {
                    'max_upload_size': '10MB',
                    'rate_limit': '1000/hour per IP',
                    'max_offline_sales': 1000,
                    'backup_retention_days': 30,
                },
                'support': {
                    'documentation': 'https://docs.vendex.example.com',
                    'api_reference': 'https://api.vendex.example.com/docs',
                    'contact_email': 'support@vendex.example.com',
                    'emergency_contact': '+2547XXXXXXXX',
                },
                'timestamp': timezone.now().isoformat(),
            }
            
            return Response(info)
            
        except Exception as e:
            logger.error(f"Server info error: {str(e)}")
            return Response({
                'error': 'Failed to fetch server info',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_django_version(self):
        import django
        return django.get_version()


class DatabaseStatusView(APIView):
    """
    Database status and statistics
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            stats = {
                'tables': {},
                'connections': {},
                'performance': {}
            }

            # Get table counts
            from django.apps import apps
            from django.db.models import Count

            for model in apps.get_models():
                try:
                    table_name = model._meta.db_table
                    count = model.objects.count()
                    stats['tables'][table_name] = {
                        'count': count,
                        'last_updated': self.get_last_update_time(model)
                    }
                except Exception as e:
                    stats['tables'][table_name] = {
                        'error': str(e),
                        'count': 0
                    }

            # Get database connection info
            stats['connections'] = {
                'active': len(connection.queries) if hasattr(connection, 'queries') else 0,
                'max_connections': self.get_max_connections(),
                'queries_executed': len(connection.queries) if hasattr(connection, 'queries') else 0,
            }

            # Database performance metrics
            stats['performance'] = {
                'query_time': sum(float(q['time']) for q in connection.queries) if hasattr(connection, 'queries') else 0,
                'slow_query_count': self.get_slow_query_count(),
            }

            # Database size (approximate)
            try:
                with connection.cursor() as cursor:
                    if 'postgresql' in settings.DATABASES['default']['ENGINE']:
                        cursor.execute("SELECT pg_database_size(current_database())")
                        size_bytes = cursor.fetchone()[0]
                        stats['database_size_mb'] = round(size_bytes / (1024 * 1024), 2)
                    elif 'sqlite3' in settings.DATABASES['default']['ENGINE']:
                        import os
                        db_path = settings.DATABASES['default']['NAME']
                        if os.path.exists(db_path):
                            size_bytes = os.path.getsize(db_path)
                            stats['database_size_mb'] = round(size_bytes / (1024 * 1024), 2)
            except:
                stats['database_size_mb'] = 'unknown'

            return Response(stats)
            
        except Exception as e:
            logger.error(f"Database status error: {str(e)}")
            return Response({
                'error': 'Failed to fetch database status',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_last_update_time(self, model):
        try:
            last_obj = model.objects.order_by('-updated_at').first()
            if last_obj and hasattr(last_obj, 'updated_at'):
                return last_obj.updated_at.isoformat()
            return None
        except:
            return None

    def get_max_connections(self):
        try:
            with connection.cursor() as cursor:
                if 'postgresql' in settings.DATABASES['default']['ENGINE']:
                    cursor.execute("SHOW max_connections")
                    return cursor.fetchone()[0]
        except:
            return 'unknown'

    def get_slow_query_count(self):
        # This is a placeholder - implement actual slow query tracking
        return 0


@api_view(['GET'])
@permission_classes([AllowAny])
def simple_health_check(request):
    """
    Lightweight health check for quick status verification
    """
    try:
        # Quick database check
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        return Response({
            'status': 'ok',
            'message': 'Server is running',
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        return Response({
            'status': 'error',
            'message': f'Database error: {str(e)}'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_info(request):
    """
    Get detailed information about the current user
    """
    user = request.user
    from accounts.models import UserProfile
    
    try:
        profile = UserProfile.objects.get(user=user)
        
        user_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'date_joined': user.date_joined.isoformat(),
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'profile': {
                'user_type': profile.user_type,
                'phone_number': profile.phone_number,
                'is_verified': profile.is_verified,
                'created_at': profile.created_at.isoformat(),
                'updated_at': profile.updated_at.isoformat(),
            }
        }
        
        # Add shop information if user is an employee
        try:
            from shops.models import Employee
            employee = Employee.objects.get(user=user, is_active=True)
            user_data['employment'] = {
                'shop': {
                    'id': employee.shop.id,
                    'name': employee.shop.name,
                    'business': employee.shop.business.name
                },
                'role': {
                    'id': employee.role.id,
                    'name': employee.role.name,
                    'type': employee.role.role_type
                },
                'employment_date': employee.employment_date.isoformat(),
            }
        except Employee.DoesNotExist:
            user_data['employment'] = None
        
        # Add business information if user is an owner
        try:
            from shops.models import Business
            businesses = Business.objects.filter(owner=user)
            if businesses.exists():
                user_data['businesses'] = [
                    {
                        'id': biz.id,
                        'name': biz.name,
                        'shop_count': biz.shops.count()
                    }
                    for biz in businesses
                ]
        except:
            user_data['businesses'] = []
        
        return Response(user_data)
        
    except UserProfile.DoesNotExist:
        return Response({
            'error': 'User profile not found',
            'user_id': user.id,
            'username': user.username
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"User info error: {str(e)}")
        return Response({
            'error': 'Failed to fetch user info',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_user_info(request):
    """
    Update user information
    """
    user = request.user
    data = request.data
    
    try:
        profile = user.profile
        
        # Update user fields
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'email' in data and data['email'] != user.email:
            # Check if email is already taken
            from django.contrib.auth.models import User
            if User.objects.filter(email=data['email']).exclude(id=user.id).exists():
                return Response({
                    'error': 'Email already taken'
                }, status=status.HTTP_400_BAD_REQUEST)
            user.email = data['email']
        
        # Update profile fields
        if 'phone_number' in data:
            profile.phone_number = data['phone_number']
        if 'date_of_birth' in data:
            from django.utils.dateparse import parse_date
            dob = parse_date(data['date_of_birth'])
            if dob:
                profile.date_of_birth = dob
        
        user.save()
        profile.save()
        
        return Response({
            'message': 'User information updated successfully',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'profile': {
                'phone_number': profile.phone_number,
                'date_of_birth': profile.date_of_birth.isoformat() if profile.date_of_birth else None,
            }
        })
        
    except Exception as e:
        logger.error(f"Update user info error: {str(e)}")
        return Response({
            'error': 'Failed to update user info',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
# backend/middleware/request_logging.py
import logging
import time
import json
from django.utils.deprecation import MiddlewareMixin

# Get the request logger
logger = logging.getLogger('request')

class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Middleware for logging all incoming requests and responses.
    Includes user information, request body (for non-sensitive endpoints),
    and response times.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Paths to exclude from body logging (sensitive data)
        self.sensitive_paths = [
            '/auth/login/',
            '/auth/register/',
            '/auth/password-reset/',
            '/health/user/update/',
        ]
    
    def __call__(self, request):
        start_time = time.time()
        
        # Log request
        self.log_request(request)
        
        # Process the request
        response = self.get_response(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log response
        self.log_response(request, response, duration)
        
        return response
    
    def log_request(self, request):
        """Log incoming request details"""
        try:
            user = getattr(request, 'user', None)
            username = user.username if user and user.is_authenticated else 'Anonymous'
            
            request_data = {
                'method': request.method,
                'path': request.path,
                'user': username,
                'user_id': user.id if user and user.is_authenticated else None,
                'ip_address': self.get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'content_type': request.content_type,
                'query_params': dict(request.GET),
            }
            
            # Log request body for non-sensitive endpoints
            if not any(path in request.path for path in self.sensitive_paths):
                try:
                    if request.body and len(request.body) < 1000:  # Limit size
                        body = request.body.decode('utf-8', errors='ignore')
                        if body:
                            try:
                                # Try to parse as JSON for better readability
                                json_body = json.loads(body)
                                request_data['body'] = json_body
                            except:
                                request_data['body'] = body[:500]  # Truncate if too long
                except:
                    pass  # Skip body logging if there's an error
            
            logger.info(f"Request: {json.dumps(request_data, default=str)}")
            
        except Exception as e:
            logger.error(f"Error logging request: {str(e)}")
    
    def log_response(self, request, response, duration):
        """Log response details"""
        try:
            user = getattr(request, 'user', None)
            username = user.username if user and user.is_authenticated else 'Anonymous'
            
            response_data = {
                'method': request.method,
                'path': request.path,
                'user': username,
                'user_id': user.id if user and user.is_authenticated else None,
                'status_code': response.status_code,
                'duration_ms': round(duration * 1000, 2),
                'content_type': response.get('Content-Type', ''),
                'content_length': len(response.content) if hasattr(response, 'content') else 0,
            }
            
            # Log error responses with more details
            if response.status_code >= 400:
                try:
                    if hasattr(response, 'data'):
                        response_data['error'] = str(response.data)
                    elif hasattr(response, 'content'):
                        content = response.content.decode('utf-8', errors='ignore')
                        if len(content) < 500:  # Don't log huge error responses
                            response_data['error'] = content
                except:
                    pass
            
            logger.info(f"Response: {json.dumps(response_data, default=str)}")
            
        except Exception as e:
            logger.error(f"Error logging response: {str(e)}")
    
    def get_client_ip(self, request):
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def process_exception(self, request, exception):
        """Log exceptions that occur during request processing"""
        try:
            user = getattr(request, 'user', None)
            username = user.username if user and user.is_authenticated else 'Anonymous'
            
            exception_data = {
                'method': request.method,
                'path': request.path,
                'user': username,
                'exception_type': type(exception).__name__,
                'exception_message': str(exception),
                'ip_address': self.get_client_ip(request),
            }
            
            logger.error(f"Exception: {json.dumps(exception_data, default=str)}")
            
        except Exception as e:
            logger.error(f"Error logging exception: {str(e)}")
        
        return None  # Let other middleware handle the exception
# backend/middleware/api_analytics.py

import logging
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from datetime import datetime

logger = logging.getLogger('analytics')


def safe_increment(key, timeout=86400):
    """
    Safely increment a cache key.
    If the key does not exist, initialize it with 1.
    """
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=timeout)


class APIAnalyticsMiddleware(MiddlewareMixin):
    """
    Middleware for tracking API usage analytics:
    - Request counts per endpoint
    - User activity
    - Peak usage times
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Track request
        self.track_request(request)

        # Process request
        response = self.get_response(request)

        # Track response
        self.track_response(request, response)

        return response

    def track_request(self, request):
        """Track incoming request for analytics"""
        try:
            # Skip static files and admin
            if request.path.startswith('/static/') or request.path.startswith('/admin/'):
                return

            user = getattr(request, 'user', None)
            user_id = user.id if user and user.is_authenticated else None

            # Keys
            current_hour = datetime.now().strftime('%Y-%m-%d-%H')
            hour_key = f"analytics:hour:{current_hour}"
            endpoint_key = f"analytics:endpoint:{request.path}"
            user_key = f"analytics:user:{user_id}" if user_id else None

            # Increment safely
            safe_increment(hour_key)
            safe_increment(endpoint_key)

            if user_key:
                safe_increment(user_key)

            logger.info(
                f"API Analytics - Request: {request.method} {request.path} - "
                f"User: {user_id or 'Anonymous'}"
            )

        except Exception as e:
            logger.error(f"Error tracking request: {str(e)}")

    def track_response(self, request, response):
        """Track response for analytics"""
        try:
            status_key = f"analytics:status:{response.status_code}"
            safe_increment(status_key)

        except Exception as e:
            logger.error(f"Error tracking response: {str(e)}")
# backend/middleware/performance_monitoring.py
import logging
import time
from django.utils.deprecation import MiddlewareMixin
from django.db import connection

logger = logging.getLogger('performance')

class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """
    Middleware to monitor performance metrics:
    - Request/response time
    - Database query count and time
    - Slow requests (> 1 second)
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Start timing
        start_time = time.time()
        initial_queries = len(connection.queries)
        initial_query_time = sum(float(q['time']) for q in connection.queries)
        
        # Process request
        response = self.get_response(request)
        
        # Calculate metrics
        total_time = time.time() - start_time
        query_count = len(connection.queries) - initial_queries
        query_time = sum(float(q['time']) for q in connection.queries[initial_queries:])
        
        # Log slow requests
        if total_time > 1.0:  # More than 1 second
            self.log_slow_request(request, response, total_time, query_count, query_time)
        
        # Add performance headers (optional)
        response['X-Request-Time'] = f"{total_time:.3f}s"
        response['X-Query-Count'] = str(query_count)
        response['X-Query-Time'] = f"{query_time:.3f}s"
        
        return response
    
    def log_slow_request(self, request, response, total_time, query_count, query_time):
        """Log details of slow requests"""
        user = getattr(request, 'user', None)
        username = user.username if user and user.is_authenticated else 'Anonymous'
        
        logger.warning(
            f"Slow Request: {request.method} {request.path} - "
            f"User: {username} - "
            f"Total: {total_time:.3f}s - "
            f"Queries: {query_count} ({query_time:.3f}s) - "
            f"Status: {response.status_code}"
        )
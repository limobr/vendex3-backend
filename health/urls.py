# backend/health/urls.py
from django.urls import path
from .views import (
    HealthCheckView,
    ServerInfoView,
    DatabaseStatusView,
    simple_health_check,
    user_info,
    update_user_info
)

urlpatterns = [
    path('', HealthCheckView.as_view(), name='health_check'),
    path('simple/', simple_health_check, name='simple_health_check'),
    path('info/', ServerInfoView.as_view(), name='server_info'),
    path('db/', DatabaseStatusView.as_view(), name='database_status'),
    path('user/', user_info, name='user_info'),
    path('user/update/', update_user_info, name='update_user_info'),
]
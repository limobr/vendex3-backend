# vendex/urls.py - Fixed: removed duplicate shops/, wired sales/ and sync/
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView, TokenBlacklistView, TokenVerifyView
from accounts.views import CustomLoginView, RegisterView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # Authentication
    path('auth/', include('accounts.urls')),
    path('auth/login/', CustomLoginView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='refresh'),
    path('auth/verify/', TokenVerifyView.as_view(), name='verify_token'),
    path('auth/logout/', TokenBlacklistView.as_view(), name='logout'),

    # API modules
    path('health/', include('health.urls')),
    path('shops/', include('shops.urls')),
    path('products/', include('products.urls')),
    path('sales/', include('sales.urls')),
    path('sync/', include('sync.urls')),

    # Root health check
    path('', include('health.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

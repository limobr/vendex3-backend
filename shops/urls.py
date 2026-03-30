from django.urls import path
from . import views

urlpatterns = [
    # Business endpoints
    path('businesses/create/', views.BusinessCreateView.as_view(), name='business-create'),
    path('businesses/<uuid:business_id>/update/', views.BusinessUpdateView.as_view(), name='business-update'),
    path('businesses/<uuid:business_id>/delete/', views.BusinessDeleteView.as_view(), name='business-delete'),
    path('businesses/list/', views.BusinessListView.as_view(), name='business-list'),
    path('businesses/sync/', views.BusinessSyncView.as_view(), name='business-sync'),
    path('businesses/user-data/', views.UserBusinessDataView.as_view(), name='user-business-data'),
    
    # Shop endpoints
    path('shops/create/', views.ShopCreateView.as_view(), name='shop-create'),
    path('shops/<uuid:shop_id>/update/', views.ShopUpdateView.as_view(), name='shop-update'),
    path('shops/<uuid:shop_id>/delete/', views.ShopDeleteView.as_view(), name='shop-delete'),
    path('shops/list/', views.ShopListView.as_view(), name='shop-list'),
    path('shops/<uuid:shop_id>/', views.ShopDetailView.as_view(), name='shop-detail'),
    
    # Employee endpoints
    path('employees/roles/', views.RoleListView.as_view(), name='role-list'),
    path('employees/create/', views.EmployeeCreateView.as_view(), name='employee-create'),
    path('employees/list/', views.EmployeeListView.as_view(), name='employee-list'),
    path('employees/<uuid:employee_id>/', views.EmployeeDetailView.as_view(), name='employee-detail'),
    path('employees/<uuid:employee_id>/resend-credentials/', views.ResendEmployeeCredentialsView.as_view(), name='resend-credentials'),
]
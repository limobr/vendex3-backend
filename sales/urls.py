# sales/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Sales
    path('create/', views.SaleCreateView.as_view(), name='sale-create'),
    path('list/', views.SaleListView.as_view(), name='sale-list'),
    path('detail/<uuid:sale_id>/', views.SaleDetailView.as_view(), name='sale-detail'),
    path('refund/<uuid:sale_id>/', views.SaleRefundView.as_view(), name='sale-refund'),
    path('download/', views.SalesDownloadView.as_view(), name='sales-download'),

    # Customers
    path('customers/', views.CustomerListView.as_view(), name='customer-list'),
    path('customers/create/', views.CustomerCreateView.as_view(), name='customer-create'),
    path('customers/<uuid:customer_id>/', views.CustomerDetailView.as_view(), name='customer-detail'),

    # Reports & Dashboard
    path('reports/', views.SalesReportView.as_view(), name='sales-report'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
]

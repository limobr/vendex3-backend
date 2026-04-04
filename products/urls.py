# products/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Categories
    path('categories/', views.CategoryListView.as_view(), name='category-list'),
    path('categories/create/', views.CategoryCreateView.as_view(), name='category-create'),
    
    # Taxes
    path('taxes/', views.TaxListView.as_view(), name='tax-list'),
    
    # Products
    path('create/', views.ProductCreateView.as_view(), name='product-create'),
    path('list/', views.ProductListView.as_view(), name='product-list'),
    path('detail/<uuid:product_id>/', views.ProductDetailView.as_view(), name='product-detail'),
    path('update/<uuid:product_id>/', views.ProductDetailView.as_view(), name='product-update'),
    path('delete/<uuid:product_id>/', views.ProductDetailView.as_view(), name='product-delete'),
    
    # Sync
    path('download/all/', views.ProductDownloadAllView.as_view(), name='product-download-all'),
    path('sync/incremental/', views.ProductIncrementalSyncView.as_view(), name='product-incremental-sync'),
    path('sync/', views.ProductSyncView.as_view(), name='product-sync'),

    # Inventory
    path('restock/', views.ProductRestockView.as_view(), name='product-restock'),
]
# sync/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('full-download/', views.FullSyncDownloadView.as_view(), name='full-sync-download'),
    path('push/', views.PushSyncView.as_view(), name='push-sync'),
    path('incremental/', views.IncrementalSyncView.as_view(), name='incremental-sync'),
]

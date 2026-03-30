# sync/models.py
from django.db import models
import uuid
from shops.models import Shop

class SyncLog(models.Model):
    SYNC_TYPES = (
        ('push', 'Push to Server'),
        ('pull', 'Pull from Server'),
        ('full', 'Full Sync'),
    )
    
    SYNC_STATUS = (
        ('started', 'Started'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('partial', 'Partial Success'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='sync_logs')
    device_id = models.CharField(max_length=255)  # Mobile device identifier
    sync_type = models.CharField(max_length=20, choices=SYNC_TYPES)
    status = models.CharField(max_length=20, choices=SYNC_STATUS)
    
    # Statistics
    records_pushed = models.IntegerField(default=0)
    records_pulled = models.IntegerField(default=0)
    conflicts_found = models.IntegerField(default=0)
    conflicts_resolved = models.IntegerField(default=0)
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    
    # Error handling
    error_message = models.TextField(blank=True, null=True)
    stack_trace = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Sync {self.sync_type} - {self.shop.name} - {self.status}"

class PendingSync(models.Model):
    """Queue for offline changes that need to be synced"""
    MODEL_TYPES = (
        ('sale', 'Sale'),
        ('sale_item', 'Sale Item'),
        ('payment', 'Payment'),
        ('inventory', 'Inventory'),
        ('customer', 'Customer'),
    )
    
    OPERATION_TYPES = (
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='pending_syncs')
    device_id = models.CharField(max_length=255)
    model_type = models.CharField(max_length=20, choices=MODEL_TYPES)
    operation = models.CharField(max_length=10, choices=OPERATION_TYPES)
    record_id = models.UUIDField()  # ID of the record that was changed
    data = models.JSONField()  # The actual data to sync
    created_at = models.DateTimeField(auto_now_add=True)
    attempts = models.IntegerField(default=0)
    last_attempt = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['shop', 'model_type', 'created_at']),
        ]

    def __str__(self):
        return f"{self.operation} {self.model_type} - {self.shop.name}"

class Backup(models.Model):
    BACKUP_TYPES = (
        ('full', 'Full Backup'),
        ('incremental', 'Incremental Backup'),
        ('emergency', 'Emergency Backup'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='backups')
    backup_type = models.CharField(max_length=20, choices=BACKUP_TYPES)
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField()  # Size in bytes
    checksum = models.CharField(max_length=64)  # SHA-256 checksum
    encrypted = models.BooleanField(default=True)
    
    # Cloud storage info
    cloud_path = models.TextField(blank=True, null=True)
    cloud_provider = models.CharField(max_length=50, blank=True, null=True)  # 'google_drive', 'icloud'
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Backup {self.backup_type} - {self.shop.name} - {self.created_at}"
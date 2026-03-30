# accounts/utils.py - Notification helpers & UUID validation
import uuid
import logging
import secrets
from django.utils import timezone

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# UUID validation for offline IDs
# ──────────────────────────────────────────────────────────
def validate_offline_id(value):
    """
    Validate that a given value is a proper UUID.
    Returns (is_valid: bool, cleaned_uuid: str|None, error: str|None)
    """
    if not value:
        return True, None, None  # empty is OK (not required)
    try:
        val = uuid.UUID(str(value))
        return True, str(val), None
    except (ValueError, AttributeError):
        return False, None, f"Invalid UUID format: {value}"


def validate_offline_ids(data_dict, fields=None):
    """
    Validate multiple offline ID fields in a dictionary.
    Returns (is_valid, errors_dict)
    """
    fields = fields or ['offline_id']
    errors = {}
    for field in fields:
        val = data_dict.get(field)
        if val:
            is_valid, _, err = validate_offline_id(val)
            if not is_valid:
                errors[field] = err
    return len(errors) == 0, errors


# ──────────────────────────────────────────────────────────
# Verification code generation
# ──────────────────────────────────────────────────────────
def generate_verification_code(length=6):
    """Generate a numeric verification code (default 6 digits)."""
    return ''.join([str(secrets.randbelow(10)) for _ in range(length)])


# ──────────────────────────────────────────────────────────
# Notification creation helpers
# ──────────────────────────────────────────────────────────
def create_notification(
    title, message,
    recipient=None, recipient_role=None, business=None,
    notification_type='info', category='general',
    related_object_type=None, related_object_id=None,
):
    """
    Create a Notification record. Import here to avoid circular imports.
    """
    from accounts.models import Notification
    try:
        notif = Notification.objects.create(
            recipient=recipient,
            recipient_role=recipient_role,
            business=business,
            title=title,
            message=message,
            notification_type=notification_type,
            category=category,
            related_object_type=related_object_type,
            related_object_id=related_object_id,
        )
        logger.info(f"🔔 Notification created: [{category}] {title}")
        return notif
    except Exception as e:
        logger.error(f"❌ Failed to create notification: {e}")
        return None


def notify_sale_completed(sale):
    """Notify shop owner that a sale was completed."""
    owner = sale.shop.business.owner
    create_notification(
        title='Sale Completed',
        message=f'Sale {sale.receipt_number} completed for {sale.shop.currency} {sale.total_amount:.2f} at {sale.shop.name}.',
        recipient=owner,
        business=sale.shop.business,
        notification_type='success',
        category='sale',
        related_object_type='sale',
        related_object_id=sale.id,
    )


def notify_inventory_update(inventory, adjustment, user=None):
    """Notify owner about inventory adjustment."""
    product_name = inventory.variant.name if inventory.variant else (inventory.product.name if inventory.product else 'Unknown')
    owner = inventory.shop.business.owner
    create_notification(
        title='Inventory Updated',
        message=f'{product_name} stock adjusted by {adjustment:+d} at {inventory.shop.name}. New stock: {inventory.current_stock}.',
        recipient=owner,
        business=inventory.shop.business,
        notification_type='info',
        category='inventory',
        related_object_type='inventory',
        related_object_id=inventory.id,
    )


def notify_low_stock(inventory):
    """Notify owner when stock falls below minimum."""
    product_name = inventory.variant.name if inventory.variant else (inventory.product.name if inventory.product else 'Unknown')
    owner = inventory.shop.business.owner
    create_notification(
        title='Low Stock Alert',
        message=f'{product_name} at {inventory.shop.name} has only {inventory.current_stock} units left (minimum: {inventory.minimum_stock}).',
        recipient=owner,
        business=inventory.shop.business,
        notification_type='warning',
        category='stock_alert',
        related_object_type='inventory',
        related_object_id=inventory.id,
    )


def notify_employee_invited(employee, business):
    """Notify owner that an employee invite was sent."""
    create_notification(
        title='Employee Invited',
        message=f'{employee.user.get_full_name() or employee.user.email} has been invited to join {employee.shop.name} as {employee.role.name}.',
        recipient=business.owner,
        business=business,
        notification_type='info',
        category='employee',
        related_object_type='employee',
        related_object_id=employee.id,
    )


def notify_employee_joined(employee, business):
    """Notify owner that an employee accepted the invite."""
    create_notification(
        title='Employee Joined',
        message=f'{employee.user.get_full_name() or employee.user.email} has completed onboarding and joined {employee.shop.name}.',
        recipient=business.owner,
        business=business,
        notification_type='success',
        category='employee',
        related_object_type='employee',
        related_object_id=employee.id,
    )


def notify_role_changed(employee, old_role_name, new_role_name, business):
    """Notify employee that their role was changed."""
    create_notification(
        title='Role Updated',
        message=f'Your role at {employee.shop.name} has been changed from {old_role_name} to {new_role_name}.',
        recipient=employee.user,
        business=business,
        notification_type='info',
        category='role_change',
        related_object_type='employee',
        related_object_id=employee.id,
    )


def notify_invite_resent(employee, business):
    """Notify that a new invite was resent."""
    create_notification(
        title='Invite Resent',
        message=f'New login credentials have been sent to {employee.user.email} for {employee.shop.name}.',
        recipient=business.owner,
        business=business,
        notification_type='info',
        category='employee',
        related_object_type='employee',
        related_object_id=employee.id,
    )

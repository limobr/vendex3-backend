# accounts/urls.py - Updated with new endpoints
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    CompleteUserSyncView,
    DeleteProfilePictureView,
    RegisterView,
    UploadAndSyncProfilePicture,
    sync_accounts_data,
    LogoutView,
    sync_employees_data,
    sync_user_data,
    verify_auth,
    UserProfileUpdateView,
    UserProfileDetailView,
    BulkSyncView,
    verify_token,
    ProfilePictureUploadView,
    Base64ImageUploadView,
    health_check,
    test_media,
)
from .views_new import (
    EmployeeLoginView,
    CompleteOnboardingView,
    ChangeTempPasswordView,
    VerifyInviteCodeView,
    ConfigurationView,
    NotificationListView,
    NotificationMarkReadView,
    NotificationMarkAllReadView,
    MessageListView,
    MessageSendView,
    MessageMarkReadView,
    RequestResendCredentialsView,
    ReceiptTemplateView,
)

urlpatterns = [
    # Health checks (public)
    path('health/', health_check, name='health_check'),
    path('test-media/', test_media, name='test_media'),

    # Authentication
    path('register/', RegisterView.as_view(), name='register'),
    path('sync/', sync_accounts_data, name='sync_accounts'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('verify/', verify_auth, name='verify_auth'),
    path('verify-token/', verify_token, name='verify_token'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Employee login & onboarding (NEW)
    path('employee-login/', EmployeeLoginView.as_view(), name='employee_login'),
    path('complete-onboarding/', CompleteOnboardingView.as_view(), name='complete_onboarding'),
    path('change-temp-password/', ChangeTempPasswordView.as_view(), name='change_temp_password'),
    path('verify-invite-code/', VerifyInviteCodeView.as_view(), name='verify_invite_code'),
    path('request-resend-credentials/', RequestResendCredentialsView.as_view(), name='request_resend_credentials'),

    # Profile
    path('profile/update/', UserProfileUpdateView.as_view(), name='profile_update'),
    path('profile/detail/', UserProfileDetailView.as_view(), name='profile_detail'),
    path('profile/upload-picture/', ProfilePictureUploadView.as_view(), name='profile_upload_picture'),
    path('profile/upload-base64/', Base64ImageUploadView.as_view(), name='profile_upload_base64'),
    path('profile/delete-picture/', DeleteProfilePictureView.as_view(), name='profile_delete_picture'),
    path('upload-profile-picture/', UploadAndSyncProfilePicture.as_view(), name='upload_profile_picture'),

    # Sync
    path('bulk-sync/', BulkSyncView.as_view(), name='bulk_sync'),
    path('auth/complete-sync/', CompleteUserSyncView.as_view(), name='complete_sync'),
    path('sync/user-data/', sync_user_data, name='sync_user_data'),
    path('sync/employees/', sync_employees_data, name='sync_employees'),

    # Configuration / Theme (NEW)
    path('config/<uuid:business_id>/', ConfigurationView.as_view(), name='configuration'),

    # Notifications (NEW)
    path('notifications/', NotificationListView.as_view(), name='notification_list'),
    path('notifications/<uuid:notification_id>/read/', NotificationMarkReadView.as_view(), name='notification_read'),
    path('notifications/read-all/', NotificationMarkAllReadView.as_view(), name='notification_read_all'),

    # Messages (NEW)
    path('messages/', MessageListView.as_view(), name='message_list'),
    path('messages/send/', MessageSendView.as_view(), name='message_send'),
    path('messages/<uuid:message_id>/read/', MessageMarkReadView.as_view(), name='message_read'),

    # Receipt Templates (NEW)
    path('receipt-templates/<uuid:shop_id>/', ReceiptTemplateView.as_view(), name='receipt_template'),
]

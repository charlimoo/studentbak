# start of apps/users/urls.py
# apps/users/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserRegistrationView, InstitutionRegistrationView, UserMeView, UserViewSet, RoleViewSet, PermissionListView,
    ImpersonateStartView, ImpersonateStopView,
    UserProfileView, ChangePasswordView, UserNotificationSettingsView,
    PasswordResetRequestView, PasswordResetConfirmView,
    InstitutionStaffViewSet # --- FIX: Import the new viewset
)

router = DefaultRouter()
router.register(r'management', UserViewSet, basename='user-management')
router.register(r'roles', RoleViewSet, basename='role')
# --- FIX: Register the new endpoint for institution staff management ---
router.register(r'institution-staff', InstitutionStaffViewSet, basename='institution-staff')

auth_urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='user-register'),
    path('institution-register/', InstitutionRegistrationView.as_view(), name='institution-register'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
]

impersonate_urlpatterns = [
    path('<int:user_id>/start/', ImpersonateStartView.as_view(), name='impersonate-start'),
    path('stop/', ImpersonateStopView.as_view(), name='impersonate-stop'),
]

profile_urlpatterns = [
    path('', UserProfileView.as_view(), name='user-profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('notification-settings/', UserNotificationSettingsView.as_view(), name='notification-settings'),
]

urlpatterns = [
    path('me/', UserMeView.as_view(), name='user-me'),
    path('me/profile/', include(profile_urlpatterns)),
    path('auth/', include(auth_urlpatterns)),
    path('impersonate/', include(impersonate_urlpatterns)),
    path('permissions/', PermissionListView.as_view(), name='permission-list'),
    path('', include(router.urls)),
]
# end of apps/users/urls.py
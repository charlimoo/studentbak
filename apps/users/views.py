# start of apps/users/views.py
# apps/users/views.py
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.db import transaction # --- FIX: Import transaction
from rest_framework import viewsets, permissions, status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.tokens import RefreshToken
from impersonate.views import impersonate as start_impersonate_session, stop_impersonate as stop_impersonate_session
from rest_framework import serializers
from .models import User, Role, Permission, UserNotificationSettings, PasswordResetToken
from .serializers import (
    UserSerializer, UserAdminSerializer, RoleSerializer, PermissionSerializer,
    UserRegistrationSerializer, InstitutionRegistrationSerializer, UserProfileSerializer,
    ChangePasswordSerializer, PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    UserNotificationSettingsSerializer, InstitutionStaffSerializer # --- FIX: Import new serializer
)
from .permissions import IsHeadOfOrganization, HasPermission, IsRecruitmentInstitution # --- FIX: Import new permission
from .filters import UserFilter
from .tasks import send_password_reset_email_task
import logging

logger = logging.getLogger(__name__)

# --- Public & General User Views ---
class UserRegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = UserRegistrationSerializer

class InstitutionRegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = InstitutionRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]

class UserMeView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, *args, **kwargs):
        return Response(UserSerializer(request.user).data)

# --- Password Reset Flow ---
class PasswordResetRequestView(generics.GenericAPIView):
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [permissions.AllowAny]
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = User.objects.get(email__iexact=serializer.validated_data['email'])
            PasswordResetToken.objects.filter(user=user).delete()
            reset_token = PasswordResetToken.objects.create(user=user)
            send_password_reset_email_task.delay(user.id, str(reset_token.token))
        except User.DoesNotExist: pass
        return Response({"detail": "If an account with that email exists, a password reset link has been sent."}, status=status.HTTP_200_OK)

class PasswordResetConfirmView(generics.GenericAPIView):
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [permissions.AllowAny]
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reset_token = PasswordResetToken.objects.select_related('user').get(token=serializer.validated_data['token'])
        except (PasswordResetToken.DoesNotExist, ValueError):
            return Response({"token": ["Invalid or expired token."]}, status=status.HTTP_400_BAD_REQUEST)
        if reset_token.is_expired():
            reset_token.delete()
            return Response({"token": ["Invalid or expired token."]}, status=status.HTTP_400_BAD_REQUEST)
        user = reset_token.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        reset_token.delete()
        return Response({"detail": "Password has been reset successfully."}, status=status.HTTP_200_OK)

# --- Self-Service Profile Management Views ---
class UserProfileView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_object(self):
        return self.request.user

class ChangePasswordView(generics.UpdateAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_object(self):
        return self.request.user
    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not self.object.check_password(serializer.data.get("old_password")):
            return Response({"old_password": ["Wrong password."]}, status=status.HTTP_400_BAD_REQUEST)
        self.object.set_password(serializer.data.get("new_password"))
        self.object.save()
        return Response({"detail": "Password updated successfully."}, status=status.HTTP_200_OK)

class UserNotificationSettingsView(generics.RetrieveUpdateAPIView):
    serializer_class = UserNotificationSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_object(self):
        settings, _ = UserNotificationSettings.objects.get_or_create(user=self.request.user)
        return settings

# --- Admin & Management Views ---
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.prefetch_related('roles', 'universities', 'organization_unit').order_by('id')
    serializer_class = UserAdminSerializer
    permission_classes = [permissions.IsAuthenticated, HasPermission]
    required_permission = 'manage_users'
    filterset_class = UserFilter
    ordering_fields = ['full_name', 'email', 'date_joined']

class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.prefetch_related('permissions').all()
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated, HasPermission]
    required_permission = 'manage_roles'

class PermissionListView(generics.ListAPIView):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [permissions.IsAuthenticated, HasPermission]
    required_permission = 'manage_roles'
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        data = {}
        for permission in queryset:
            data.setdefault(permission.group, []).append(self.get_serializer(permission).data)
        return Response(data)

# --- Impersonation Views ---
class ImpersonateStartView(APIView):
    permission_classes = [IsHeadOfOrganization]
    def post(self, request, user_id):
        target_user = get_object_or_404(get_user_model(), pk=user_id)
        if target_user.is_superuser:
            return Response({"detail": "Cannot impersonate a superuser."}, status=status.HTTP_403_FORBIDDEN)
        
        start_impersonate_session(request, target_user)
        
        refresh = RefreshToken.for_user(target_user)
        
        return Response({
            'status': f'Now impersonating {target_user.email}',
            'impersonated_user': UserSerializer(target_user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token)
        })

class ImpersonateStopView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        if not getattr(request.user, 'is_impersonate', False):
            return Response({"detail": "Not currently impersonating."}, status=status.HTTP_400_BAD_REQUEST)
        
        stop_impersonate_session(request)
        
        return Response({'status': 'Impersonation stopped.'})

# --- FIX: NEW VIEWSET FOR INSTITUTION STAFF MANAGEMENT ---
class InstitutionStaffViewSet(viewsets.ModelViewSet):
    """
    Allows Recruitment Institution users to manage their own staff (University Experts).
    Provides list, create, and delete functionality.
    """
    serializer_class = InstitutionStaffSerializer
    permission_classes = [permissions.IsAuthenticated, IsRecruitmentInstitution]

    def get_queryset(self):
        institution_user = self.request.user
        affiliated_universities = institution_user.universities.all()
        
        if not affiliated_universities.exists():
            return User.objects.none()

        return User.objects.filter(
            roles__name='UniversityExpert',
            universities__in=affiliated_universities
        ).distinct().order_by('full_name')

    def create(self, request, *args, **kwargs):
        """
        Override the create method to add detailed logging.
        """
        logger.info(f"\n--- [Institution Staff Creation] ---")
        logger.info(f"Request received from user: {request.user.email}")
        logger.info(f"Request data received: {request.data}")

        serializer = self.get_serializer(data=request.data)
        
        # Manually check for validity and log errors if they exist
        if not serializer.is_valid():
            logger.error(f"Validation FAILED for user {request.user.email}.")
            logger.error(f"Serializer Errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info("Serializer validation PASSED.")
        
        try:
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            logger.info(f"Successfully created staff user: {serializer.data.get('email')}")
            logger.info("--- [End Institution Staff Creation] ---\n")
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except Exception as e:
            logger.error(f"An unexpected error occurred during perform_create: {e}", exc_info=True)
            logger.info("--- [End Institution Staff Creation with ERROR] ---\n")
            return Response({"detail": "An internal server error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def perform_create(self, serializer):
        """
        When an institution creates a new staff member, we automatically:
        1. Create the user as a staff member.
        2. Assign the 'UniversityExpert' role.
        3. Affiliate them with the institution's universities.
        """
        institution_user = self.request.user
        email = serializer.validated_data['email']
        logger.info(f"Starting perform_create for email: {email}")
        
        with transaction.atomic():
            logger.info("Transaction started.")
            # Create the user with the provided email and password
            user = User.objects.create_user(
                email=email,
                full_name=serializer.validated_data['full_name'],
                password=serializer.validated_data['password'],
                is_staff=True, # UniversityExperts are staff
                is_active=True
            )
            logger.info(f"User object created in memory for {email}.")
            
            # Assign the 'UniversityExpert' role
            try:
                expert_role = Role.objects.get(name='UniversityExpert')
                user.roles.add(expert_role)
                logger.info(f"Assigned 'UniversityExpert' role to {email}.")
            except Role.DoesNotExist:
                logger.error("CRITICAL: 'UniversityExpert' role not found in the database!")
                raise serializers.ValidationError("System Error: 'UniversityExpert' role not found.")

            # Assign the same universities as the institution
            universities_to_add = institution_user.universities.all()
            if universities_to_add.exists():
                user.universities.add(*universities_to_add)
                logger.info(f"Assigned {universities_to_add.count()} university/ies to {email}.")
            else:
                logger.warning(f"Institution user {institution_user.email} has no universities to assign.")

            # The user is saved by the create_user and subsequent M2M adds.
            logger.info(f"Transaction will now be committed for {email}.")
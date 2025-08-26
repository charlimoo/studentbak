# apps/users/serializers.py
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from .models import User, Role, Permission, UserNotificationSettings, InstitutionProfile
from apps.applications.models import ApplicationTask
from apps.core.serializers import UniversitySerializer
# --- Read-Only & Helper Serializers ---
class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'codename', 'name', 'group']

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name', 'description']

class UserSerializer(serializers.ModelSerializer):
    roles = RoleSerializer(many=True, read_only=True)
    # --- FIX: ADD THIS LINE TO INCLUDE UNIVERSITIES IN THE SERIALIZER ---
    universities = UniversitySerializer(many=True, read_only=True)
    
    class Meta:
        model = User
        # --- FIX: ADD 'universities' TO THE LIST OF FIELDS ---
        fields = ['id', 'email', 'full_name', 'roles', 'universities', 'profile_picture', 'is_active', 'is_staff']

# --- Action-Specific Serializers ---
class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password], style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, required=True, label="Confirm Password", style={'input_type': 'password'})
    class Meta:
        model = User
        fields = ('id', 'email', 'full_name', 'password', 'password2')
    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        attrs['username'] = attrs['email']
        return attrs
    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        try:
            applicant_role, _ = Role.objects.get_or_create(name='Applicant')
            user.roles.add(applicant_role)
        except Exception:
            pass # Log this critical server configuration error
        return user

class InstitutionRegistrationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    legal_name = serializers.CharField(write_only=True)
    address = serializers.CharField(write_only=True)
    contact_person_name = serializers.CharField(write_only=True)
    contact_person_phone = serializers.CharField(write_only=True)
    registration_document = serializers.FileField(write_only=True)
    class Meta:
        model = User
        fields = ('email', 'password', 'legal_name', 'address', 'contact_person_name', 'contact_person_phone', 'registration_document')
    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
    def create(self, validated_data):
        with transaction.atomic():
            user = User.objects.create_user(
                email=validated_data['email'], password=validated_data['password'],
                full_name=validated_data['legal_name'], is_active=False
            )
            try:
                institution_role = Role.objects.get(name='Recruitment Institution')
                user.roles.add(institution_role)
            except Role.DoesNotExist: pass
            InstitutionProfile.objects.create(
                user=user, legal_name=validated_data['legal_name'], address=validated_data['address'],
                contact_person_name=validated_data['contact_person_name'],
                contact_person_phone=validated_data['contact_person_phone'],
                registration_document=validated_data['registration_document']
            )
        return user

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['full_name', 'phone_number', 'profile_picture']

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    new_password2 = serializers.CharField(required=True, write_only=True, label="Confirm New Password")
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({"new_password": "Password fields didn't match."})
        return attrs

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    new_password2 = serializers.CharField(required=True, write_only=True, label="Confirm New Password")
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({"new_password": "Password fields didn't match."})
        return attrs

class UserNotificationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserNotificationSettings
        fields = ['email_on_new_task', 'email_on_status_update']

class UserAdminSerializer(serializers.ModelSerializer):
    roles = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all(), many=True, required=False)
    password = serializers.CharField(write_only=True, required=False, style={'input_type': 'password'})
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'password', 'roles', 'universities', 'organization_unit', 'is_active', 'is_staff']
    def update(self, instance, validated_data):
        new_roles_data = validated_data.get('roles')
        if new_roles_data is not None:
            try:
                expert_role = Role.objects.get(name='UniversityExpert')
                if expert_role in instance.roles.all() and expert_role not in new_roles_data:
                    if ApplicationTask.objects.filter(assigned_expert=instance, status='ASSIGNED').exists():
                        raise serializers.ValidationError({"roles": "This user has active tasks. Reassign them before removing the UniversityExpert role."})
            except Role.DoesNotExist: pass
        password = validated_data.pop('password', None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save()
        return instance
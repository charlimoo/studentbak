# apps/users/models.py
import uuid
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

class UserManager(BaseUserManager):
    """Custom user model manager where email is the unique identifier."""
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        username = extra_fields.pop('username', email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        return self.create_user(email, password, **extra_fields)

class Permission(models.Model):
    codename = models.CharField(_("Codename"), max_length=100, unique=True, help_text=_("e.g., view_all_applications"))
    name = models.CharField(_("Name"), max_length=255, help_text=_("e.g., Can view all applications"))
    group = models.CharField(_("Group"), max_length=100, help_text=_("A group name for UI organization, e.g., 'applications'"))
    class Meta:
        verbose_name = _("Permission")
        verbose_name_plural = _("Permissions")
        ordering = ['group', 'name']
    def __str__(self):
        return self.name

class Role(models.Model):
    name = models.CharField(_("Role Name"), max_length=100, unique=True)
    description = models.TextField(_("Description"), blank=True)
    permissions = models.ManyToManyField(Permission, related_name="roles", blank=True, verbose_name=_("Permissions"))
    class Meta:
        verbose_name = _("Role")
        verbose_name_plural = _("Roles")
        ordering = ['name']
    def __str__(self):
        return self.name

class User(AbstractUser):
    username = models.CharField(_('username'), max_length=150, blank=True, help_text=_('Not used for login.'))
    email = models.EmailField(_('email address'), unique=True)
    full_name = models.CharField(_("Full Name"), max_length=255)
    phone_number = models.CharField(_("Phone Number"), max_length=20, blank=True)
    profile_picture = models.ImageField(_("Profile Picture"), upload_to='profile_pics/', null=True, blank=True)
    roles = models.ManyToManyField(Role, related_name="users", verbose_name=_("Roles"), blank=True)
    universities = models.ManyToManyField('core.University', related_name="experts", blank=True, verbose_name=_("Affiliated Universities"))
    organization_unit = models.ForeignKey('core.OrganizationUnit', on_delete=models.SET_NULL, null=True, blank=True, related_name='staff', verbose_name=_("Organization Unit"))
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']
    objects = UserManager()
    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
    def __str__(self):
        return self.email

class UserNotificationSettings(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_settings")
    email_on_new_task = models.BooleanField(default=True, verbose_name=_("Email on new task assignment"))
    email_on_status_update = models.BooleanField(default=False, verbose_name=_("Email on application status update"))
    class Meta:
        verbose_name = _("User Notification Settings")
        verbose_name_plural = _("User Notification Settings")

class PasswordResetToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="password_reset_tokens")
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name = "Password Reset Token"
        verbose_name_plural = "Password Reset Tokens"
    def is_expired(self):
        return self.created_at < timezone.now() - timedelta(hours=1)
    def __str__(self):
        return f"Token for {self.user.email}"

class InstitutionProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="institution_profile")
    legal_name = models.CharField("Legal Institution Name", max_length=255, unique=True)
    address = models.TextField("Address")
    contact_person_name = models.CharField("Contact Person Name", max_length=255)
    contact_person_phone = models.CharField("Contact Person Phone", max_length=20)
    registration_document = models.FileField("Registration Document", upload_to='institution_registrations/')
    is_approved = models.BooleanField("Approved", default=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reviewed_institutions", limit_choices_to={'is_staff': True}
    )
    reviewed_at = models.DateTimeField("Reviewed At", null=True, blank=True)
    class Meta:
        verbose_name = "Institution Profile"
        verbose_name_plural = "Institution Profiles"
    def __str__(self):
        return f"Profile for {self.legal_name}"
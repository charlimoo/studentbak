# apps/core/models.py
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from mptt.models import MPTTModel, TreeForeignKey

class University(models.Model):
    name = models.CharField(_("University Name"), max_length=255, unique=True)
    class Meta:
        verbose_name = _("University")
        verbose_name_plural = _("Universities")
        ordering = ['name']
    def __str__(self):
        return self.name

class Program(models.Model):
    name = models.CharField(_("Program Name"), max_length=255)
    university = models.ForeignKey(University, on_delete=models.CASCADE, related_name="programs", verbose_name=_("University"))
    class Meta:
        unique_together = ('name', 'university')
        verbose_name = _("Program")
        verbose_name_plural = _("Programs")
        ordering = ['university__name', 'name']
    def __str__(self):
        return f"{self.name} ({self.university.name})"

class OrganizationUnit(MPTTModel):
    class UnitType(models.TextChoices):
        ORGANIZATION = 'ORGANIZATION', _('Organization')
        PROVINCE = 'PROVINCE', _('Province')
        UNIVERSITY = 'UNIVERSITY', _('University')
    name = models.CharField(_("Unit Name"), max_length=255)
    type = models.CharField(_("Unit Type"), max_length=20, choices=UnitType.choices)
    manager_name = models.CharField(_("Manager Name"), max_length=255, blank=True)
    description = models.TextField(_("Description"), blank=True)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', db_index=True, verbose_name=_("Parent Unit"))
    class MPTTMeta:
        order_insertion_by = ['name']
    class Meta:
        verbose_name = _("Organization Unit")
        verbose_name_plural = _("Organization Units")
    def __str__(self):
        return self.name

class NotificationTemplate(models.Model):
    class TemplateType(models.TextChoices):
        EMAIL = 'EMAIL', _('Email')
        SMS = 'SMS', _('SMS')
    name = models.CharField(_("Template Name"), max_length=100, unique=True, help_text=_("e.g., 'application_approved_email'"))
    type = models.CharField(_("Type"), max_length=10, choices=TemplateType.choices)
    subject = models.CharField(_("Subject"), max_length=255, blank=True, help_text=_("For emails only."))
    body = models.TextField(_("Body"), help_text=_("Use placeholders like {{ full_name }} or {{ tracking_code }}."))
    class Meta:
        verbose_name = _("Notification Template")
        verbose_name_plural = _("Notification Templates")
    def __str__(self):
        return self.name

class SystemList(models.Model):
    name = models.CharField(_("List Name"), max_length=100, unique=True, help_text=_("e.g., 'nationalities'"))
    items = models.JSONField(_("Items"), default=list, help_text=_("A JSON array of strings or objects."))
    class Meta:
        verbose_name = _("System List")
        verbose_name_plural = _("System Lists")
    def __str__(self):
        return self.name

class Permit(models.Model):
    class PermitType(models.TextChoices):
        UNIVERSITY = 'UNIVERSITY', _('University')
        AZFA_CENTER = 'AZFA', _('AZFA Center')
        RECRUITMENT = 'RECRUITMENT', _('Recruitment Institution')
    class PermitStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', _('Active')
        EXPIRED = 'EXPIRED', _('Expired')
        PENDING = 'PENDING', _('Pending Review')
    permit_type = models.CharField(_("Permit Type"), max_length=20, choices=PermitType.choices)
    institution_name = models.CharField(_("Institution Name"), max_length=255)
    status = models.CharField(_("Status"), max_length=20, choices=PermitStatus.choices, default=PermitStatus.PENDING)
    issue_date = models.DateField(_("Issue Date"), null=True, blank=True)
    expiry_date = models.DateField(_("Expiry Date"), null=True, blank=True)
    permit_number = models.CharField(_("Permit Number"), max_length=50, unique=True)
    details = models.JSONField(_("Details"), default=dict, blank=True, help_text=_("Stores type-specific data."))
    class Meta:
        verbose_name = _("Permit")
        verbose_name_plural = _("Permits")
    def __str__(self):
        return f"{self.get_permit_type_display()} Permit for {self.institution_name}"

class Scholarship(models.Model):
    title = models.CharField(_("Scholarship Title"), max_length=255)
    university = models.ForeignKey("core.University", on_delete=models.CASCADE, related_name="scholarships")
    field_of_study = models.CharField(_("Field of Study"), max_length=255)
    description = models.TextField(_("Description"))
    duration = models.CharField(_("Duration"), max_length=100)
    financial_coverage = models.CharField(_("Financial Coverage"), max_length=255)
    application_deadline = models.DateField(_("Application Deadline"))
    requirements = models.JSONField(_("Requirements"), default=list)
    is_active = models.BooleanField(_("Is Active"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name = _("Scholarship")
        verbose_name_plural = _("Scholarships")
        ordering = ['-application_deadline', 'title']
    def __str__(self):
        return f"{self.title} at {self.university.name}"

class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(_("Title"), max_length=255)
    message = models.TextField(_("Message"))
    is_read = models.BooleanField(_("Is Read"), default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    link = models.URLField(_("Link"), blank=True, help_text=_("Optional link to a relevant page"))
    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        ordering = ['-timestamp']
    def __str__(self):
        return f"Notification for {self.user.email}: {self.title}"
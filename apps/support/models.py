# apps/support/models.py
import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

def generate_ticket_id():
    """Generates a unique, human-readable ticket ID like 'SPT-ABC-123'."""
    # This combination provides a good balance of uniqueness and readability.
    return f"SPT-{str(uuid.uuid4().hex[:3]).upper()}-{str(uuid.uuid4().int)[:3]}"

class SupportTicket(models.Model):
    class StatusChoices(models.TextChoices):
        OPEN = 'OPEN', _('Open')
        AWAITING_REPLY = 'AWAITING_REPLY', _('Awaiting Your Reply')
        CLOSED = 'CLOSED', _('Closed')
    
    ticket_id = models.CharField(
        _("Ticket ID"), max_length=20, unique=True, editable=False, default=generate_ticket_id
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="support_tickets"
    )
    subject = models.CharField(_("Subject"), max_length=255)
    category = models.CharField(_("Category"), max_length=100)
    status = models.CharField(
        _("Status"), max_length=20, choices=StatusChoices.choices, default=StatusChoices.OPEN
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Support Ticket")
        verbose_name_plural = _("Support Tickets")
        ordering = ['-updated_at']

    def __str__(self):
        return f"Ticket {self.ticket_id} - {self.subject}"

class TicketMessage(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField(_("Message"))
    attachment = models.FileField(
        _("Attachment"), upload_to='ticket_attachments/', null=True, blank=True
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Ticket Message")
        verbose_name_plural = _("Ticket Messages")
        ordering = ['timestamp']
    
    def __str__(self):
        return f"Message from {self.sender.email} on Ticket {self.ticket.ticket_id}"
# apps/support/admin.py
from django.contrib import admin
from .models import SupportTicket, TicketMessage

class TicketMessageInline(admin.TabularInline):
    """Allows viewing and adding messages directly within the ticket admin page."""
    model = TicketMessage
    extra = 1
    readonly_fields = ('sender', 'timestamp')
    fields = ('sender', 'message', 'attachment', 'timestamp')

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_id', 'subject', 'user', 'category', 'status', 'updated_at')
    list_filter = ('status', 'category', 'created_at')
    search_fields = ('ticket_id', 'subject', 'user__email')
    readonly_fields = ('ticket_id', 'created_at', 'updated_at')
    inlines = [TicketMessageInline]

@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    """A standalone admin view for messages, useful for searching all messages."""
    list_display = ('ticket', 'sender', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('message', 'sender__email', 'ticket__ticket_id')
    raw_id_fields = ('ticket', 'sender') # Better UI for selecting FKs with many options
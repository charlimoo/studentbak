# apps/support/views.py
from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from .models import SupportTicket, TicketMessage
from .serializers import (
    SupportTicketListSerializer, SupportTicketDetailSerializer,
    SupportTicketCreateSerializer, TicketMessageSerializer
)
# from apps.core.utils import create_notification  # Assuming a helper function for notifications

class SupportTicketViewSet(viewsets.ModelViewSet):
    """ViewSet for creating and viewing support tickets."""
    queryset = SupportTicket.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'ticket_id'

    def get_serializer_class(self):
        if self.action == 'create':
            return SupportTicketCreateSerializer
        if self.action == 'retrieve':
            return SupportTicketDetailSerializer
        return SupportTicketListSerializer

    def get_queryset(self):
        """
        Users can only see their own tickets.
        Staff with the 'SupportStaff' role can see all tickets.
        """
        user = self.request.user
        base_queryset = SupportTicket.objects.prefetch_related('messages__sender', 'user')
        
        # This assumes a role named 'SupportStaff' exists for your support team.
        if user.is_staff or user.roles.filter(name='SupportStaff').exists():
            return base_queryset
        return base_queryset.filter(user=user)

    def perform_create(self, serializer):
        """Handle the creation of the ticket and its initial message."""
        user = self.request.user
        message_text = serializer.validated_data.pop('message')
        attachment_file = serializer.validated_data.pop('attachment', None)
        
        with transaction.atomic():
            ticket = serializer.save(user=user)
            TicketMessage.objects.create(
                ticket=ticket, sender=user, message=message_text, attachment=attachment_file
            )
            # Example of creating a notification for staff:
            # create_notification(
            #     user_group='SupportStaff',
            #     title=f"New Ticket: {ticket.ticket_id}",
            #     message=f"A new support ticket has been opened by {user.email}.",
            #     link=f"/support/tickets/{ticket.ticket_id}"
            # )

    def create(self, request, *args, **kwargs):
        """Override create to return the detailed view of the new ticket."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        detail_serializer = SupportTicketDetailSerializer(serializer.instance)
        headers = self.get_success_headers(detail_serializer.data)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class TicketMessageViewSet(viewsets.ModelViewSet):
    """ViewSet for replying to an existing support ticket."""
    queryset = TicketMessage.objects.all()
    serializer_class = TicketMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filter messages to only those belonging to the specified ticket."""
        ticket_id = self.kwargs.get('ticket_ticket_id')
        return TicketMessage.objects.filter(ticket__ticket_id=ticket_id)

    def perform_create(self, serializer):
        """Handle the creation of a new message and update the parent ticket."""
        ticket_id = self.kwargs.get('ticket_ticket_id')
        try:
            ticket = SupportTicket.objects.get(ticket_id=ticket_id)
        except SupportTicket.DoesNotExist:
            raise permissions.NotFound("Ticket not found.")
            
        user = self.request.user
        is_staff = user.is_staff or user.roles.filter(name='SupportStaff').exists()

        # Permission check: user must be the ticket owner or a staff member.
        if ticket.user != user and not is_staff:
            raise permissions.PermissionDenied("You do not have permission to reply to this ticket.")
            
        with transaction.atomic():
            message = serializer.save(sender=user, ticket=ticket)
            
            # Update ticket status and timestamp
            ticket.updated_at = message.timestamp
            if is_staff:
                ticket.status = SupportTicket.StatusChoices.AWAITING_REPLY
                # Notify the user who created the ticket
                # create_notification(user=ticket.user, ...)
            else:
                ticket.status = SupportTicket.StatusChoices.OPEN
                # Notify support staff
                # create_notification(user_group='SupportStaff', ...)
            ticket.save()
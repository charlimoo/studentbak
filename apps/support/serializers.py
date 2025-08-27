# start of apps/support/serializers.py
# apps/support/serializers.py
from rest_framework import serializers
from .models import SupportTicket, TicketMessage
from apps.users.serializers import UserSerializer

class TicketMessageSerializer(serializers.ModelSerializer):
    """Serializer for an individual ticket message."""
    sender = UserSerializer(read_only=True)
    class Meta:
        model = TicketMessage
        fields = ['id', 'sender', 'message', 'attachment', 'timestamp']
        read_only_fields = ['id', 'sender', 'timestamp']

class SupportTicketListSerializer(serializers.ModelSerializer):
    """A simplified serializer for listing multiple support tickets."""
    class Meta:
        model = SupportTicket
        fields = ['ticket_id', 'subject', 'category', 'status', 'updated_at']

class SupportTicketDetailSerializer(serializers.ModelSerializer):
    """A detailed serializer for viewing a single ticket and its full conversation."""
    user = UserSerializer(read_only=True)
    messages = TicketMessageSerializer(many=True, read_only=True)
    class Meta:
        model = SupportTicket
        fields = ['ticket_id', 'user', 'subject', 'category', 'status', 'created_at', 'updated_at', 'messages']

class SupportTicketCreateSerializer(serializers.ModelSerializer):
    """Serializer used for creating a new support ticket."""
    # The first message is created along with the ticket, so we accept its content here.
    # These fields do not exist on the SupportTicket model but are used by the view.
    message = serializers.CharField(write_only=True, required=True, min_length=10)
    attachment = serializers.FileField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = SupportTicket
        # The user will be set automatically from the request.
        fields = ['subject', 'category', 'message', 'attachment']
# end of apps/support/serializers.py
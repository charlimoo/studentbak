# apps/support/urls.py
from django.urls import path, include
from rest_framework_nested import routers
from .views import SupportTicketViewSet, TicketMessageViewSet

# Main router for the top-level /tickets/ endpoint
router = routers.DefaultRouter()
router.register(r'tickets', SupportTicketViewSet, basename='ticket')

# Nested router for messages, creating URLs like:
# /api/v1/support/tickets/{ticket_ticket_id}/messages/
tickets_router = routers.NestedDefaultRouter(router, r'tickets', lookup='ticket')
tickets_router.register(r'messages', TicketMessageViewSet, basename='ticket-message')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(tickets_router.urls)),
]
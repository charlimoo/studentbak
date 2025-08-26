# apps/applications/filters.py
import django_filters
from django.db.models import Q
from .models import Application

class ApplicationFilter(django_filters.FilterSet):
    """
    FilterSet for the Application model.
    Enables filtering by status, creation date, and provides a generic search field.
    """
    # Define a search filter that looks across multiple relevant fields
    search = django_filters.CharFilter(
        method='filter_by_search',
        label="Search by applicant name, email, or tracking code"
    )

    class Meta:
        model = Application
        fields = {
            'status': ['exact', 'in'],  # e.g., ?status=PENDING_REVIEW or ?status__in=APPROVED,REJECTED
            'created_at': ['gte', 'lte', 'exact'], # e.g., ?created_at__gte=2024-01-01 (Greater than or equal to)
        }

    def filter_by_search(self, queryset, name, value):
        """
        Custom method to perform a case-insensitive search on the applicant's
        full name, their email, or the application's tracking code.
        """
        if not value:
            return queryset
            
        return queryset.filter(
            Q(full_name__icontains=value) |
            Q(applicant__email__icontains=value) |
            Q(tracking_code__icontains=value)
        )
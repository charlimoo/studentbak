# apps/users/filters.py
import django_filters
from django.db.models import Q
from .models import User

class UserFilter(django_filters.FilterSet):
    """
    FilterSet for the User model, designed for admin management lists.
    Enables filtering by roles and status, and provides a generic search field.
    """
    # Allows partial, case-insensitive search across multiple fields
    search = django_filters.CharFilter(
        method='filter_by_search_term',
        label="Search by Full Name or Email"
    )
    
    class Meta:
        model = User
        fields = {
            'roles': ['exact'],  # e.g., ?roles=1
            'organization_unit': ['exact'], # e.g., ?organization_unit=5
            'is_active': ['exact'], # e.g., ?is_active=true
        }

    def filter_by_search_term(self, queryset, name, value):
        """
        Custom method to perform a search on the user's full name and email address.
        """
        if not value:
            return queryset
            
        return queryset.filter(
            Q(full_name__icontains=value) | Q(email__icontains=value)
        )
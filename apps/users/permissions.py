# start of apps/users/permissions.py
# apps/users/permissions.py
from rest_framework.permissions import BasePermission

class IsHeadOfOrganization(BasePermission):
    """Allows access only to users with the 'HeadOfOrganization' role."""
    message = "You do not have permission to perform this action. Administrator access is required."
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and
            request.user.roles.filter(name='HeadOfOrganization').exists()
        )

# --- FIX: NEW PERMISSION CLASS FOR INSTITUTIONS ---
class IsRecruitmentInstitution(BasePermission):
    """
    Allows access only to users with the 'Recruitment Institution' role.
    """
    message = "You must be a Recruitment Institution to perform this action."
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and
            request.user.roles.filter(name='Recruitment Institution').exists()
        )

class HasPermission(BasePermission):
    """
    DRF permission class that checks if a user has a specific permission codename
    through their assigned roles.
    
    Usage in a view:
    permission_classes = [permissions.IsAuthenticated, HasPermission]
    required_permission = 'view_all_applications'
    """
    def has_permission(self, request, view):
        required_permission = getattr(view, 'required_permission', None)
        if not required_permission:
            # Deny access if the view doesn't specify a required permission for safety.
            return False

        user = request.user
        if not (user and user.is_authenticated):
            return False

        # Superusers bypass all permission checks.
        if user.is_superuser:
            return True

        # Check if any of the user's roles contain the required permission.
        # This is an efficient query that checks the relationship across tables.
        return user.roles.filter(permissions__codename=required_permission).exists()
# end of apps/users/permissions.py
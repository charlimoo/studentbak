# apps/applications/permissions.py
from rest_framework.permissions import BasePermission
from .models import Application, ApplicationTask

class IsApplicantOwner(BasePermission):
    """
    Custom permission to only allow owners of an object to access it.
    - Read access is granted to the owner at any time.
    - Write access (PUT, PATCH) is only granted if the application status
      is 'PENDING_CORRECTION'.
    """
    message = "You do not have permission to perform this action on this application."

    def has_object_permission(self, request, view, obj):
        # The object 'obj' is an Application instance.
        if not isinstance(obj, Application):
            return False # Ensure we are working with an Application object

        # Ownership check is the first and most important step.
        if obj.applicant != request.user:
            return False

        # For safe methods (GET, HEAD, OPTIONS), ownership is sufficient.
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True

        # For unsafe methods (PUT, PATCH), we require a specific status.
        if request.method in ('PUT', 'PATCH'):
            if obj.status == Application.StatusChoices.PENDING_CORRECTION:
                return True
            else:
                # If the status is wrong, provide a more specific error message.
                self.message = "You can only edit an application that is pending correction."
                return False
        
        # Deny other methods like DELETE by default.
        return False

class IsRelatedToApplication(BasePermission):
    """
    Allows access if the user is:
    1. The applicant who owns the application.
    2. A University Expert whose university is part of the application's choices.
    3. The Head of Organization.
    """
    message = "You are not authorized to view this application."

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        # Rule 1: Applicant owner
        if obj.applicant == user:
            return True

        # Rule 3: Head of Organization has universal access
        if user.roles.filter(name='HeadOfOrganization').exists():
            return True

        # Rule 2: University Expert
        if user.roles.filter(name='UniversityExpert').exists():
            expert_universities_ids = user.universities.all().values_list('id', flat=True)
            application_universities_ids = obj.university_choices.all().values_list('university_id', flat=True)
            # Check for any intersection between the two sets of university IDs
            if set(expert_universities_ids).intersection(set(application_universities_ids)):
                return True
        
        return False

class IsAssignedExpert(BasePermission):
    """
    Allows access only to the expert who has claimed the task for a specific university.
    """
    message = "This task is not assigned to you."

    def has_object_permission(self, request, view, obj):
        user = request.user
        # This permission assumes the view context contains the university_pk
        university_pk = view.kwargs.get('university_pk')
        if not university_pk:
            return False
            
        return ApplicationTask.objects.filter(
            application=obj,
            university_id=university_pk,
            assigned_expert=user
        ).exists()
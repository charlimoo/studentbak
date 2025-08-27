# start of apps/applications/views.py
# apps/applications/views.py
from django.db import transaction, models
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework import filters as drf_filters
from django_filters.rest_framework import DjangoFilterBackend
import logging

from .models import Application, ApplicationTask, ApplicationLog, InternalNote
from .serializers import (
    ApplicationCreateSerializer, ApplicationListSerializer, ApplicationDetailSerializer,
    ApplicationUpdateSerializer, ApplicationActionSerializer, TaskReassignmentSerializer,
    InternalNoteSerializer
)
from .permissions import IsApplicantOwner, IsRelatedToApplication, IsAssignedExpert
from .filters import ApplicationFilter
from apps.core.models import University
from apps.users.permissions import HasPermission, IsHeadOfOrganization
from .exporters import generate_excel_response, generate_pdf_response

# Get a logger instance for this file
logger = logging.getLogger(__name__)

class ApplicationViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin,
                         mixins.UpdateModelMixin, mixins.ListModelMixin,
                         viewsets.GenericViewSet):
    """ViewSet for handling student applications."""
    queryset = Application.objects.select_related('applicant').prefetch_related(
        'academic_histories', 'university_choices__university', 'university_choices__program',
        'documents', 'logs__actor', 'tasks__university', 'tasks__assigned_expert', 'internal_notes__author'
    ).all()
    lookup_field = 'tracking_code'
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, drf_filters.OrderingFilter, drf_filters.SearchFilter]
    filterset_class = ApplicationFilter
    search_fields = ['full_name', 'applicant__email', 'tracking_code']
    ordering_fields = ['created_at', 'status', 'updated_at']

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return ApplicationUpdateSerializer
        if self.action == 'create':
            return ApplicationCreateSerializer
        if self.action == 'retrieve':
            return ApplicationDetailSerializer
        if self.action == 'take_action':
            return ApplicationActionSerializer
        return ApplicationListSerializer


    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'my_applications']:
            return [permissions.IsAuthenticated(), IsApplicantOwner()]
        if self.action in ['retrieve', 'claim', 'take_action']:
            return [permissions.IsAuthenticated(), IsRelatedToApplication()]
        # --- FIX: Add new permission scope for the university_applications action ---
        if self.action in ['workbench', 'all_applications', 'university_applications']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.pop('partial', False))
        
        if not serializer.is_valid():
            logger.error(
                "[UPDATE VALIDATION FAILED] User: %s, Application: %s, Errors: %s",
                request.user.email,
                instance.tracking_code,
                serializer.errors
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            self.perform_update(serializer)
            application = serializer.instance

            doc_index = 0
            while f'documents[{doc_index}][file]' in request.FILES:
                doc_type = request.data.get(f'documents[{doc_index}][document_type]')
                doc_file = request.FILES.get(f'documents[{doc_index}][file]')
                
                if doc_type and doc_file:
                    ApplicationDocument.objects.create(
                        application=application,
                        document_type=doc_type,
                        file=doc_file
                    )
                doc_index += 1
            
            application.status = Application.StatusChoices.PENDING_REVIEW
            application.save(update_fields=['status'])
            
            application.tasks.filter(status=ApplicationTask.StatusChoices.COMPLETED).update(
                status=ApplicationTask.StatusChoices.UNCLAIMED,
                assigned_expert=None, decision=ApplicationTask.DecisionChoices.PENDING
            )
            
            ApplicationLog.objects.create(
                application=application, 
                actor=request.user, 
                action="Application resubmitted after correction."
            )
            
        return Response(ApplicationDetailSerializer(instance).data)

    @action(detail=False, methods=['get'], url_path='my')
    def my_applications(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        user_applications = queryset.filter(applicant=request.user)
        page = self.paginate_queryset(user_applications)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(user_applications, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='my-submitted')
    def my_submitted_applications(self, request):
        user = request.user
        if not user.roles.filter(name='Recruitment Institution').exists():
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        
        institution_universities = user.universities.all()
        if not institution_universities.exists():
             return Response({"count": 0, "next": None, "previous": None, "results": []})

        queryset = self.filter_queryset(self.get_queryset())
        
        institution_apps = queryset.filter(
            university_choices__university__in=institution_universities
        ).distinct()
        
        page = self.paginate_queryset(institution_apps)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(institution_apps, many=True)
        return Response(serializer.data)
    
    # --- FIX START: REFINED WORKBENCH LOGIC ---
    @action(detail=False, methods=['get'], url_path='workbench')
    def workbench(self, request):
        user = request.user
        logger.info("[WORKBENCH] Starting for user: %s", user.email)

        if not user.roles.filter(name='UniversityExpert').exists():
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        expert_universities = user.universities.all()
        if not expert_universities.exists():
            # If an expert is not assigned to any university, their workbench is empty.
            return Response({"count": 0, "next": None, "previous": None, "results": []})

        logger.info("[WORKBENCH] User is expert for: %s", list(expert_universities.values_list('name', flat=True)))
        
        # 1. Get tasks unclaimed for the expert's universities
        unclaimed_q = models.Q(university__in=expert_universities, status=ApplicationTask.StatusChoices.UNCLAIMED)
        # 2. Get tasks already assigned to this expert
        assigned_q = models.Q(assigned_expert=user, status=ApplicationTask.StatusChoices.ASSIGNED)
        
        # Find all application IDs that match these task criteria AND are in PENDING_REVIEW status
        application_ids = ApplicationTask.objects.filter(unclaimed_q | assigned_q).filter(
            application__status=Application.StatusChoices.PENDING_REVIEW
        ).values_list('application_id', flat=True).distinct()
        
        logger.info("[WORKBENCH] Found %d relevant application(s) in PENDING_REVIEW state.", len(application_ids))

        # Final queryset for the applications
        queryset = self.get_queryset().filter(id__in=application_ids)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    # --- FIX END: REFINED WORKBENCH LOGIC ---

    # --- FIX START: NEW ACTION FOR UNIVERSITY-SCOPED APPLICATIONS ---
    @action(detail=False, methods=['get'], url_path='university-apps')
    def university_applications(self, request):
        """
        Returns all applications related to the universities of the logged-in
        UniversityExpert, for the "همه درخواست ها" page.
        """
        user = request.user
        if not user.roles.filter(name='UniversityExpert').exists():
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        expert_universities = user.universities.all()
        if not expert_universities.exists():
            return Response({"count": 0, "next": None, "previous": None, "results": []})

        # Filter applications where at least one of the university choices
        # matches one of the expert's affiliated universities.
        queryset = self.get_queryset().filter(
            university_choices__university__in=expert_universities
        ).distinct()

        # Apply standard filtering (search, etc.) and pagination
        filtered_queryset = self.filter_queryset(queryset)
        page = self.paginate_queryset(filtered_queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(filtered_queryset, many=True)
        return Response(serializer.data)
    # --- FIX END: NEW ACTION FOR UNIVERSITY-SCOPED APPLICATIONS ---

    @action(detail=False, methods=['get'], url_path='all', permission_classes=[IsHeadOfOrganization])
    def all_applications(self, request):
        all_apps = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(all_apps)
        serializer = self.get_serializer(page, many=True) if page is not None else self.get_serializer(all_apps, many=True)
        return self.get_paginated_response(serializer.data) if page is not None else Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='staff-all')
    def staff_all_applications(self, request):
        if not request.user.is_staff:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        all_apps = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(all_apps)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(all_apps, many=True)
        return Response(serializer.data)
    
    
    def _get_export_response(self, request, queryset):
        file_format = request.query_params.get('format', 'xlsx').lower()
        if file_format == 'xlsx':
            return generate_excel_response(queryset)
        elif file_format == 'pdf':
            return generate_pdf_response(queryset)
        return Response({"detail": "Unsupported format. Choose 'xlsx' or 'pdf'."}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='my/export')
    def export_my_applications(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(applicant=request.user)
        return self._get_export_response(request, queryset)
        
    @action(detail=False, methods=['get'], url_path='all/export', permission_classes=[IsHeadOfOrganization])
    def export_all_applications(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        return self._get_export_response(request, queryset)

    @action(detail=True, methods=['post'], url_path='claim/(?P<university_pk>[^/.]+)')
    def claim(self, request, tracking_code=None, university_pk=None):
        application, user = self.get_object(), request.user
        university = get_object_or_404(University, pk=university_pk)
        
        if not user.universities.filter(pk=university.pk).exists():
            return Response({"detail": "You are not an expert for this university."}, status=status.HTTP_403_FORBIDDEN)
        
        task = get_object_or_404(ApplicationTask, application=application, university=university, status=ApplicationTask.StatusChoices.UNCLAIMED)
        
        task.assigned_expert = user
        task.status = ApplicationTask.StatusChoices.ASSIGNED
        task.save()
        
        ApplicationLog.objects.create(application=application, actor=user, action=f"Task for {university.name} claimed.")
        return Response({"status": "Task successfully claimed."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='action/(?P<university_pk>[^/.]+)', permission_classes=[permissions.IsAuthenticated, IsRelatedToApplication, IsAssignedExpert])
    def take_action(self, request, tracking_code=None, university_pk=None):
        application, user = self.get_object(), request.user
        university = get_object_or_404(University, pk=university_pk)
        task = get_object_or_404(ApplicationTask, application=application, university=university, assigned_expert=user)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        action_type = serializer.validated_data['action']
        comment = serializer.validated_data.get('comment', '')
        
        if action_type == 'CORRECT':
            with transaction.atomic():
                application.status = Application.StatusChoices.PENDING_CORRECTION
                application.save(update_fields=['status'])
                ApplicationLog.objects.create(
                    application=application, actor=user, 
                    action="Application requires correction.", comment=comment
                )
            return Response({"status": "Application sent for correction."}, status=status.HTTP_200_OK)

        with transaction.atomic():
            log_action = f"{action_type.capitalize()}d for {university.name}"
            
            if action_type == 'APPROVE':
                task.decision = ApplicationTask.DecisionChoices.APPROVED
            elif action_type == 'REJECT':
                task.decision = ApplicationTask.DecisionChoices.REJECTED
            
            task.status = ApplicationTask.StatusChoices.COMPLETED
            task.save()
            ApplicationLog.objects.create(application=application, actor=user, action=log_action, comment=comment)

        return Response({"status": f"Decision '{action_type}' recorded successfully."}, status=status.HTTP_200_OK)


class TaskViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """ViewSet for managing individual ApplicationTasks, e.g., reassignment."""
    queryset = ApplicationTask.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsHeadOfOrganization] 
    
    @action(detail=True, methods=['post'], url_path='reassign')
    def reassign(self, request, pk=None):
        task = self.get_object()
        serializer = TaskReassignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_expert = serializer.validated_data['user_id']
        old_expert_email = task.assigned_expert.email if task.assigned_expert else "Unassigned"

        if not new_expert.roles.filter(name='UniversityExpert').exists():
            return Response({"detail": "Target user is not a UniversityExpert."}, status=status.HTTP_400_BAD_REQUEST)
        if not new_expert.universities.filter(id=task.university.id).exists():
            return Response({"detail": f"Target expert is not affiliated with {task.university.name}."}, status=status.HTTP_400_BAD_REQUEST)
        if task.status == ApplicationTask.StatusChoices.COMPLETED:
            return Response({"detail": "Cannot reassign a completed task."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            task.assigned_expert = new_expert
            task.status = ApplicationTask.StatusChoices.ASSIGNED
            task.save()
            ApplicationLog.objects.create(
                application=task.application, actor=request.user,
                action=f"Task for {task.university.name} reassigned from {old_expert_email} to {new_expert.email} by admin."
            )
        return Response({"status": "Task successfully reassigned."}, status=status.HTTP_200_OK)

class InternalNoteViewSet(viewsets.ModelViewSet):
    """ViewSet for managing internal notes on an application."""
    queryset = InternalNote.objects.all()
    serializer_class = InternalNoteSerializer
    permission_classes = [permissions.IsAuthenticated, IsRelatedToApplication]
    required_permission = 'view_internal_notes'

    def get_queryset(self):
        application_tracking_code = self.kwargs.get('application_tracking_code')
        return InternalNote.objects.filter(application__tracking_code=application_tracking_code)
    
    def perform_create(self, serializer):
        application_tracking_code = self.kwargs.get('application_tracking_code')
        application = get_object_or_404(Application, tracking_code=application_tracking_code)
        serializer.save(author=self.request.user, application=application)
# end of apps/applications/views.py
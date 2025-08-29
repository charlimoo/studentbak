# start of apps/applications/serializers.py
# apps/applications/serializers.py
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction # --- FIX: Import transaction for atomic operations
from django.core.validators import FileExtensionValidator
from rest_framework import serializers
from drf_writable_nested.serializers import WritableNestedModelSerializer
import copy # --- FIX: Import copy to duplicate nested data

from .models import (
    Application, AcademicHistory, UniversityChoice,
    ApplicationDocument, ApplicationLog, ApplicationTask, InternalNote
)
from apps.core.models import Program, University
from apps.users.models import User, Role
from apps.core.serializers import UniversitySerializer, ProgramSerializer
from apps.users.serializers import UserSerializer

# --- Validation & Helper Functions ---
def file_size_validator(value):
    limit = 5 * 1024 * 1024  # 5 MB
    if value.size > limit:
        raise DjangoValidationError('File too large. Size should not exceed 5 MB.')

def validate_application_form_data(application_type, form_data):
    required_fields = {}
    if application_type == 'VISA_EXTENSION':
        required_fields = {'current_visa_number': str, 'current_visa_expiry': str, 'requested_duration': str}
    elif application_type == 'INTERNAL_EXIT_PERMIT':
        required_fields = {'destination_university': str, 'reason_for_request': str}

    for field, field_type in required_fields.items():
        if field not in form_data:
            raise serializers.ValidationError(f"'{field}' is a required field for '{application_type}'.")
        if not isinstance(form_data.get(field), field_type):
            raise serializers.ValidationError(f"'{field}' must be of type {field_type.__name__}.")
    return form_data

# --- Nested & Read-Only Serializers ---
class AcademicHistorySerializer(serializers.ModelSerializer):
    certificate_file = serializers.FileField(use_url=True, read_only=True, required=False, allow_null=True)
    class Meta:
        model = AcademicHistory
        # --- FIX: INCLUDE 'id' IN THE FIELDS ---
        fields = ['id', 'degree_level', 'country', 'university_name', 'field_of_study', 'gpa', 'certificate_file']
        # Make 'id' optional for creation
        extra_kwargs = {'id': {'read_only': False, 'required': False}}

class UniversityChoiceSerializer(serializers.ModelSerializer):
    university = UniversitySerializer(read_only=True)
    program = ProgramSerializer(read_only=True)
    university_id = serializers.PrimaryKeyRelatedField(queryset=University.objects.all(), write_only=True, source='university')
    program_id = serializers.PrimaryKeyRelatedField(queryset=Program.objects.all(), write_only=True, source='program')
    class Meta:
        model = UniversityChoice
        fields = ['id', 'university', 'program', 'priority', 'university_id', 'program_id']
        extra_kwargs = {'id': {'read_only': False, 'required': False}}


class ApplicationDocumentSerializer(serializers.ModelSerializer):
    # This serializer is now used for both reading (displaying links)
    # and writing (accepting new files). `drf-writable-nested` will handle it.
    class Meta:
        model = ApplicationDocument
        fields = ['id', 'document_type', 'file']
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            # File is required when creating, but not when just viewing.
            # The main serializer's 'required=False' on the field handles this.
            'file': {'use_url': True} 
        }

class ApplicationLogSerializer(serializers.ModelSerializer):
    actor = UserSerializer(read_only=True)
    comment = serializers.CharField() # Ensure comment is serialized as a string
    class Meta:
        model = ApplicationLog
        fields = ['id', 'actor', 'action', 'comment', 'timestamp']

class ApplicationTaskSerializer(serializers.ModelSerializer):
    university = UniversitySerializer(read_only=True)
    assigned_expert = UserSerializer(read_only=True)
    class Meta:
        model = ApplicationTask
        fields = ['id', 'university', 'status', 'decision', 'assigned_expert']

class InternalNoteSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    class Meta:
        model = InternalNote
        fields = ['id', 'author', 'message', 'timestamp']
        read_only_fields = ['id', 'author', 'timestamp']


# --- Main Application Serializers ---
class ApplicationListSerializer(serializers.ModelSerializer):
    applicant = UserSerializer(read_only=True)
    class Meta:
        model = Application
        fields = ['tracking_code', 'status', 'application_type', 'full_name', 'created_at', 'applicant']


class ApplicationDetailSerializer(serializers.ModelSerializer):
    applicant = UserSerializer(read_only=True)
    academic_histories = AcademicHistorySerializer(many=True, read_only=True)
    university_choices = UniversityChoiceSerializer(many=True, read_only=True)
    # --- FIX: Use the corrected, writable serializer for display ---
    documents = ApplicationDocumentSerializer(many=True, read_only=True)
    logs = ApplicationLogSerializer(many=True, read_only=True)
    tasks = ApplicationTaskSerializer(many=True, read_only=True)
    internal_notes = InternalNoteSerializer(many=True, read_only=True) 
    class Meta:
        model = Application
        fields = '__all__'


class ApplicationCreateSerializer(WritableNestedModelSerializer):
    applicant = serializers.HiddenField(default=serializers.CurrentUserDefault())
    applicant_email = serializers.EmailField(write_only=True, required=False)
    application_type = serializers.ChoiceField(choices=Application.ApplicationType.choices)
    form_data = serializers.JSONField(required=False, initial=dict)
    academic_histories = AcademicHistorySerializer(many=True, required=False)
    university_choices = UniversityChoiceSerializer(many=True, required=False)
    documents = ApplicationDocumentSerializer(many=True, required=False)


    class Meta:
        model = Application
        exclude = ('status', 'submitted_by_institution')

    def validate(self, data):
        user = self.context['request'].user
        is_institution = user.roles.filter(name='Recruitment Institution').exists()

        if is_institution:
            if not data.get('applicant_email'):
                raise serializers.ValidationError({"applicant_email": "This field is required for institution submissions."})
            if not data.get('full_name'):
                raise serializers.ValidationError({"full_name": "Applicant's full name is required for institution submissions."})
        
        app_type = data.get('application_type')
        if not app_type and self.instance:
            app_type = self.instance.application_type
            
        form_data = data.get('form_data', {})
        
        if app_type != 'NEW_ADMISSION' and not form_data:
            raise serializers.ValidationError({"form_data": "This field is required for the selected application type."})
            
        data['form_data'] = validate_application_form_data(app_type, form_data)
        
        if app_type == 'NEW_ADMISSION':
            if not data.get('academic_histories'):
                raise serializers.ValidationError({"academic_histories": "This field is required for New Admission."})
            if not data.get('university_choices'):
                raise serializers.ValidationError({"university_choices": "This field is required for New Admission."})
            choices_data = data.get('university_choices', [])
            priorities = [choice['priority'] for choice in choices_data]
            if len(priorities) != len(set(priorities)):
                raise serializers.ValidationError({"university_choices": "Priorities must be unique."})
        return data

    def create(self, validated_data):
        request_user = self.context['request'].user
        is_institution = request_user.roles.filter(name='Recruitment Institution').exists()

        # Pop nested data that needs to be duplicated for each new application
        university_choices_data = validated_data.pop('university_choices', [])
        academic_histories_data = validated_data.pop('academic_histories', [])
        documents_data = validated_data.pop('documents', [])

        # Handle institution-submitted applications to find or create the applicant
        if is_institution:
            applicant_email = validated_data.pop('applicant_email')
            applicant_full_name = validated_data.get('full_name')
            applicant, created = User.objects.get_or_create(
                email__iexact=applicant_email,
                defaults={'email': applicant_email.lower(), 'full_name': applicant_full_name}
            )
            if created:
                applicant_role, _ = Role.objects.get_or_create(name='Applicant')
                applicant.roles.add(applicant_role)
            
            validated_data['applicant'] = applicant
            validated_data['submitted_by_institution'] = request_user
        
        created_applications = []
        # Use a transaction to ensure all or no applications are created
        with transaction.atomic():
            for choice_data in university_choices_data:
                app_data = copy.deepcopy(validated_data)
                new_application = Application.objects.create(**app_data)
                UniversityChoice.objects.create(application=new_application, **choice_data)
                for history_data in academic_histories_data:
                    AcademicHistory.objects.create(application=new_application, **history_data)
                for doc_data in documents_data:
                    ApplicationDocument.objects.create(application=new_application, **doc_data)
                ApplicationLog.objects.create(application=new_application, actor=request_user, action="Application submitted.")
                ApplicationTask.objects.create(application=new_application, university=choice_data['university'])
                created_applications.append(new_application)
        return created_applications[0] if created_applications else None


# --- THIS IS THE SERIALIZER THAT WAS MISSING ---
class ApplicationUpdateSerializer(WritableNestedModelSerializer):
    """Serializer for updating/resubmitting an application."""
    academic_histories = AcademicHistorySerializer(many=True, required=False)
    university_choices = UniversityChoiceSerializer(many=True, required=False)
    form_data = serializers.JSONField(required=False)
    documents = ApplicationDocumentSerializer(many=True, required=False)


    class Meta:
        model = Application
        fields = [
            'application_type', 'full_name', 'date_of_birth', 'country_of_residence',
            'father_name', 'grandfather_name', 'email', 'form_data',
            'academic_histories', 'university_choices',
            'documents' 
        ]
        read_only_fields = ('application_type',)
        
    validate = ApplicationCreateSerializer.validate

    # --- FIX START: Override update to prevent deleting old documents ---
    def update(self, instance, validated_data):
        # We pop 'documents' so drf-writable-nested does not process it.
        # The view will handle creating new documents manually.
        validated_data.pop('documents', None)
        return super().update(instance, validated_data)
    # --- FIX END ---


# --- Action-Specific Serializers ---
class ApplicationActionSerializer(serializers.Serializer):
    ACTION_CHOICES = [('APPROVE', 'Approve'), ('REJECT', 'Reject'), ('CORRECT', 'Send for Correction')]
    action = serializers.ChoiceField(choices=ACTION_CHOICES, required=True)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=1000)

    def validate_comment(self, value):
        action = self.initial_data.get('action')
        if action in ['REJECT', 'CORRECT'] and not value:
            raise serializers.ValidationError('A comment is required for this action.')
        return value

class TaskReassignmentSerializer(serializers.Serializer):
    user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), label="New Expert User ID")
    
# end of apps/applications/serializers.py
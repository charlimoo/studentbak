# apps/core/management/commands/clean_db.py
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from apps.core.models import University, Program
from apps.users.models import Role
from apps.applications.models import Application # <-- Import the Application model

User = get_user_model()

class Command(BaseCommand):
    help = 'Cleans the database of all test data created by populate_db.'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Starting database cleaning...'))

        # Delete in an order that respects foreign keys

        # 1. NEW: Delete all Application objects first.
        # This will cascade and delete related UniversityChoice, AcademicHistory, etc.
        # which will "unprotect" the Program and University models.
        apps_deleted, _ = Application.objects.all().delete()
        self.stdout.write(f'Deleted {apps_deleted} Application objects (and their related data).')
        
        # 2. Delete Programs (now unprotected)
        programs_deleted, _ = Program.objects.all().delete()
        self.stdout.write(f'Deleted {programs_deleted} Program objects.')

        # 3. Delete Universities (now unprotected)
        universities_deleted, _ = University.objects.all().delete()
        self.stdout.write(f'Deleted {universities_deleted} University objects.')

        # 4. Delete all non-superuser users
        users_deleted, _ = User.objects.filter(is_superuser=False).delete()
        self.stdout.write(f'Deleted {users_deleted} non-superuser User objects.')

        # 5. Delete Roles
        role_names_to_delete = [
            'Applicant',
            'UniversityExpert',
            'Recruitment Institution',
            'HeadOfOrganization',
        ]
        roles_deleted, _ = Role.objects.filter(name__in=role_names_to_delete).delete()
        self.stdout.write(f'Deleted {roles_deleted} Role objects.')


        self.stdout.write(self.style.SUCCESS('Database cleaning complete! You can now run populate_db again.'))
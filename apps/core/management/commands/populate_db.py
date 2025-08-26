# start of apps/core/management/commands/populate_db.py
# apps/core/management/commands/populate_db.py
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from apps.core.models import University, Program
from apps.users.models import Role

User = get_user_model()

# --- Data Definitions based on the provided document ---
# This structure maps universities to their specific, allowed programs.
UNIVERSITY_DATA = {
    "دانشگاه تهران": [
        "مدیریت",
        "صنایع",
        "مهندسی نرم افزار",
        "اقتصاد",
    ],
    "دانشگاه صنعتی شریف": [
        "مدیریت",
        "صنایع",
        "مهندسی نرم افزار",
        "اقتصاد",
        "فلسفه علم و فناوری",
    ],
    "دانشگاه امیرکبیر": [
        "مدیریت",
        "صنایع",
        "مهندسی نرم افزار",
        "اقتصاد",
    ],
    "دانشگاه علامه طباطبایی": [
        # "مهندسی نرم افزار" is intentionally excluded as per the document.
        "مدیریت",
        "صنایع",
        "اقتصاد",
        "فلسفه علم و فناوری",
    ],
    "دانشگاه شهید بهشتی": [
        "مدیریت",
        "صنایع",
        "مهندسی نرم افزار",
        "اقتصاد",
        "فلسفه علم و فناوری",
    ],
}

class Command(BaseCommand):
    help = 'Populates the database with initial data for testing and development based on the project document.'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting database population...'))

        if University.objects.exists() or User.objects.filter(is_superuser=False).exists():
            self.stdout.write(self.style.WARNING('Database already contains data. Run `clean_db` first. Skipping population.'))
            return

        # 1. Create Roles
        self.stdout.write('Creating roles...')
        applicant_role, _ = Role.objects.get_or_create(name='Applicant', description='A standard applicant user.')
        expert_role, _ = Role.objects.get_or_create(name='UniversityExpert', description='A university expert who reviews applications.')
        institution_role, _ = Role.objects.get_or_create(name='Recruitment Institution', description='A partner institution that submits applications.')
        head_role, _ = Role.objects.get_or_create(name='HeadOfOrganization', description='An administrator with full access.')

        # 2. Create Universities and Programs
        self.stdout.write('Creating universities and programs from document...')
        for uni_name, programs in UNIVERSITY_DATA.items():
            university, created = University.objects.get_or_create(name=uni_name)
            if created:
                self.stdout.write(f'  - Created University: {uni_name}')
            for prog_name in programs:
                Program.objects.get_or_create(university=university, name=prog_name)
        
        uni_tehran = University.objects.get(name="دانشگاه تهران")
        uni_sharif = University.objects.get(name="دانشگاه صنعتی شریف")

        # 3. Create Test Users
        self.stdout.write('Creating test user accounts...')
        
        # Student User (as requested)
        student_user = User.objects.create_user(
            email='ali.karamudini19@gmail.com',
            full_name='علی کرم الدینی',
            password='Aa793145268'
        )
        student_user.roles.add(applicant_role)
        self.stdout.write(self.style.SUCCESS('  - Created Student: ali.karamudini19@gmail.com (pw: Aa793145268)'))
        
        # University Expert
        expert_user = User.objects.create_user(
            email='expert@university.com',
            full_name='کارشناس دانشگاه',
            password='password123',
            is_staff=True
        )
        expert_user.roles.add(expert_role)
        expert_user.universities.add(uni_tehran)
        self.stdout.write(self.style.SUCCESS('  - Created University Expert: expert@university.com (pw: password123)'))

        # Recruitment Institution
        inst_user = User.objects.create_user(
            email='institution@recruitment.com',
            full_name='موسسه اعزام دانشجو',
            password='password123'
        )
        inst_user.roles.add(institution_role)
        # --- FIX: Associate institution with universities to allow viewing of applicants ---
        inst_user.universities.add(uni_tehran)
        inst_user.universities.add(uni_sharif)
        self.stdout.write(self.style.SUCCESS('  - Created Institution User: institution@recruitment.com (pw: password123)'))

        # Head of Organization (Admin)
        head_user = User.objects.create_user(
            email='head@organization.com',
            full_name='رئیس سازمان',
            password='password123',
            is_staff=True
        )
        head_user.roles.add(head_role)
        self.stdout.write(self.style.SUCCESS('  - Created Head of Org: head@organization.com (pw: password123)'))

        self.stdout.write(self.style.SUCCESS('Database population complete!'))
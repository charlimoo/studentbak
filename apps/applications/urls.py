# apps/applications/urls.py
from django.urls import path, include
from rest_framework_nested import routers
from .views import ApplicationViewSet, TaskViewSet, InternalNoteViewSet

router = routers.DefaultRouter()
router.register(r'applications', ApplicationViewSet, basename='application')
router.register(r'tasks', TaskViewSet, basename='task')

# --- ADD THIS NESTED ROUTER ---
applications_router = routers.NestedDefaultRouter(router, r'applications', lookup='application')
applications_router.register(r'notes', InternalNoteViewSet, basename='application-notes')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(applications_router.urls)), # <-- ADD THIS LINE
]
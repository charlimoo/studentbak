# apps/core/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers
from .views import (
    UniversityViewSet, ProgramViewSet, DocumentTypesView, OrganizationChartView,
    NotificationTemplateViewSet, SystemListNameView, SystemListDetailView, PermitViewSet,
    ScholarshipViewSet, NotificationViewSet, DashboardStatsView, ReportsView
)

router = DefaultRouter()
router.register(r'universities', UniversityViewSet, basename='university')
router.register(r'settings/templates', NotificationTemplateViewSet, basename='notification-template')
router.register(r'permits', PermitViewSet, basename='permit')
router.register(r'scholarships', ScholarshipViewSet, basename='scholarship')
router.register(r'notifications', NotificationViewSet, basename='notification')

universities_router = routers.NestedDefaultRouter(router, r'universities', lookup='university')
universities_router.register(r'programs', ProgramViewSet, basename='university-programs')

urlpatterns = [
    # Static & Non-model based endpoints
    path('document-types/', DocumentTypesView.as_view(), name='document-types'),
    path('organization-chart/', OrganizationChartView.as_view(), name='organization-chart'),
    path('dashboard-stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    
    # NEW: The dedicated endpoint for the reporting engine
    path('reports/summary/', ReportsView.as_view(), name='reports-summary'),
    
    # System List management endpoints
    path('settings/lists/', SystemListNameView.as_view(), name='system-list-names'),
    path('settings/lists/<str:name>/', SystemListDetailView.as_view(), name='system-list-detail'),
    
    # Include all router-generated URLs
    path('', include(router.urls)),
    path('', include(universities_router.urls)),
]
# start of student_affairs_project/urls.py
# student_affairs_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from apps.core.views import management_actions_view
# --- API URL Patterns ---
# Group all v1 API endpoints together for clarity and versioning.
api_v1_urlpatterns = [
    path('', include('apps.applications.urls')),
    path('', include('apps.users.urls')),
    path('choices/', include('apps.core.urls')),
    # --- FIX: Add the support app's URLs to the main API ---
    path('support/', include('apps.support.urls')),
]

# --- Main URL Patterns ---
urlpatterns = [
    # Django Admin Site
    path('admin/management-actions/', management_actions_view, name='management_actions'),
    
    path('admin/', admin.site.urls),

    # Authentication Endpoints (JWT)
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Application API v1
    path('api/v1/', include(api_v1_urlpatterns)),

    # django-impersonate URL (optional, useful for browser-based admin testing)
    path('impersonate/', include('impersonate.urls')),
]

# --- Media File Serving for Development ---
# In DEBUG mode, this allows Django's development server to serve user-uploaded media files.
# In production, this should be handled by your web server (e.g., Nginx).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# In a production-ready project, you would also add API documentation URLs here,
# for example, using drf-spectacular:
#
# from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
#
# urlpatterns += [
#     path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
#     path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
# ]
# end of student_affairs_project/urls.py
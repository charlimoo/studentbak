# apps/users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, Role

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """
    Admin view for the Role model.
    """
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Customized admin view for the custom User model.
    """
    list_display = ('email', 'full_name', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'roles', 'universities')
    search_fields = ('email', 'full_name')
    ordering = ('email',)

    # Define the layout of the user edit page in the admin
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('full_name',)}),
        (
            _('Affiliations & Roles'),
            {'fields': ('roles', 'universities')}
        ),
        (
            _('Permissions'),
            {
                'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            },
        ),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    # Use a more user-friendly widget for ManyToMany fields
    filter_horizontal = ('roles', 'universities', 'groups', 'user_permissions')

    # Since we use email as the username field, we don't need 'username' in the admin.
    # The BaseUserAdmin expects 'username', so we must set it to None.
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'password', 'password2'),
        }),
    )
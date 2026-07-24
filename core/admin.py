from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from core.models import Branch, SystemAlert, UserProfile

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'

class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'is_superuser']
    list_filter = ['is_active', 'is_staff', 'is_superuser', 'groups']

admin.site.unregister(User)
admin.site.register(User, UserAdmin)

@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'location', 'manager', 'status', 'capacity_percent']
    list_filter = ['status', 'region']
    search_fields = ['name', 'code', 'manager']

@admin.register(SystemAlert)
class SystemAlertAdmin(admin.ModelAdmin):
    list_display = ['title', 'severity', 'is_resolved', 'created_at']
    list_filter = ['severity', 'is_resolved']

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_global_admin']
    list_filter = ['is_global_admin', 'allowed_branches']
    search_fields = ['user__username', 'user__email']

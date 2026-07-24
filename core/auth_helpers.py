from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from core.models import UserProfile, Branch


def get_or_create_profile(user):
    try:
        return user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user)
        return profile


def can_access_branch(user, branch_code):
    if user.is_superuser:
        return True
    try:
        profile = get_or_create_profile(user)
        return profile.can_access_branch(branch_code)
    except Branch.DoesNotExist:
        return False


def branch_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from core.branch_context import get_current_branch_code
        branch_code = get_current_branch_code()
        if branch_code and not can_access_branch(request.user, branch_code):
            messages.error(request, 'You do not have access to this branch.')
            return redirect('reports_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def superuser_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, 'This action requires superuser privileges.')
            return redirect('reports_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def module_permission_required(module, action):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            perm_codename = f'core.{module}_{action}'
            if not request.user.has_perm(perm_codename):
                messages.error(request, 'You do not have permission to perform this action.')
                return redirect(request.META.get('HTTP_REFERER', '/'))
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def is_admin_or_inventory_manager(user):
    if user.is_superuser:
        return True
    return user.groups.filter(name='Inventory Manager').exists()


def admin_or_inventory_manager_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_admin_or_inventory_manager(request.user):
            messages.error(request, 'Only admin and inventory managers can receive transfers.')
            return redirect(request.META.get('HTTP_REFERER', '/'))
        return view_func(request, *args, **kwargs)
    return wrapper

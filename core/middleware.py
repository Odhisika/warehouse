from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from core.branch_context import set_current_branch_code
from core.auth_helpers import can_access_branch


PUBLIC_PATHS = {'/login/', '/logout/', '/admin/'}


class BranchMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_branch_code(None)

        if request.user.is_authenticated:
            branch_code = request.session.get('branch_code')
            if branch_code and not can_access_branch(request.user, branch_code):
                branch_code = None
                messages.warning(request, 'Branch access changed. Select your branch.')
            if not branch_code:
                branch_code = self._default_branch(request)
                request.session['branch_code'] = branch_code
            set_current_branch_code(branch_code)

        response = self.get_response(request)
        return response

    def _default_branch(self, request):
        from core.models import Branch, SiteSettings
        profile = getattr(request.user, 'profile', None)
        if profile and not profile.is_global_admin and not request.user.is_superuser:
            first = profile.allowed_branches.filter(status='active').first()
            if first:
                return first.code
        settings = SiteSettings.get_settings()
        if settings.default_branch:
            return settings.default_branch.code
        first = Branch.objects.filter(status='active').first()
        return first.code if first else None

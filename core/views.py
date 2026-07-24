from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages
from django.db.models import Sum, Count, Q, F, Avg
from django.views.decorators.http import require_POST
from core.models import SystemAlert, Branch, UserProfile
from core.branch_context import get_current_branch_code
from core.auth_helpers import superuser_required, get_or_create_profile


LOGIN_RATE_LIMITS = {}  # Simple in-memory rate limiter


def _check_login_rate(ip):
    import time
    now = time.time()
    # Clean old entries
    LOGIN_RATE_LIMITS[ip] = [t for t in LOGIN_RATE_LIMITS.get(ip, []) if now - t < 60]
    if len(LOGIN_RATE_LIMITS[ip]) >= 5:
        return False
    return True


def _record_login_attempt(ip):
    import time
    if ip not in LOGIN_RATE_LIMITS:
        LOGIN_RATE_LIMITS[ip] = []
    LOGIN_RATE_LIMITS[ip].append(time.time())


@login_required
def dashboard(request):
    from inventory.models import Product, StockAlert
    from dispatch.models import DispatchOrder

    total_inv_value = Product.objects.aggregate(
        total=Sum(F('stock_qty') * F('unit_cost'))
    )['total'] or 0

    total_sku_count = Product.objects.filter(is_active=True).count()

    pending_dispatches = DispatchOrder.objects.filter(
        status__in=['pending', 'processing']
    ).count()

    low_stock_alerts = StockAlert.objects.filter(is_resolved=False).count()
    priority_alerts = StockAlert.objects.filter(is_resolved=False, priority=True).count()

    damaged_items = Product.objects.filter(condition='damaged').count()

    critical_alerts = SystemAlert.objects.filter(is_resolved=False).order_by('-created_at')[:4]

    recent_dispatches = DispatchOrder.objects.order_by('-created_at')[:5]

    low_stock_items = StockAlert.objects.filter(
        is_resolved=False
    ).select_related('product').order_by('product__stock_qty')[:6]

    context = {
        'page_title': 'Dashboard',
        'total_inv_value': total_inv_value,
        'total_sku_count': total_sku_count,
        'pending_dispatches': pending_dispatches,
        'low_stock_alerts': low_stock_alerts,
        'priority_alerts': priority_alerts,
        'damaged_items': damaged_items,
        'critical_alerts': critical_alerts,
        'recent_dispatches': recent_dispatches,
        'low_stock_items': low_stock_items,
    }
    return render(request, 'core/dashboard.html', context)


def login_view(request):
    if request.user.is_authenticated:
        return redirect('/')
    if request.method == 'POST':
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        if not _check_login_rate(ip):
            messages.error(request, 'Too many login attempts. Try again in 60 seconds.')
            return render(request, 'core/login.html')

        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        _record_login_attempt(ip)
        if user:
            LOGIN_RATE_LIMITS.pop(ip, None)
            login(request, user)
            return redirect(request.GET.get('next', '/'))
        messages.error(request, 'Invalid username or password.')
    return render(request, 'core/login.html')


@require_POST
def logout_view(request):
    logout(request)
    return redirect('/login/')


@login_required
@require_POST
def switch_branch(request, code):
    from core.auth_helpers import can_access_branch
    from core.models import Branch
    branch = get_object_or_404(Branch, code=code, status='active')
    if not can_access_branch(request.user, code):
        messages.error(request, 'You do not have access to this branch.')
        return redirect(request.META.get('HTTP_REFERER', '/'))
    request.session['branch_code'] = code
    messages.success(request, f'Switched to {branch.name}')
    return redirect('/')


# ─── Notifications ───

@login_required
def read_notification(request, pk):
    from core.models import TransferNotification
    notif = get_object_or_404(TransferNotification, pk=pk, branch_code=get_current_branch_code())
    notif.is_read = True
    notif.save()
    return redirect(notif.link)


@login_required
@require_POST
def clear_notifications(request):
    from core.models import TransferNotification
    branch_code = get_current_branch_code()
    if branch_code:
        count = TransferNotification.objects.filter(branch_code=branch_code, is_read=False).update(is_read=True)
        if count:
            messages.success(request, f'{count} notification(s) cleared.')
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


# ─── Clear Alerts ───

@login_required
@require_POST
def clear_alerts(request):
    count = SystemAlert.objects.filter(is_resolved=False).update(is_resolved=True)
    messages.success(request, f'{count} alert(s) cleared.')
    return redirect('dashboard')


# ─── Settings Views ───

@login_required
@superuser_required
def settings_general(request):
    from core.models import Branch, SiteSettings
    from PIL import Image
    import io

    settings = SiteSettings.get_settings()

    if request.method == 'POST':
        settings.company_name = request.POST.get('company_name', 'Nexus Warehouse')
        settings.currency = request.POST.get('currency', 'USD – United States Dollar')
        settings.timezone = request.POST.get('timezone', '(GMT+00:00) UTC')
        settings.language = request.POST.get('language', 'English (United States)')
        settings.date_format = request.POST.get('date_format', 'MM/DD/YYYY')
        settings.theme = request.POST.get('theme', 'light')

        default_branch_pk = request.POST.get('default_branch')
        if default_branch_pk:
            settings.default_branch = Branch.objects.filter(pk=default_branch_pk).first()
        else:
            settings.default_branch = None

        if 'logo' in request.FILES:
            uploaded = request.FILES['logo']
            try:
                img = Image.open(uploaded)
                img.verify()
                uploaded.seek(0)
                settings.logo = uploaded
            except Exception:
                messages.error(request, 'Invalid image file. Please upload a valid PNG, JPG, or JPEG.')

        settings.save()
        messages.success(request, 'Settings saved.')
        return redirect('settings_general')

    return render(request, 'core/settings/general.html', {
        'page_title': 'Settings',
        'settings': settings,
        'branches': Branch.objects.all(),
    })


# ─── Role & Permission Definitions ───

PERMISSION_MODULES = [
    ('inventory', 'Inventory Management', 'Control warehouse stock levels and SKUs'),
    ('shipping', 'Shipping & Logistics', 'Manage outgoing shipments and carrier logs'),
    ('suppliers', 'Supplier Directory', 'Access and modify supplier contact information'),
    ('invoicing', 'Invoicing & Billing', 'Generate and approve financial documents'),
    ('system', 'System Configurations', 'Manage global node and branch settings'),
]

PERMISSION_ACTIONS = ['view', 'create', 'edit', 'delete', 'export']

ROLE_PERMISSIONS = {
    'Warehouse Admin': {
        'inventory': ['view', 'create', 'edit', 'delete', 'export'],
        'shipping': ['view', 'create', 'edit', 'delete', 'export'],
        'suppliers': ['view', 'create', 'edit', 'delete', 'export'],
        'invoicing': ['view', 'create', 'edit', 'delete', 'export'],
        'system': ['view', 'create', 'edit', 'delete', 'export'],
    },
    'Inventory Manager': {
        'inventory': ['view', 'create', 'edit', 'export'],
        'shipping': ['view'],
        'suppliers': ['view', 'create', 'edit'],
        'invoicing': ['view'],
        'system': [],
    },
    'Dispatcher': {
        'inventory': ['view'],
        'shipping': ['view', 'create', 'edit', 'export'],
        'suppliers': ['view'],
        'invoicing': ['view'],
        'system': [],
    },
    'Viewer': {
        'inventory': ['view'],
        'shipping': ['view'],
        'suppliers': ['view'],
        'invoicing': ['view'],
        'system': ['view'],
    },
}


def ensure_default_roles():
    ct = ContentType.objects.get_for_model(UserProfile)
    for mod_key, mod_label, _ in PERMISSION_MODULES:
        for action in PERMISSION_ACTIONS:
            codename = f'{mod_key}_{action}'
            Permission.objects.get_or_create(
                codename=codename,
                content_type=ct,
                defaults={'name': f'Can {action} {mod_label}'},
            )
    for role_name, module_actions in ROLE_PERMISSIONS.items():
        group, created = Group.objects.get_or_create(name=role_name)
        if created or group.permissions.count() == 0:
            perm_codenames = []
            for mod_key, actions in module_actions.items():
                for action in actions:
                    perm_codenames.append(f'{mod_key}_{action}')
            perms = Permission.objects.filter(content_type=ct, codename__in=perm_codenames)
            group.permissions.set(perms)


def get_perm_matrix(group):
    ct = ContentType.objects.get_for_model(UserProfile)
    matrix = {}
    for mod_key, mod_label, mod_desc in PERMISSION_MODULES:
        perms = {}
        for action in PERMISSION_ACTIONS:
            codename = f'{mod_key}_{action}'
            perm = Permission.objects.filter(codename=codename, content_type=ct).first()
            checked = bool(perm and group and group.permissions.filter(pk=perm.pk).exists())
            perms[action] = {
                'codename': codename,
                'checked': checked,
                'perm': perm,
            }
        matrix[mod_key] = {
            'label': mod_label,
            'desc': mod_desc,
            'perms': perms,
        }
    return matrix


@login_required
@superuser_required
def settings_roles(request):
    ensure_default_roles()
    groups = Group.objects.prefetch_related('user_set', 'permissions').all()
    selected_role = request.GET.get('role') or (groups.first().name if groups.exists() else '')
    current_group = groups.filter(name=selected_role).first()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_user':
            username = request.POST.get('username', '').strip()
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '')
            confirm_password = request.POST.get('confirm_password', '')
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            role_name = request.POST.get('role', '').strip()
            branch_ids = request.POST.getlist('branches')

            if not username:
                messages.error(request, 'Username is required.')
            elif not password or len(password) < 8:
                messages.error(request, 'Password must be at least 8 characters.')
            elif password != confirm_password:
                messages.error(request, 'Passwords do not match.')
            elif User.objects.filter(username=username).exists():
                messages.error(request, f'Username "{username}" is already taken.')
            else:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                )
                if role_name:
                    g = Group.objects.filter(name=role_name).first()
                    if g:
                        user.groups.add(g)
                        selected_role = g.name
                profile = get_or_create_profile(user)
                if branch_ids:
                    profile.allowed_branches.set(Branch.objects.filter(pk__in=branch_ids))
                messages.success(request, f'User "{username}" created successfully.')

        elif action == 'save_permissions':
            group_id = request.POST.get('group_id')
            g = Group.objects.filter(pk=group_id).first()
            if g:
                ct = ContentType.objects.get_for_model(UserProfile)
                perm_ids = []
                for key, val in request.POST.items():
                    if key.startswith('perm_') and val == 'on':
                        codename = key.replace('perm_', '', 1)
                        perm = Permission.objects.filter(codename=codename, content_type=ct).first()
                        if perm:
                            perm_ids.append(perm.pk)
                g.permissions.set(perm_ids)
                messages.success(request, f'Permissions for "{g.name}" updated.')
                selected_role = g.name

        elif action == 'remove_user':
            user_id = request.POST.get('user_id')
            group_id = request.POST.get('group_id')
            g = Group.objects.filter(pk=group_id).first()
            user = User.objects.filter(pk=user_id).first()
            if user and g:
                user.groups.remove(g)
                messages.success(request, f'{user.username} removed from {g.name}.')
                selected_role = g.name

        elif action == 'toggle_active':
            user_id = request.POST.get('user_id')
            user = User.objects.filter(pk=user_id).first()
            if user:
                user.is_active = not user.is_active
                user.save()
                status = 'activated' if user.is_active else 'deactivated'
                messages.success(request, f'{user.username} {status}.')

        elif action == 'transfer_branch':
            user_id = request.POST.get('user_id')
            branch_ids = request.POST.getlist('branch_ids')
            user = User.objects.filter(pk=user_id).first()
            if user:
                profile = get_or_create_profile(user)
                profile.allowed_branches.set(Branch.objects.filter(pk__in=branch_ids))
                messages.success(request, f'{user.username} branch access updated.')

        elif action == 'delete_user':
            user_id = request.POST.get('user_id')
            user = User.objects.filter(pk=user_id).first()
            if user and not user.is_superuser:
                username = user.username
                user.delete()
                messages.success(request, f'User "{username}" has been deleted.')
            else:
                messages.error(request, 'Cannot delete this user.')

        return redirect(f'{request.path}?role={selected_role}')

    role_users = current_group.user_set.all().order_by('username') if current_group else []
    perm_matrix = get_perm_matrix(current_group) if current_group else {}

    total_users = User.objects.filter(is_superuser=False).count()

    return render(request, 'core/settings/roles.html', {
        'page_title': 'Settings',
        'groups': groups,
        'selected_role': selected_role,
        'current_group': current_group,
        'perm_matrix': perm_matrix,
        'perm_modules': PERMISSION_MODULES,
        'perm_actions': PERMISSION_ACTIONS,
        'role_users': role_users,
        'branches': Branch.objects.filter(status='active'),
        'total_users': total_users,
    })


@login_required
@superuser_required
def settings_branches(request):
    from core.models import Branch

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_branch':
            code = request.POST.get('code', '').strip().upper()
            name = request.POST.get('name', '').strip()
            if code and name and not Branch.objects.filter(code=code).exists():
                branch = Branch.objects.create(
                    name=name,
                    code=code,
                    location=request.POST.get('location', ''),
                    manager=request.POST.get('manager', ''),
                    capacity_percent=int(request.POST.get('capacity_percent', 0)),
                    status=request.POST.get('status', 'active'),
                )
                messages.success(request, f'Branch "{branch.name}" created. Database migrated automatically.')
            elif Branch.objects.filter(code=code).exists():
                messages.error(request, f'Branch code "{code}" already exists.')
            else:
                messages.error(request, 'Name and Code are required.')

        elif action == 'save_all':
            updates = 0
            for key, value in request.POST.items():
                if key.startswith('name_'):
                    pk = key.replace('name_', '')
                    branch = Branch.objects.filter(pk=pk).first()
                    if branch:
                        branch.name = value
                        branch.location = request.POST.get(f'location_{pk}', '')
                        branch.manager = request.POST.get(f'manager_{pk}', '')
                        branch.capacity_percent = int(request.POST.get(f'capacity_{pk}', 0))
                        branch.status = request.POST.get(f'status_{pk}', 'active')
                        branch.save()
                        updates += 1
            messages.success(request, f'{updates} branch(es) updated.')

        return redirect('settings_branches')

    branches = Branch.objects.all()
    stats = {
        'total': branches.count(),
        'active': branches.filter(status='active').count(),
        'inactive': branches.filter(status='inactive').count(),
        'avg_capacity': int(branches.aggregate(
            avg=Avg('capacity_percent')
        )['avg'] or 0),
    }
    return render(request, 'core/settings/branches.html', {
        'page_title': 'Settings',
        'branches': branches,
        'stats': stats,
    })


@login_required
@superuser_required
def settings_security(request):
    if request.method == 'POST':
        current = request.POST.get('current_password', '')
        new_pw = request.POST.get('new_password', '')
        confirm = request.POST.get('confirm_password', '')

        if not request.user.check_password(current):
            messages.error(request, 'Current password is incorrect.')
        elif not new_pw or len(new_pw) < 8:
            messages.error(request, 'New password must be at least 8 characters.')
        elif new_pw != confirm:
            messages.error(request, 'New passwords do not match.')
        else:
            request.user.set_password(new_pw)
            request.user.save()
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            messages.success(request, 'Password changed successfully.')
        return redirect('settings_security')

    return render(request, 'core/settings/security.html', {
        'page_title': 'Settings',
    })


@login_required
def profile(request):
    user = request.user
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()

        if not email:
            messages.error(request, 'Email is required.')
        else:
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            user.save()
            messages.success(request, 'Profile updated successfully.')

        current = request.POST.get('current_password', '')
        new_pw = request.POST.get('new_password', '')
        confirm = request.POST.get('confirm_password', '')

        if current or new_pw or confirm:
            if not user.check_password(current):
                messages.error(request, 'Current password is incorrect.')
            elif not new_pw or len(new_pw) < 8:
                messages.error(request, 'New password must be at least 8 characters.')
            elif new_pw != confirm:
                messages.error(request, 'New passwords do not match.')
            else:
                user.set_password(new_pw)
                user.save()
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, user)
                messages.success(request, 'Password changed successfully.')

        return redirect('profile')

    return render(request, 'core/profile.html', {
        'page_title': 'My Profile',
    })

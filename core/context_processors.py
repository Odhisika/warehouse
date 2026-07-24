from core.models import SystemAlert, SiteSettings, Branch, TransferNotification
from core.branch_context import get_current_branch_code


def _user_has_module_perm(user, module):
    if user.is_superuser:
        return True
    return user.has_perm(f'core.{module}_view')


def _count(model, **filters):
    try:
        return model.objects.filter(**filters).count()
    except Exception:
        return 0


def sidebar_context(request):
    current_path = request.path
    user = request.user

    current_branch_code = get_current_branch_code()
    current_branch = Branch.objects.filter(code=current_branch_code).first() if current_branch_code else None

    all_nav_items = [
        {'label': 'Dashboard',  'url': '/',                 'icon': 'grid',       'perm': None},
        {'label': 'Inventory',  'url': '/inventory/',       'icon': 'package',    'perm': 'inventory'},
        {'label': 'Receiving',  'url': '/receiving/',       'icon': 'download',   'perm': 'shipping'},
        {'label': 'Dispatch',   'url': '/dispatch/',        'icon': 'truck',      'perm': 'shipping'},
        {'label': 'Returns',    'url': '/returns/',         'icon': 'corner-up-left', 'perm': 'inventory'},
        {'label': 'Transfers',  'url': '/transfers/',       'icon': 'repeat',     'perm': 'shipping'},
        {'label': 'Fleet',      'url': '/fleet/',           'icon': 'map',        'perm': 'shipping'},
        {'label': 'Invoicing',  'url': '/invoicing/',       'icon': 'file-text',  'perm': 'invoicing'},
        {'label': 'Reports',    'url': '/reports/',         'icon': 'bar-chart-2','perm': 'inventory'},
    ]

    nav_items = [
        item for item in all_nav_items
        if item['perm'] is None or _user_has_module_perm(user, item['perm'])
    ]

    # ─── Per‑section pending counts ───

    # Dashboard – unresolved alerts (central DB)
    dash_count = SystemAlert.objects.filter(is_resolved=False).count()

    # Inventory – low‑stock + out‑of‑stock products (branch DB)
    try:
        from inventory.models import Product
        inv_count = _count(Product, status__in=['low_stock', 'out_of_stock'])
    except Exception:
        inv_count = 0

    # Receiving – incoming transfers + incomplete supplier shipments
    try:
        from receiving.models import InboundShipment
        incomplete_shipments = _count(InboundShipment, is_complete=False)
    except Exception:
        incomplete_shipments = 0
    incoming_transfers = 0
    if current_branch_code:
        incoming_transfers = TransferNotification.objects.filter(
            branch_code=current_branch_code, is_read=False
        ).count()
    recv_count = incoming_transfers + incomplete_shipments

    # Dispatch – pending/processing orders (branch DB)
    try:
        from dispatch.models import DispatchOrder
        disp_count = _count(DispatchOrder, status__in=['pending', 'processing'])
    except Exception:
        disp_count = 0

    # Returns – incomplete returns (branch DB)
    try:
        from returns.models import ReturnRequest
        ret_count = _count(ReturnRequest, is_complete=False)
    except Exception:
        ret_count = 0

    # Transfers – non‑complete transfers (branch DB)
    try:
        from transfers.models import StockTransfer
        trf_count = _count(StockTransfer, status__in=['draft', 'pending', 'in_transit'])
    except Exception:
        trf_count = 0

    # Fleet – in-transit trips (branch DB)
    try:
        from fleet.models import TripSheet
        fleet_count = _count(TripSheet, status='in_transit')
    except Exception:
        fleet_count = 0

    # Invoicing – pending invoices (branch DB)
    try:
        from invoicing.models import SupplierInvoice
        invc_count = _count(SupplierInvoice, status='pending')
    except Exception:
        invc_count = 0

    label_counts = {
        'Dashboard': dash_count,
        'Inventory': inv_count,
        'Receiving': recv_count,
        'Dispatch': disp_count,
        'Returns': ret_count,
        'Transfers': trf_count,
        'Fleet': fleet_count,
        'Invoicing': invc_count,
        'Reports': 0,
    }

    for item in nav_items:
        item['active'] = current_path == item['url'] or (
            item['url'] != '/' and current_path.startswith(item['url'])
        )
        item['count'] = label_counts.get(item['label'], 0)

    settings_active = current_path.startswith('/settings/')
    site_settings = SiteSettings.get_settings()
    branches = Branch.objects.all()

    return {
        'nav_items': nav_items,
        'active_alerts': dash_count,
        'incoming_count': incoming_transfers,
        'settings_active': settings_active,
        'current_path': current_path,
        'site_settings': site_settings,
        'branches': branches,
        'current_branch': current_branch,
    }

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from inventory.models import Product, StockAlert
from core.auth_helpers import module_permission_required
from core.export_utils import export_excel, export_pdf


@login_required
@module_permission_required('inventory', 'view')
def reports_dashboard(request):
    total_stock_value = sum(
        (p.stock_qty * p.unit_cost) for p in Product.objects.filter(is_active=True)
    )
    out_of_stock = Product.objects.filter(is_active=True, stock_qty=0).count()
    low_stock_items = Product.objects.filter(is_active=True, stock_qty__gt=0, stock_qty__lte=10)
    damaged = Product.objects.filter(is_active=True, condition='damaged').count()
    ledger = Product.objects.select_related('category').filter(is_active=True)[:20]

    return render(request, 'reports/dashboard.html', {
        'page_title': 'Analytics & Report',
        'total_stock_value': total_stock_value,
        'out_of_stock': out_of_stock,
        'low_stock_items': low_stock_items,
        'damaged': damaged,
        'ledger': ledger,
    })


@login_required
@module_permission_required('inventory', 'export')
def reports_export(request):
    qs = Product.objects.select_related('category').filter(is_active=True)
    headers = ['SKU', 'Name', 'Category', 'Stock Qty', 'Reserved', 'Unit Cost', 'Total Value', 'Status']
    rows = []
    for p in qs:
        rows.append([
            p.sku, p.name, p.category.name if p.category else '',
            p.stock_qty, p.reserved_qty, str(p.unit_cost),
            str(p.total_value), p.status_display,
        ])

    fmt = request.GET.get('format', 'xlsx')
    if fmt == 'pdf':
        return export_pdf('Analytics Report', headers, rows, 'analytics.pdf', landscape=True)
    return export_excel(headers, rows, 'analytics.xlsx')

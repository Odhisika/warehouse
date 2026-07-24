import datetime, random
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.text import slugify
from inventory.models import Product, Category, StockAlert
from core.auth_helpers import module_permission_required
from core.export_utils import export_excel, export_pdf


@login_required
@module_permission_required('inventory', 'view')
def inventory_list(request):
    qs = Product.objects.select_related('category').filter(is_active=True)

    search = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    stock_level = request.GET.get('stock_level', '')

    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(sku__icontains=search))
    if category_id:
        qs = qs.filter(category_id=category_id)
    if stock_level == 'in_stock':
        qs = qs.filter(stock_qty__gt=10)
    elif stock_level == 'low_stock':
        qs = qs.filter(stock_qty__gt=0, stock_qty__lte=10)
    elif stock_level == 'out_of_stock':
        qs = qs.filter(stock_qty=0)

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'inventory/list.html', {
        'page_title': 'Inventory Management',
        'products': page,
        'categories': Category.objects.all(),
        'search': search,
        'selected_category': category_id,
        'selected_stock_level': stock_level,
    })


@login_required
@module_permission_required('inventory', 'create')
def product_add(request):
    if request.method == 'POST':
        name = request.POST['name']

        category_id = request.POST.get('category')
        if category_id == '__new__':
            new_name = request.POST.get('new_category_name', '').strip()
            if new_name:
                category = Category.objects.create(
                    name=new_name,
                    slug=slugify(new_name) or f'cat-{int(datetime.datetime.now().timestamp())}',
                )
                category_id = category.pk

        sku = request.POST.get('sku', '').strip()
        if not sku:
            date_part = datetime.date.today().strftime('%y%m%d')
            rand_part = f'{random.randint(0, 9999):04d}'
            sku = f'SKU-{date_part}-{rand_part}'

        Product.objects.create(
            name=name,
            sku=sku,
            stock_qty=request.POST.get('stock_qty', 0),
            unit_cost=request.POST.get('unit_cost', 0),
            batch_number=request.POST.get('batch_number', ''),
            category_id=category_id or None,
        )
        messages.success(request, 'Product added successfully.')
        return redirect('inventory_list')
    return render(request, 'inventory/product_form.html', {
        'page_title': 'Add New Product',
        'categories': Category.objects.all(),
    })


@login_required
@module_permission_required('inventory', 'edit')
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        category_id = request.POST.get('category')
        if category_id == '__new__':
            new_name = request.POST.get('new_category_name', '').strip()
            if new_name:
                category = Category.objects.create(
                    name=new_name,
                    slug=slugify(new_name) or f'cat-{int(datetime.datetime.now().timestamp())}',
                )
                category_id = category.pk

        product.name = request.POST['name']
        product.sku = request.POST['sku']
        product.stock_qty = request.POST.get('stock_qty', 0)
        product.unit_cost = request.POST.get('unit_cost', 0)
        product.batch_number = request.POST.get('batch_number', '')
        product.category_id = category_id or None
        product.save()
        messages.success(request, 'Product updated.')
        return redirect('inventory_list')
    return render(request, 'inventory/product_form.html', {
        'page_title': 'Edit Product',
        'product': product,
        'categories': Category.objects.all(),
    })


@login_required
@module_permission_required('inventory', 'delete')
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.is_active = False
        product.save()
        messages.success(request, 'Product removed.')
    return redirect('inventory_list')


@login_required
@module_permission_required('inventory', 'view')
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    alerts = product.alerts.order_by('-created_at')
    recent_dispatches = []
    recent_inbound = []
    recent_returns = []
    try:
        from dispatch.models import DispatchItem
        recent_dispatches = DispatchItem.objects.filter(
            product=product
        ).select_related('order', 'order__customer').order_by('-order__created_at')[:10]
    except Exception:
        pass
    try:
        from receiving.models import InboundItem
        recent_inbound = InboundItem.objects.filter(
            product=product
        ).select_related('shipment', 'shipment__supplier').order_by('-shipment__created_at')[:10]
    except Exception:
        pass
    try:
        from returns.models import ReturnItem
        recent_returns = ReturnItem.objects.filter(
            product=product
        ).select_related('return_request', 'return_request__original_order').order_by('-return_request__created_at')[:10]
    except Exception:
        pass
    return render(request, 'inventory/product_detail.html', {
        'page_title': product.name,
        'product': product,
        'alerts': alerts,
        'recent_dispatches': recent_dispatches,
        'recent_inbound': recent_inbound,
        'recent_returns': recent_returns,
    })


@login_required
@module_permission_required('inventory', 'export')
def inventory_export(request):
    qs = Product.objects.select_related('category').filter(is_active=True)
    headers = ['SKU', 'Name', 'Category', 'Batch', 'Expiry', 'Stock Qty', 'Unit Cost', 'Status']
    rows = []
    for p in qs:
        rows.append([
            p.sku, p.name, p.category.name if p.category else '',
            p.batch_number, p.expiry_date or '', p.stock_qty,
            str(p.unit_cost), p.status_display,
        ])

    fmt = request.GET.get('format', 'xlsx')
    if fmt == 'pdf':
        return export_pdf('Inventory Report', headers, rows, 'inventory.pdf', landscape=True)
    return export_excel(headers, rows, 'inventory.xlsx')

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction, models
from django.views.decorators.http import require_POST
from dispatch.models import DispatchOrder, DispatchItem, Customer
from inventory.models import Product
from core.export_utils import export_excel, export_pdf
from core.auth_helpers import branch_required, module_permission_required


@login_required
@branch_required
@module_permission_required('shipping', 'view')
def dispatch_list(request):
    orders = DispatchOrder.objects.select_related('customer').order_by('-created_at')
    return render(request, 'dispatch/list.html', {
        'page_title': 'Dispatch',
        'orders': orders,
    })


@login_required
@branch_required
@module_permission_required('shipping', 'create')
def dispatch_new(request):
    if request.method == 'POST':
        order = DispatchOrder.objects.create(
            customer_id=request.POST.get('customer') or None,
            destination=request.POST.get('destination', ''),
            carrier=request.POST.get('carrier', ''),
            handling_fee=request.POST.get('handling_fee', 0),
            tax_rate=request.POST.get('tax_rate', 15),
        )
        items_added = 0
        for key, val in request.POST.items():
            if key.startswith('manifest_qty_'):
                try:
                    product_id = int(key.replace('manifest_qty_', ''))
                    qty = int(val)
                except (ValueError, TypeError):
                    continue
                if qty <= 0:
                    continue
                try:
                    product = Product.objects.get(pk=product_id)
                    unit_price = float(product.unit_cost)
                except (Product.DoesNotExist, ValueError, TypeError):
                    unit_price = 0
                DispatchItem.objects.create(
                    order=order,
                    product_id=product_id,
                    quantity=qty,
                    unit_price=unit_price,
                )
                items_added += 1
        if items_added:
            messages.success(request, f'Dispatch {order.dispatch_id} created with {items_added} item(s).')
        else:
            messages.warning(request, f'Dispatch {order.dispatch_id} created with no items.')
        return redirect('dispatch_detail', pk=order.pk)
    return render(request, 'dispatch/new.html', {
        'page_title': 'New Dispatch',
        'customers': Customer.objects.all(),
        'products': Product.objects.filter(is_active=True, stock_qty__gt=0),
    })


@login_required
@branch_required
@module_permission_required('shipping', 'view')
def dispatch_detail(request, pk):
    order = get_object_or_404(DispatchOrder, pk=pk)
    return render(request, 'dispatch/detail.html', {
        'page_title': 'Dispatch',
        'order': order,
    })


@login_required
@branch_required
@module_permission_required('shipping', 'edit')
@require_POST
@transaction.atomic
def dispatch_authorize(request, pk):
    order = get_object_or_404(DispatchOrder.objects.select_for_update(), pk=pk)
    if order.status != 'pending':
        messages.error(request, f'Only pending dispatches can be authorized.')
        return redirect('dispatch_detail', pk=pk)
    for item in order.items.all():
        if not item.product:
            continue
        product = Product.objects.select_for_update().get(pk=item.product_id)
        if product.stock_qty < item.quantity:
            messages.error(request, f'Insufficient stock for {product.sku}: need {item.quantity}, have {product.stock_qty}')
            return redirect('dispatch_detail', pk=pk)
        product.stock_qty -= item.quantity
        product.save()
    order.subtotal = order.items.aggregate(
        total=models.Sum(models.F('quantity') * models.F('unit_price'))
    )['total'] or 0
    order.status = 'processing'
    order.save()
    messages.success(request, f'{order.dispatch_id} authorized. Stock deducted.')
    return redirect('dispatch_detail', pk=pk)


@login_required
@branch_required
@module_permission_required('shipping', 'edit')
def dispatch_ship(request, pk):
    order = get_object_or_404(DispatchOrder, pk=pk)
    if order.status != 'processing':
        messages.error(request, 'Only processing dispatches can be shipped.')
        return redirect('dispatch_detail', pk=pk)
    if request.method == 'POST':
        vehicle_id = request.POST.get('vehicle')
        driver_id = request.POST.get('driver')
        if not vehicle_id or not driver_id:
            messages.error(request, 'Vehicle and driver are required to ship.')
            return redirect('dispatch_ship', pk=pk)
        from fleet.models import Vehicle, Driver
        vehicle = Vehicle.objects.filter(pk=vehicle_id, status='active').first()
        driver = Driver.objects.filter(pk=driver_id, is_active=True).first()
        if not vehicle:
            messages.error(request, 'Selected vehicle is not available.')
            return redirect('dispatch_ship', pk=pk)
        if not driver:
            messages.error(request, 'Selected driver is not available.')
            return redirect('dispatch_ship', pk=pk)
        total_weight = sum(
            (item.quantity * float(item.product.unit_cost) if item.product else 0)
            for item in order.items.all()
        )
        order.assigned_vehicle = vehicle
        order.assigned_driver = driver
        order.status = 'shipped'
        order.save()
        messages.success(request, f'{order.dispatch_id} shipped via {vehicle.plate_number} driven by {driver.full_name}.')
        return redirect('dispatch_detail', pk=pk)
    from fleet.models import Vehicle, Driver, DriverVehicleAssignment
    vehicles = Vehicle.objects.filter(status='active')
    annotated = []
    for v in vehicles:
        assignment = DriverVehicleAssignment.objects.filter(
            vehicle=v, end_date__isnull=True
        ).select_related('driver').first()
        annotated.append({
            'pk': v.pk,
            'plate_number': v.plate_number,
            'vehicle_type': v.vehicle_type,
            'get_vehicle_type_display': v.get_vehicle_type_display(),
            'capacity_weight_kg': v.capacity_weight_kg,
            'current_driver_id': assignment.driver.pk if assignment else '',
            'current_driver_name': str(assignment.driver) if assignment else '',
        })
    return render(request, 'dispatch/ship_form.html', {
        'page_title': f'Ship — {order.dispatch_id}',
        'order': order,
        'vehicles': annotated,
        'drivers': Driver.objects.filter(is_active=True),
    })


@login_required
@branch_required
@module_permission_required('shipping', 'edit')
@require_POST
def dispatch_deliver(request, pk):
    order = get_object_or_404(DispatchOrder, pk=pk)
    if order.status != 'shipped':
        messages.error(request, 'Only shipped dispatches can be marked as delivered.')
        return redirect('dispatch_detail', pk=pk)
    if hasattr(order, 'pod'):
        messages.info(request, f'POD already recorded for {order.dispatch_id}.')
        return redirect('pod_detail', pk=pk)
    return redirect('pod_capture', pk=pk)


@login_required
@branch_required
@module_permission_required('shipping', 'edit')
@require_POST
@transaction.atomic
def dispatch_cancel(request, pk):
    order = get_object_or_404(DispatchOrder.objects.select_for_update(), pk=pk)
    if order.status in ('delivered', 'cancelled'):
        messages.error(request, f'Cannot cancel a {order.get_status_display().lower()} dispatch.')
        return redirect('dispatch_detail', pk=pk)
    if order.status == 'processing':
        for item in order.items.all():
            if not item.product:
                continue
            product = Product.objects.select_for_update().get(pk=item.product_id)
            product.stock_qty += item.quantity
            product.save()
    order.status = 'cancelled'
    order.save()
    messages.success(request, f'{order.dispatch_id} cancelled. Stock restored.')
    return redirect('dispatch_detail', pk=pk)


@login_required
@branch_required
@module_permission_required('shipping', 'export')
def dispatch_export(request):
    qs = DispatchOrder.objects.select_related('customer').order_by('-created_at')
    headers = ['Dispatch ID', 'Customer', 'Destination', 'Carrier', 'Subtotal', 'Handling', 'Tax', 'Grand Total', 'Status', 'Date']
    rows = []
    for o in qs:
        rows.append([
            o.dispatch_id, o.customer.name if o.customer else '',
            o.destination, o.get_carrier_display(), str(o.subtotal),
            str(o.handling_fee), str(o.tax_amount), str(o.grand_total),
            o.get_status_display(), o.created_at.strftime('%Y-%m-%d'),
        ])

    fmt = request.GET.get('format', 'xlsx')
    if fmt == 'pdf':
        return export_pdf('Dispatch Report', headers, rows, 'dispatch.pdf', landscape=True)
    return export_excel(headers, rows, 'dispatch.xlsx')


@login_required
@branch_required
@module_permission_required('shipping', 'view')
def customer_list(request):
    customers = Customer.objects.order_by('name')
    return render(request, 'dispatch/customer_list.html', {
        'page_title': 'Customers',
        'customers': customers,
    })


@login_required
@branch_required
@module_permission_required('shipping', 'create')
def customer_new(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Customer name is required.')
            return redirect('customer_new')
        customer = Customer.objects.create(
            name=name,
            customer_id=request.POST.get('customer_id', '').strip(),
            zone=request.POST.get('zone', ''),
            shipping_method=request.POST.get('shipping_method', ''),
            credit_status=request.POST.get('credit_status', 'ok'),
            email=request.POST.get('email', ''),
            phone=request.POST.get('phone', ''),
        )
        messages.success(request, f'Customer "{customer.name}" created.')
        return redirect('customer_detail', pk=customer.pk)
    return render(request, 'dispatch/customer_form.html', {
        'page_title': 'New Customer',
        'customer': None,
    })


@login_required
@branch_required
@module_permission_required('shipping', 'view')
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    orders = DispatchOrder.objects.filter(customer=customer).order_by('-created_at')
    return render(request, 'dispatch/customer_detail.html', {
        'page_title': customer.name,
        'customer': customer,
        'orders': orders,
    })


@login_required
@branch_required
@module_permission_required('shipping', 'edit')
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Customer name is required.')
            return redirect('customer_edit', pk=pk)
        customer.name = name
        customer.customer_id = request.POST.get('customer_id', customer.customer_id)
        customer.zone = request.POST.get('zone', '')
        customer.shipping_method = request.POST.get('shipping_method', '')
        customer.credit_status = request.POST.get('credit_status', 'ok')
        customer.email = request.POST.get('email', '')
        customer.phone = request.POST.get('phone', '')
        customer.save()
        messages.success(request, f'Customer "{customer.name}" updated.')
        return redirect('customer_detail', pk=customer.pk)
    return render(request, 'dispatch/customer_form.html', {
        'page_title': f'Edit {customer.name}',
        'customer': customer,
    })


@login_required
@branch_required
@module_permission_required('shipping', 'edit')
@require_POST
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    name = customer.name
    customer.delete()
    messages.success(request, f'Customer "{name}" deleted.')
    return redirect('customer_list')

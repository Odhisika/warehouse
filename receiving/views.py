from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.views.decorators.http import require_POST
from receiving.models import InboundShipment, InboundItem
from inventory.models import Product, Supplier
from core.export_utils import export_excel, export_pdf
from core.auth_helpers import branch_required, module_permission_required
from core.branch_context import get_current_branch_code, set_current_branch_code
from core.db_router import register_branch_db


@login_required
@branch_required
@module_permission_required('shipping', 'view')
def receiving_list(request):
    from core.branch_context import get_current_branch_code
    from core.models import TransferNotification

    shipments = InboundShipment.objects.select_related('supplier').order_by('-created_at')

    branch_code = get_current_branch_code()
    incoming_transfers = TransferNotification.objects.none()
    if branch_code:
        incoming_transfers = TransferNotification.objects.filter(
            branch_code=branch_code, is_read=False
        ).order_by('-created_at')

    return render(request, 'receiving/list.html', {
        'page_title': 'Receiving',
        'shipments': shipments,
        'incoming_transfers': incoming_transfers,
    })


@login_required
@branch_required
@module_permission_required('shipping', 'create')
def receiving_new(request):
    if request.method == 'POST':
        shipment = InboundShipment.objects.create(
            supplier_id=request.POST.get('supplier') or None,
            invoice_ref=request.POST.get('invoice_ref', ''),
            po_reference=request.POST.get('po_reference', ''),
            receive_date=request.POST.get('receive_date') or timezone.now().date(),
        )
        items_added = 0
        for key, val in request.POST.items():
            if key.startswith('qty_'):
                try:
                    row_id = int(key.replace('qty_', ''))
                    qty = int(val)
                except (ValueError, TypeError):
                    continue
                if qty <= 0:
                    continue
                product_pk = request.POST.get(f'product_{row_id}')
                if not product_pk:
                    continue
                try:
                    product_pk = int(product_pk)
                except (ValueError, TypeError):
                    continue
                unit_cost = request.POST.get(f'cost_{row_id}', 0)
                try:
                    unit_cost = float(unit_cost)
                except (ValueError, TypeError):
                    unit_cost = 0
                InboundItem.objects.create(
                    shipment=shipment,
                    product_id=product_pk,
                    quantity=qty,
                    unit_cost=unit_cost,
                    condition=request.POST.get(f'condition_{row_id}', 'pristine'),
                )
                items_added += 1
        if items_added:
            messages.success(request, f'Inbound shipment created with {items_added} item(s).')
        else:
            messages.warning(request, 'Inbound shipment created with no items.')
        return redirect('receiving_detail', pk=shipment.pk)
    return render(request, 'receiving/new.html', {
        'page_title': 'Receiving Module',
        'suppliers': Supplier.objects.filter(is_active=True),
        'products': Product.objects.filter(is_active=True),
        'today': timezone.now().date(),
    })


@login_required
@branch_required
@module_permission_required('shipping', 'view')
def receiving_detail(request, pk):
    shipment = get_object_or_404(InboundShipment, pk=pk)
    return render(request, 'receiving/detail.html', {
        'page_title': 'Receiving Module',
        'shipment': shipment,
        'products': Product.objects.filter(is_active=True),
    })


@login_required
@branch_required
@module_permission_required('shipping', 'edit')
@require_POST
@transaction.atomic
def receiving_complete(request, pk):
    shipment = get_object_or_404(InboundShipment.objects.select_for_update(), pk=pk)
    if shipment.is_complete:
        messages.error(request, 'This shipment is already completed.')
        return redirect('receiving_detail', pk=pk)
    for item in shipment.items.all():
        if not item.product:
            continue
        product, created = Product.objects.select_for_update().get_or_create(
            pk=item.product_id,
            defaults={
                'name': f'Product #{item.product_id}',
                'sku': f'IMP-{item.product_id}',
                'stock_qty': 0,
            }
        )
        product.stock_qty += item.quantity
        product.save()
    shipment.is_complete = True
    shipment.save()
    messages.success(request, f'Shipment completed. Stock added to inventory.')
    return redirect('receiving_detail', pk=pk)


@login_required
@branch_required
@module_permission_required('shipping', 'export')
def receiving_export(request):
    qs = InboundShipment.objects.select_related('supplier').order_by('-created_at')
    headers = ['Invoice Ref', 'PO Reference', 'Supplier', 'Date', 'Units', 'Value', 'Status']
    rows = []
    for s in qs:
        rows.append([
            s.invoice_ref or str(s.pk), s.po_reference or '',
            s.supplier.name if s.supplier else '',
            s.receive_date.strftime('%Y-%m-%d') if s.receive_date else '',
            s.total_units, str(s.total_value),
            'Complete' if s.is_complete else 'In Progress',
        ])

    fmt = request.GET.get('format', 'xlsx')
    if fmt == 'pdf':
        return export_pdf('Receiving Report', headers, rows, 'receiving.pdf', landscape=True)
    return export_excel(headers, rows, 'receiving.xlsx')


# ─── Receive incoming transfers (cross‑branch) ───

@login_required
@branch_required
@module_permission_required('shipping', 'edit')
def receiving_incoming(request, notif_pk):
    from core.models import TransferNotification
    from transfers.models import StockTransfer
    from transfers.services import execute_transfer

    current_branch = get_current_branch_code()
    notif = get_object_or_404(TransferNotification, pk=notif_pk, branch_code=current_branch)

    # Old-format notifications (pre-migration) — redirect to their stored link
    if not notif.from_branch_code or not notif.transfer_pk:
        if notif.link:
            return redirect(notif.link)
        messages.error(request, 'This notification is from an older version.')
        return redirect('receiving_list')

    # Temporarily switch to source branch context to find the StockTransfer
    register_branch_db(notif.from_branch_code)
    set_current_branch_code(notif.from_branch_code)
    t = get_object_or_404(StockTransfer, pk=notif.transfer_pk)

    if t.to_branch_code != current_branch:
        set_current_branch_code(current_branch)
        messages.error(request, 'This transfer is not destined for your branch.')
        return redirect('receiving_list')

    if request.method == 'POST':
        notif.is_read = True
        notif.save()

        from invoicing.models import TransferWaybill
        try:
            waybill = t.waybill
        except TransferWaybill.DoesNotExist:
            waybill = None

        if waybill:
            for wb_item in waybill.items.all():
                qty_received = request.POST.get(f'qty_received_{wb_item.pk}', '')
                qty_damaged = request.POST.get(f'qty_damaged_{wb_item.pk}', '0')
                condition_notes = request.POST.get(f'condition_notes_{wb_item.pk}', '')

                try:
                    qty_received = int(qty_received) if qty_received else 0
                    qty_damaged = int(qty_damaged) if qty_damaged else 0
                except (ValueError, TypeError):
                    qty_received = 0
                    qty_damaged = 0

                if qty_received < 0:
                    qty_received = 0
                if qty_damaged < 0:
                    qty_damaged = 0

                wb_item.qty_received = qty_received
                wb_item.qty_damaged = qty_damaged
                wb_item.condition_notes = condition_notes
                wb_item.save()

        execute_transfer(t, waybill=waybill)
        t.status = 'received'
        t.completed_at = timezone.now()
        t.save()

        if waybill:
            has_discrepancy = waybill.has_discrepancy
            waybill.received_at = timezone.now()
            waybill.received_by = request.user
            waybill.status = 'partial' if has_discrepancy else 'received'
            waybill.save()

        set_current_branch_code(current_branch)
        if waybill and has_discrepancy:
            messages.warning(request, f'Transfer {t.reference} received with discrepancies.')
        else:
            messages.success(request, f'Transfer {t.reference} received successfully.')
        return redirect('receiving_list')

    items = list(t.items.select_related('product').all())
    from invoicing.models import TransferWaybill
    try:
        waybill = t.waybill
    except TransferWaybill.DoesNotExist:
        waybill = None
    waybill_items = list(waybill.items.select_related('product').all()) if waybill else []
    set_current_branch_code(current_branch)
    return render(request, 'receiving/incoming.html', {
        'page_title': f'Receive {t.reference}',
        'transfer': t,
        'items': items,
        'waybill': waybill,
        'waybill_items': waybill_items,
        'notification': notif,
    })

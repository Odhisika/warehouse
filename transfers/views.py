from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.views.decorators.http import require_POST
from transfers.models import StockTransfer, TransferItem
from inventory.models import Product
from core.models import Branch
from fleet.models import Vehicle, Driver
from core.branch_context import get_current_branch_code
from core.auth_helpers import can_access_branch, module_permission_required, is_admin_or_inventory_manager
from transfers.services import execute_transfer
from core.export_utils import export_excel, export_pdf
from invoicing.models import TransferWaybill, TransferWaybillItem


@login_required
@module_permission_required('shipping', 'view')
def transfers_list(request):
    transfers = StockTransfer.objects.order_by('-created_at')
    return render(request, 'transfers/list.html', {
        'page_title': 'Stock Transfer',
        'transfers': transfers,
    })


@login_required
@module_permission_required('shipping', 'create')
def transfers_new(request):
    from django.utils import timezone
    from transfers.services import execute_transfer
    from core.models import TransferNotification

    current_branch = get_current_branch_code()
    if request.method == 'POST':
        to_branch_code = request.POST.get('to_branch_code', '')
        from_branch_code = request.POST.get('from_branch_code') or current_branch
        if not can_access_branch(request.user, from_branch_code):
            messages.error(request, 'You cannot create transfers from a branch you do not have access to.')
            return redirect('transfers_list')
        if not can_access_branch(request.user, to_branch_code):
            messages.error(request, 'You cannot create transfers to a branch you do not have access to.')
            return redirect('transfers_list')
        if from_branch_code == to_branch_code:
            messages.error(request, 'Cannot transfer stock to the same branch. Please select a different destination.')
            return redirect('transfers_new')

        t = StockTransfer.objects.create(
            from_branch_code=from_branch_code,
            to_branch_code=to_branch_code,
            assigned_vehicle_id=request.POST.get('assigned_vehicle') or None,
            assigned_driver_id=request.POST.get('assigned_driver') or None,
            notes=request.POST.get('notes', ''),
        )

        items_added = 0
        for key, val in request.POST.items():
            if key.startswith('transfer_qty_'):
                try:
                    product_id = int(key.replace('transfer_qty_', ''))
                    qty = int(val)
                except (ValueError, TypeError):
                    continue
                if qty <= 0:
                    continue
                TransferItem.objects.create(
                    transfer=t,
                    product_id=product_id,
                    quantity=qty,
                )
                items_added += 1

        if not items_added:
            t.delete()
            messages.error(request, 'Add at least one item to the transfer.')
            return redirect('transfers_new')

        t.status = 'in_transit'
        t.save()

        waybill = TransferWaybill.objects.create(
            transfer=t,
            status='dispatched',
            created_by=request.user,
        )
        for item in t.items.all():
            TransferWaybillItem.objects.create(
                waybill=waybill,
                product=item.product,
                qty_sent=item.quantity,
            )

        notif = TransferNotification.objects.create(
            branch_code=to_branch_code,
            from_branch_code=from_branch_code,
            transfer_pk=t.pk,
            title=f'Transfer {t.reference} Dispatched',
            message=f'{items_added} item(s) dispatched from {from_branch_code} to {to_branch_code}.',
            link='',
        )
        notif.link = f'/receiving/incoming/{notif.pk}/'
        notif.save()

        messages.success(request, f'Transfer {t.reference} dispatched. Awaiting confirmation from {to_branch_code}.')
        return redirect('transfers_list')

    return render(request, 'transfers/new.html', {
        'page_title': 'Stock Transfer',
        'branches': Branch.objects.all(),
        'products': Product.objects.filter(is_active=True, stock_qty__gt=0),
        'vehicles': Vehicle.objects.filter(status='active'),
        'drivers': Driver.objects.filter(is_active=True),
    })


@login_required
@module_permission_required('shipping', 'view')
def transfers_detail(request, pk):
    t = get_object_or_404(StockTransfer, pk=pk)
    branch_names = {b.code: b.name for b in Branch.objects.all()}
    return render(request, 'transfers/detail.html', {
        'page_title': f'Transfer {t.reference}',
        'transfer': t,
        'branch_names': branch_names,
        'vehicles': Vehicle.objects.filter(status='active'),
        'drivers': Driver.objects.filter(is_active=True),
        'can_receive': is_admin_or_inventory_manager(request.user),
    })


@login_required
@module_permission_required('shipping', 'edit')
@require_POST
def transfers_send(request, pk):
    current_branch = get_current_branch_code()
    t = get_object_or_404(StockTransfer, pk=pk)
    if t.from_branch_code != current_branch:
        messages.error(request, 'You can only send transfers from your current branch.')
        return redirect('transfers_detail', pk=pk)
    if t.status != 'draft':
        messages.error(request, 'Only draft transfers can be sent.')
        return redirect('transfers_detail', pk=pk)
    if not t.items.exists():
        messages.error(request, 'Cannot send a transfer with no items.')
        return redirect('transfers_detail', pk=pk)
    t.status = 'pending'
    t.save()
    messages.success(request, f'Transfer {t.reference} marked as pending.')
    return redirect('transfers_detail', pk=pk)


@login_required
@module_permission_required('shipping', 'edit')
@require_POST
def transfers_dispatch(request, pk):
    from core.models import TransferNotification
    current_branch = get_current_branch_code()
    t = get_object_or_404(StockTransfer, pk=pk)
    if t.from_branch_code != current_branch:
        messages.error(request, 'You can only dispatch transfers from the source branch.')
        return redirect('transfers_detail', pk=pk)
    if t.status != 'pending':
        messages.error(request, 'Only pending transfers can be dispatched.')
        return redirect('transfers_detail', pk=pk)

    with transaction.atomic():
        vehicle_id = request.POST.get('assigned_vehicle')
        driver_id = request.POST.get('assigned_driver')
        if vehicle_id:
            t.assigned_vehicle_id = int(vehicle_id)
        if driver_id:
            t.assigned_driver_id = int(driver_id)
        t.status = 'in_transit'
        t.save()

        try:
            waybill = t.waybill
        except TransferWaybill.DoesNotExist:
            waybill = TransferWaybill.objects.create(transfer=t, created_by=request.user)
            for item in t.items.all():
                TransferWaybillItem.objects.create(
                    waybill=waybill,
                    product=item.product,
                    qty_sent=item.quantity,
                )

        notif = TransferNotification.objects.create(
            branch_code=t.to_branch_code,
            from_branch_code=t.from_branch_code,
            transfer_pk=t.pk,
            title=f'Transfer {t.reference} Dispatched',
            message=f'{t.items.count()} item(s) dispatched from {t.from_branch_code} to {t.to_branch_code}.',
            link='',
        )
        notif.link = f'/receiving/incoming/{notif.pk}/'
        notif.save()

    messages.success(request, f'Transfer {t.reference} is now in transit. Waybill {waybill.waybill_number} generated.')
    return redirect('transfers_detail', pk=pk)


@login_required
@module_permission_required('shipping', 'edit')
@require_POST
def transfers_receive(request, pk):
    if not is_admin_or_inventory_manager(request.user):
        messages.error(request, 'Only admin and inventory managers can receive transfers.')
        return redirect('transfers_detail', pk=pk)
    current_branch = get_current_branch_code()
    t = get_object_or_404(StockTransfer, pk=pk)
    if t.to_branch_code != current_branch:
        messages.error(request, 'You can only receive transfers at the destination branch.')
        return redirect('transfers_detail', pk=pk)
    if t.status != 'in_transit':
        messages.error(request, 'Only in-transit transfers can be received.')
        return redirect('transfers_detail', pk=pk)

    # If waybill exists, redirect to verification form
    try:
        waybill = t.waybill
        return redirect('transfers_verify_receive', pk=pk)
    except TransferWaybill.DoesNotExist:
        pass

    # Legacy path: no waybill, receive directly
    execute_transfer(t)
    t.status = 'received'
    t.completed_at = timezone.now()
    t.save()

    from core.models import TransferNotification
    TransferNotification.objects.filter(
        branch_code=t.to_branch_code, transfer_pk=t.pk, is_read=False
    ).update(is_read=True)

    messages.success(request, f'Transfer {t.reference} received.')
    return redirect('transfers_detail', pk=pk)


@login_required
@module_permission_required('shipping', 'edit')
def transfers_verify_receive(request, pk):
    if not is_admin_or_inventory_manager(request.user):
        messages.error(request, 'Only admin and inventory managers can receive transfers.')
        return redirect('transfers_detail', pk=pk)
    t = get_object_or_404(StockTransfer, pk=pk)
    current_branch = get_current_branch_code()
    if t.to_branch_code != current_branch:
        messages.error(request, 'You can only receive transfers at the destination branch.')
        return redirect('transfers_detail', pk=pk)
    if t.status != 'in_transit':
        messages.error(request, 'Only in-transit transfers can be received.')
        return redirect('transfers_detail', pk=pk)

    try:
        waybill = t.waybill
    except TransferWaybill.DoesNotExist:
        messages.error(request, 'No waybill found for this transfer. Please dispatch first.')
        return redirect('transfers_detail', pk=pk)

    if request.method == 'POST':
        with transaction.atomic():
            has_discrepancy = False
            for item in waybill.items.all():
                qty_received = request.POST.get(f'qty_received_{item.pk}', '')
                qty_damaged = request.POST.get(f'qty_damaged_{item.pk}', '0')
                condition_notes = request.POST.get(f'condition_notes_{item.pk}', '')

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

                item.qty_received = qty_received
                item.qty_damaged = qty_damaged
                item.condition_notes = condition_notes
                item.save()

                if qty_received + qty_damaged != item.qty_sent:
                    has_discrepancy = True

            execute_transfer(t, waybill=waybill)

            t.status = 'received'
            t.completed_at = timezone.now()
            t.save()

            from core.models import TransferNotification
            TransferNotification.objects.filter(
                branch_code=t.to_branch_code, transfer_pk=t.pk, is_read=False
            ).update(is_read=True)

            waybill.received_at = timezone.now()
            waybill.received_by = request.user
            waybill.status = 'partial' if has_discrepancy else 'received'
            waybill.save()

            if has_discrepancy:
                messages.warning(request, f'Transfer {t.reference} received with discrepancies.')
            else:
                messages.success(request, f'Transfer {t.reference} received successfully.')
            return redirect('transfers_detail', pk=pk)

    return render(request, 'transfers/verify_receive.html', {
        'page_title': 'Verify Receipt',
        'transfer': t,
        'waybill': waybill,
    })


@login_required
@module_permission_required('shipping', 'edit')
@require_POST
def transfers_cancel(request, pk):
    current_branch = get_current_branch_code()
    t = get_object_or_404(StockTransfer, pk=pk)
    if t.from_branch_code != current_branch and t.to_branch_code != current_branch:
        messages.error(request, 'You can only cancel transfers involving your current branch.')
        return redirect('transfers_detail', pk=pk)
    if t.status in ('received', 'complete', 'cancelled'):
        messages.error(request, f'Cannot cancel a {t.get_status_display().lower()} transfer.')
        return redirect('transfers_detail', pk=pk)
    t.status = 'cancelled'
    t.save()
    messages.success(request, f'Transfer {t.reference} cancelled.')
    return redirect('transfers_list')


@login_required
@module_permission_required('shipping', 'export')
def transfers_export(request):
    qs = StockTransfer.objects.order_by('-created_at')
    headers = ['Reference', 'From Branch', 'To Branch', 'Items', 'Status', 'Created', 'Completed']
    rows = []
    for t in qs:
        rows.append([
            t.reference, t.from_branch_code, t.to_branch_code,
            t.items.count(), t.get_status_display(),
            t.created_at.strftime('%Y-%m-%d'),
            t.completed_at.strftime('%Y-%m-%d') if t.completed_at else '',
        ])

    fmt = request.GET.get('format', 'xlsx')
    if fmt == 'pdf':
        return export_pdf('Transfer Report', headers, rows, 'transfers.pdf', landscape=True)
    return export_excel(headers, rows, 'transfers.xlsx')

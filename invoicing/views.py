from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.views.decorators.http import require_POST
from invoicing.models import TransferWaybill, TransferWaybillItem, SupplierInvoice, SupplierInvoiceItem
from receiving.models import InboundShipment
from inventory.models import Product, Supplier
from core.auth_helpers import branch_required, module_permission_required
from core.export_utils import export_excel
from django.http import HttpResponse
from io import BytesIO


# ─── Unified Invoice List ───

@login_required
@branch_required
@module_permission_required('invoicing', 'view')
def invoice_list(request):
    waybills = TransferWaybill.objects.select_related('transfer').order_by('-dispatched_at')[:10]
    supplier_invoices = SupplierInvoice.objects.select_related('supplier').order_by('-created_at')[:10]
    return render(request, 'invoicing/list.html', {
        'page_title': 'Invoicing',
        'waybills': waybills,
        'supplier_invoices': supplier_invoices,
    })


# ─── Waybills ───

@login_required
@branch_required
@module_permission_required('invoicing', 'view')
def waybill_list(request):
    waybills = TransferWaybill.objects.select_related('transfer').order_by('-dispatched_at')
    return render(request, 'invoicing/waybill_list.html', {
        'page_title': 'Waybills',
        'waybills': waybills,
    })


@login_required
@branch_required
@module_permission_required('invoicing', 'view')
def waybill_detail(request, pk):
    waybill = get_object_or_404(TransferWaybill.objects.select_related('transfer'), pk=pk)
    return render(request, 'invoicing/waybill_detail.html', {
        'page_title': f'Waybill {waybill.waybill_number}',
        'waybill': waybill,
    })


@login_required
@branch_required
@module_permission_required('invoicing', 'view')
def waybill_pdf(request, pk):
    waybill = get_object_or_404(TransferWaybill.objects.select_related('transfer'), pk=pk)
    pdf = _render_waybill_pdf(waybill)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{waybill.waybill_number}.pdf"'
    response.write(pdf)
    return response


def _render_waybill_pdf(waybill):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm,
                            leftMargin=15*mm, rightMargin=15*mm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, spaceAfter=4, textColor=colors.HexColor('#1F2937'))
    sub_style = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#6B7280'), spaceAfter=2)
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=9, leading=12)
    cell_bold = ParagraphStyle('CellB', parent=cell_style, fontName='Helvetica-Bold')

    transfer = waybill.transfer
    elements = []

    # Header
    elements.append(Paragraph(f'WAYBILL', title_style))
    elements.append(Paragraph(f'#{waybill.waybill_number}', sub_style))
    elements.append(Spacer(1, 6*mm))

    # Info table
    info_data = [
        [Paragraph('From Branch', cell_bold), Paragraph(transfer.from_branch_code, cell_style),
         Paragraph('Status', cell_bold), Paragraph(waybill.get_status_display(), cell_style)],
        [Paragraph('To Branch', cell_bold), Paragraph(transfer.to_branch_code, cell_style),
         Paragraph('Dispatched', cell_bold), Paragraph(waybill.dispatched_at.strftime('%d %b %Y %H:%M'), cell_style)],
        [Paragraph('Reference', cell_bold), Paragraph(transfer.reference, cell_style),
         Paragraph('Received', cell_bold), Paragraph(waybill.received_at.strftime('%d %b %Y %H:%M') if waybill.received_at else '—', cell_style)],
    ]
    info_table = Table(info_data, colWidths=[80, 180, 80, 150])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 6*mm))

    # Items table
    headers = ['SKU', 'Product', 'Qty Sent', 'Qty Received', 'Damaged', 'Difference']
    rows = [headers]
    for item in waybill.items.all():
        diff = (item.qty_received or 0) - item.qty_sent
        rows.append([
            item.product.sku if item.product else '—',
            item.product.name[:30] if item.product else 'Deleted',
            str(item.qty_sent),
            str(item.qty_received) if item.qty_received is not None else '—',
            str(item.qty_damaged),
            str(diff) if item.qty_received is not None else '—',
        ])
    rows.append([
        '', 'TOTALS',
        str(waybill.total_sent),
        str(waybill.total_received),
        str(waybill.total_damaged),
        str(waybill.total_received - waybill.total_sent) if waybill.received_at else '—',
    ])

    available = A4[0] - 30*mm
    col_w = available / len(headers)
    table = Table(rows, colWidths=[col_w]*len(headers))
    table_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F2937')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D1D5DB')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F9FAFB')]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F3F4F6')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]
    # Highlight discrepancy rows
    for i, item in enumerate(waybill.items.all(), start=1):
        if item.qty_received is not None and (item.qty_received + item.qty_damaged) != item.qty_sent:
            table_style.append(('TEXTCOLOR', (3, i), (-1, i), colors.HexColor('#DC2626')))
            table_style.append(('FONTNAME', (3, i), (-1, i), 'Helvetica-Bold'))
    table.setStyle(TableStyle(table_style))
    elements.append(table)

    if waybill.notes:
        elements.append(Spacer(1, 4*mm))
        elements.append(Paragraph(f'Notes: {waybill.notes}', sub_style))

    if waybill.has_discrepancy:
        elements.append(Spacer(1, 4*mm))
        d = waybill.total_sent - waybill.total_received - waybill.total_damaged
        elements.append(Paragraph(f'⚠ Discrepancy: {d} unit(s) unaccounted for', ParagraphStyle('Warn', parent=sub_style, textColor=colors.HexColor('#DC2626'), fontName='Helvetica-Bold')))

    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()


# ─── Supplier Invoices ───

@login_required
@branch_required
@module_permission_required('invoicing', 'view')
def supplier_invoice_list(request):
    invoices = SupplierInvoice.objects.select_related('supplier', 'inbound_shipment').order_by('-created_at')
    return render(request, 'invoicing/supplier_list.html', {
        'page_title': 'Supplier Invoices',
        'invoices': invoices,
    })


@login_required
@branch_required
@module_permission_required('invoicing', 'create')
def supplier_invoice_create(request):
    if request.method == 'POST':
        supplier_id = request.POST.get('supplier')
        invoice_number = request.POST.get('invoice_number', '').strip()
        po_reference = request.POST.get('po_reference', '').strip()
        invoice_date = request.POST.get('invoice_date') or timezone.now().date()
        due_date = request.POST.get('due_date') or None
        subtotal = request.POST.get('subtotal', 0)
        tax = request.POST.get('tax', 0)
        total = request.POST.get('total', 0)
        notes = request.POST.get('notes', '')

        try:
            subtotal = float(subtotal)
            tax = float(tax)
            total = float(total)
        except (ValueError, TypeError):
            messages.error(request, 'Invalid monetary values.')
            return redirect('supplier_invoice_create')

        if not invoice_number:
            messages.error(request, 'Invoice number is required.')
            return redirect('supplier_invoice_create')

        invoice = SupplierInvoice.objects.create(
            supplier_id=supplier_id or None,
            invoice_number=invoice_number,
            po_reference=po_reference,
            invoice_date=invoice_date,
            due_date=due_date,
            subtotal=subtotal,
            tax=tax,
            total=total,
            notes=notes,
        )

        # Process items
        items_added = 0
        for key, val in request.POST.items():
            if key.startswith('qty_invoiced_'):
                try:
                    row_id = int(key.replace('qty_invoiced_', ''))
                    qty = int(val)
                except (ValueError, TypeError):
                    continue
                if qty <= 0:
                    continue
                product_pk = request.POST.get(f'product_{row_id}')
                unit_price = request.POST.get(f'unit_price_{row_id}', 0)
                qty_received = request.POST.get(f'qty_received_{row_id}', 0)
                try:
                    product_pk = int(product_pk)
                    unit_price = float(unit_price)
                    qty_received = int(qty_received)
                except (ValueError, TypeError):
                    continue
                SupplierInvoiceItem.objects.create(
                    invoice=invoice,
                    product_id=product_pk,
                    qty_invoiced=qty,
                    unit_price=unit_price,
                    qty_received=qty_received,
                )
                items_added += 1

        if items_added:
            messages.success(request, f'Supplier invoice {invoice.internal_ref} created with {items_added} item(s).')
        else:
            messages.warning(request, f'Supplier invoice {invoice.internal_ref} created with no items.')
        return redirect('supplier_invoice_detail', pk=invoice.pk)

    return render(request, 'invoicing/supplier_form.html', {
        'page_title': 'New Supplier Invoice',
        'suppliers': Supplier.objects.filter(is_active=True),
        'products': Product.objects.filter(is_active=True),
        'today': timezone.now().date(),
    })


@login_required
@branch_required
@module_permission_required('invoicing', 'view')
def supplier_invoice_detail(request, pk):
    invoice = get_object_or_404(SupplierInvoice.objects.select_related('supplier', 'inbound_shipment'), pk=pk)
    shipments = InboundShipment.objects.filter(supplier=invoice.supplier, is_complete=True) if invoice.supplier else []
    return render(request, 'invoicing/supplier_detail.html', {
        'page_title': f'Invoice {invoice.internal_ref}',
        'invoice': invoice,
        'shipments': shipments,
    })


@login_required
@branch_required
@module_permission_required('invoicing', 'view')
def supplier_invoice_pdf(request, pk):
    invoice = get_object_or_404(SupplierInvoice.objects.select_related('supplier'), pk=pk)
    pdf = _render_supplier_invoice_pdf(invoice)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{invoice.internal_ref}.pdf"'
    response.write(pdf)
    return response


def _render_supplier_invoice_pdf(invoice):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from reportlab.lib.enums import TA_RIGHT

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm,
                            leftMargin=15*mm, rightMargin=15*mm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, spaceAfter=4, textColor=colors.HexColor('#1F2937'))
    sub_style = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#6B7280'), spaceAfter=2)
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=9, leading=12)
    cell_bold = ParagraphStyle('CellB', parent=cell_style, fontName='Helvetica-Bold')
    hdr_style = ParagraphStyle('Hdr', parent=styles['Normal'], fontSize=9, textColor=colors.white, fontName='Helvetica-Bold')

    elements = []
    elements.append(Paragraph('SUPPLIER INVOICE', title_style))
    elements.append(Paragraph(f'#{invoice.internal_ref}', sub_style))
    elements.append(Spacer(1, 4*mm))

    # Supplier info
    info_data = [
        [Paragraph('Supplier', cell_bold), Paragraph(str(invoice.supplier or '—'), cell_style),
         Paragraph('Invoice #', cell_bold), Paragraph(invoice.invoice_number, cell_style)],
        [Paragraph('PO Reference', cell_bold), Paragraph(invoice.po_reference or '—', cell_style),
         Paragraph('Invoice Date', cell_bold), Paragraph(invoice.invoice_date.strftime('%d %b %Y'), cell_style)],
        [Paragraph('Status', cell_bold), Paragraph(invoice.get_status_display(), cell_style),
         Paragraph('Due Date', cell_bold), Paragraph(invoice.due_date.strftime('%d %b %Y') if invoice.due_date else '—', cell_style)],
    ]
    info_table = Table(info_data, colWidths=[80, 170, 80, 170])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 6*mm))

    # Line items
    headers = ['SKU', 'Product', 'Qty Invoiced', 'Unit Price', 'Line Total', 'Qty Received']
    rows = [headers]
    for item in invoice.items.all():
        rows.append([
            item.product.sku if item.product else '—',
            item.product.name[:30] if item.product else 'Deleted',
            str(item.qty_invoiced),
            f'{item.unit_price:.2f}',
            f'{item.line_total:.2f}',
            str(item.qty_received),
        ])
    rows.append(['', '', '', '', f'{invoice.subtotal:.2f}', ''])
    rows.append(['', '', '', 'Tax', f'{invoice.tax:.2f}', ''])
    rows.append(['', '', '', 'Total', f'{invoice.total:.2f}', ''])

    available = A4[0] - 30*mm
    col_w = available / len(headers)
    table = Table(rows, colWidths=[col_w]*len(headers))
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F2937')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D1D5DB')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -4), [colors.white, colors.HexColor('#F9FAFB')]),
        ('BACKGROUND', (0, -3), (-1, -1), colors.HexColor('#F3F4F6')),
        ('FONTNAME', (0, -3), (-1, -1), 'Helvetica-Bold'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)

    if invoice.notes:
        elements.append(Spacer(1, 4*mm))
        elements.append(Paragraph(f'Notes: {invoice.notes}', sub_style))

    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()


@login_required
@branch_required
@module_permission_required('invoicing', 'edit')
@require_POST
def supplier_invoice_match(request, pk):
    invoice = get_object_or_404(SupplierInvoice, pk=pk)
    shipment_pk = request.POST.get('shipment_id')
    if not shipment_pk:
        messages.error(request, 'Please select a shipment to match.')
        return redirect('supplier_invoice_detail', pk=pk)

    shipment = get_object_or_404(InboundShipment, pk=shipment_pk)
    if shipment.supplier != invoice.supplier:
        messages.error(request, 'Shipment supplier does not match invoice supplier.')
        return redirect('supplier_invoice_detail', pk=pk)

    invoice.inbound_shipment = shipment
    # Auto-update received qty from shipment items
    for inv_item in invoice.items.all():
        if not inv_item.product:
            continue
        shipment_items = shipment.items.filter(product=inv_item.product)
        total_received = sum(i.quantity for i in shipment_items)
        inv_item.qty_received = total_received
        inv_item.save()

    # Auto-set status
    if invoice.has_discrepancy:
        invoice.status = 'partial'
    else:
        invoice.status = 'matched'
    invoice.save()

    if invoice.has_discrepancy:
        messages.warning(request, f'Invoice matched to shipment but there are quantity discrepancies.')
    else:
        messages.success(request, f'Invoice matched to shipment successfully.')
    return redirect('supplier_invoice_detail', pk=pk)

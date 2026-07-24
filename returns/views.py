from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from returns.models import ReturnRequest, ReturnItem
from inventory.models import Product
from core.auth_helpers import module_permission_required
from core.export_utils import export_excel, export_pdf


@login_required
@module_permission_required('inventory', 'view')
def returns_list(request):
    returns = ReturnRequest.objects.order_by('-created_at')
    return render(request, 'returns/list.html', {
        'page_title': 'Return & Damaged Stock',
        'returns': returns,
    })


@login_required
@module_permission_required('inventory', 'create')
def returns_new(request):
    if request.method == 'POST':
        rr = ReturnRequest.objects.create(
            reason=request.POST.get('reason', 'other'),
            return_type=request.POST.get('return_type', 'full'),
            disposition=request.POST.get('disposition', 'restock'),
            return_date=request.POST.get('return_date') or timezone.now().date(),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, f'Return #{rr.pk} created.')
        return redirect('returns_list')
    return render(request, 'returns/new.html', {
        'page_title': 'Return & Damaged Stock',
        'products': Product.objects.filter(is_active=True),
        'today': timezone.now().date(),
    })


@login_required
@module_permission_required('inventory', 'export')
def returns_export(request):
    qs = ReturnRequest.objects.prefetch_related('items').order_by('-created_at')
    headers = ['Return #', 'Reason', 'Type', 'Disposition', 'Items', 'Return Date', 'Completed', 'Notes']
    rows = []
    for r in qs:
        rows.append([
            str(r.pk), r.get_reason_display(), r.get_return_type_display(),
            r.get_disposition_display(), r.items.count(),
            r.return_date.strftime('%Y-%m-%d') if r.return_date else '',
            'Yes' if r.is_complete else 'No', r.notes,
        ])

    fmt = request.GET.get('format', 'xlsx')
    if fmt == 'pdf':
        return export_pdf('Returns Report', headers, rows, 'returns.pdf', landscape=True)
    return export_excel(headers, rows, 'returns.xlsx')

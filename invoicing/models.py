from django.db import models
from django.conf import settings
from inventory.models import Product, Supplier
from transfers.models import StockTransfer
from receiving.models import InboundShipment


class TransferWaybill(models.Model):
    STATUS_CHOICES = [
        ('dispatched', 'Dispatched'),
        ('received', 'Received'),
        ('partial', 'Partial'),
        ('reconciled', 'Reconciled'),
    ]

    waybill_number = models.CharField(max_length=30, unique=True, blank=True)
    transfer = models.OneToOneField(StockTransfer, on_delete=models.CASCADE, related_name='waybill')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='dispatched')
    notes = models.TextField(blank=True)
    dispatched_at = models.DateTimeField(auto_now_add=True)
    received_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, db_constraint=False)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='waybills_received', db_constraint=False)

    class Meta:
        ordering = ['-dispatched_at']

    def __str__(self):
        return self.waybill_number or f'Waybill #{self.pk}'

    def save(self, *args, **kwargs):
        if not self.waybill_number:
            import datetime
            year = datetime.datetime.now().year
            count = TransferWaybill.objects.count() + 1
            self.waybill_number = f'WAY-{year}-{count:04d}'
        super().save(*args, **kwargs)

    @property
    def total_sent(self):
        return sum(i.qty_sent for i in self.items.all())

    @property
    def total_received(self):
        return sum(i.qty_received or 0 for i in self.items.all())

    @property
    def total_damaged(self):
        return sum(i.qty_damaged for i in self.items.all())

    @property
    def has_discrepancy(self):
        return self.total_sent != self.total_received + self.total_damaged


class TransferWaybillItem(models.Model):
    waybill = models.ForeignKey(TransferWaybill, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    qty_sent = models.PositiveIntegerField(default=0)
    qty_received = models.PositiveIntegerField(null=True, blank=True)
    qty_damaged = models.PositiveIntegerField(default=0)
    condition_notes = models.TextField(blank=True)

    def __str__(self):
        return f'{self.product} x{self.qty_sent} sent'


class SupplierInvoice(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('matched', 'Matched'),
        ('partial', 'Partial Match'),
        ('reconciled', 'Reconciled'),
        ('cancelled', 'Cancelled'),
    ]

    internal_ref = models.CharField(max_length=30, unique=True, blank=True)
    invoice_number = models.CharField(max_length=100)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True)
    inbound_shipment = models.OneToOneField(InboundShipment, on_delete=models.SET_NULL, null=True, blank=True, related_name='supplier_invoice')
    po_reference = models.CharField(max_length=50, blank=True)
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.internal_ref} – {self.supplier}'

    def save(self, *args, **kwargs):
        if not self.internal_ref:
            import datetime
            year = datetime.datetime.now().year
            count = SupplierInvoice.objects.count() + 1
            self.internal_ref = f'SINV-{year}-{count:04d}'
        super().save(*args, **kwargs)

    @property
    def total_qty_invoiced(self):
        return sum(i.qty_invoiced for i in self.items.all())

    @property
    def total_qty_received(self):
        return sum(i.qty_received for i in self.items.all())

    @property
    def has_discrepancy(self):
        return self.total_qty_invoiced != self.total_qty_received


class SupplierInvoiceItem(models.Model):
    invoice = models.ForeignKey(SupplierInvoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    qty_invoiced = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    qty_received = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f'{self.product} x{self.qty_invoiced} @ {self.unit_price}'

    @property
    def line_total(self):
        return self.qty_invoiced * self.unit_price

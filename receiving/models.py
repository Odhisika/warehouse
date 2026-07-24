from django.db import models
from inventory.models import Product, Supplier


class InboundShipment(models.Model):
    CONDITION_CHOICES = [('pristine','Pristine'),('good','Good'),('damaged','Damaged')]

    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    invoice_ref = models.CharField(max_length=50, blank=True)
    po_reference = models.CharField(max_length=50, blank=True)
    receive_date = models.DateField()
    notes = models.TextField(blank=True)
    is_complete = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.invoice_ref or f"Shipment #{self.pk}"

    @property
    def total_units(self):
        return sum(i.quantity for i in self.items.all())

    @property
    def total_value(self):
        return sum(i.line_total for i in self.items.all())


class InboundItem(models.Model):
    CONDITION_CHOICES = [('pristine','Pristine'),('good','Good'),('damaged','Damaged')]

    shipment = models.ForeignKey(InboundShipment, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    batch_number = models.CharField(max_length=50, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    quantity = models.PositiveIntegerField(default=0)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='pristine')

    @property
    def line_total(self):
        return self.quantity * self.unit_cost

from django.db import models
from inventory.models import Product


class StockTransfer(models.Model):
    STATUS_CHOICES = [('draft','Draft'),('pending','Pending'),('in_transit','In Transit'),('received','Received'),('complete','Complete'),('cancelled','Cancelled')]
    reference = models.CharField(max_length=50, blank=True)
    from_branch_code = models.CharField(max_length=20)
    to_branch_code = models.CharField(max_length=20)
    assigned_vehicle = models.ForeignKey('fleet.Vehicle', on_delete=models.SET_NULL, null=True, blank=True, related_name='transfers', db_constraint=False)
    assigned_driver = models.ForeignKey('fleet.Driver', on_delete=models.SET_NULL, null=True, blank=True, related_name='transfers', db_constraint=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.reference or f"Transfer #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.reference:
            count = StockTransfer.objects.count() + 1
            self.reference = f"TFR-{count:04d}"
        super().save(*args, **kwargs)


class TransferItem(models.Model):
    transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField(default=0)
    weight_kg = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.product} x{self.quantity}"

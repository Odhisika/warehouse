from django.db import models
from inventory.models import Product
from dispatch.models import DispatchOrder


class ReturnRequest(models.Model):
    REASON_CHOICES = [
        ('customer_return', 'Customer Return'),
        ('damaged_transit', 'Damaged in Transit'),
        ('wrong_item', 'Wrong Item'),
        ('expired', 'Expired'),
        ('other', 'Other'),
    ]
    DISPOSITION_CHOICES = [
        ('restock', 'Restock'),
        ('quarantine', 'Quarantine'),
        ('dispose', 'Dispose'),
        ('return_supplier', 'Return to Supplier'),
    ]
    TYPE_CHOICES = [('full', 'Full Return'), ('partial', 'Partial Return')]

    original_order = models.ForeignKey(DispatchOrder, on_delete=models.SET_NULL, null=True, blank=True)
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    return_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='full')
    disposition = models.CharField(max_length=20, choices=DISPOSITION_CHOICES, default='restock')
    return_date = models.DateField()
    notes = models.TextField(blank=True)
    is_complete = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Return #{self.pk}"


class ReturnItem(models.Model):
    CONDITION_CHOICES = [('good','Good'),('damaged','Damaged'),('pristine','Pristine')]
    return_request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField(default=1)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='good')

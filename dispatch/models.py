from django.db import models
from inventory.models import Product


class Customer(models.Model):
    name = models.CharField(max_length=200)
    customer_id = models.CharField(max_length=50, unique=True)
    zone = models.CharField(max_length=100, blank=True)
    shipping_method = models.CharField(max_length=100, blank=True)
    credit_status = models.CharField(max_length=20, default='ok')
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return f"{self.name} ({self.customer_id})"


class DispatchOrder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    CARRIER_CHOICES = [
        ('fedex', 'FedEx Ground'),
        ('dhl', 'DHL Global'),
        ('swift', 'Swift Express'),
        ('logitrans', 'LogiTrans'),
        ('other', 'Other'),
    ]

    dispatch_id = models.CharField(max_length=30, unique=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    carrier = models.CharField(max_length=20, choices=CARRIER_CHOICES, blank=True)
    destination = models.CharField(max_length=200, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    handling_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=15)
    notes = models.TextField(blank=True)
    assigned_vehicle = models.ForeignKey('fleet.Vehicle', on_delete=models.SET_NULL, null=True, blank=True, related_name='dispatches')
    assigned_driver = models.ForeignKey('fleet.Driver', on_delete=models.SET_NULL, null=True, blank=True, related_name='dispatches')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.dispatch_id or f"Order #{self.pk}"

    @property
    def tax_amount(self):
        return self.subtotal * self.tax_rate / 100

    @property
    def grand_total(self):
        return self.subtotal + self.handling_fee + self.tax_amount

    def save(self, *args, **kwargs):
        if not self.dispatch_id:
            import datetime
            from django.db import transaction
            year = datetime.datetime.now().year
            prefix = f"DISP-{year}-"
            last = DispatchOrder.objects.filter(
                dispatch_id__startswith=prefix
            ).order_by('-dispatch_id').values_list('dispatch_id', flat=True).first()
            if last:
                try:
                    num = int(last.split('-')[-1]) + 1
                except (ValueError, IndexError):
                    num = DispatchOrder.objects.filter(dispatch_id__startswith=prefix).count() + 1
            else:
                num = 1
            self.dispatch_id = f"{prefix}{num:04d}"
        super().save(*args, **kwargs)


class DispatchItem(models.Model):
    order = models.ForeignKey(DispatchOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    batch_number = models.CharField(max_length=50, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.product} x{self.quantity}"

from django.db import models
from django.contrib.auth.models import User


class Vehicle(models.Model):
    VEHICLE_TYPE_CHOICES = [
        ('truck', 'Truck'),
        ('van', 'Van'),
        ('motorcycle', 'Motorcycle'),
        ('pickup', 'Pickup'),
        ('trailer', 'Trailer'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('maintenance', 'Under Maintenance'),
        ('retired', 'Retired'),
    ]

    plate_number = models.CharField(max_length=20, unique=True)
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPE_CHOICES, default='truck')
    make_model = models.CharField(max_length=100, blank=True, help_text='e.g. Toyota Hilux')
    capacity_weight_kg = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text='Max payload in kg')
    capacity_volume_m3 = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text='Max cargo volume in m³')
    insurance_expiry = models.DateField(null=True, blank=True)
    last_service_date = models.DateField(null=True, blank=True)
    fitness_cert_expiry = models.DateField(null=True, blank=True)
    assigned_branch = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['plate_number']

    def __str__(self):
        return f"{self.plate_number} ({self.get_vehicle_type_display()})"

    @property
    def _parse_date(self):
        import datetime
        def _parse(d):
            if d is None:
                return None
            if isinstance(d, datetime.date):
                return d
            if isinstance(d, str):
                try:
                    return datetime.date.fromisoformat(d)
                except (ValueError, TypeError):
                    return None
            return None
        return _parse

    @property
    def insurance_valid(self):
        _parse = self._parse_date
        exp = _parse(self.insurance_expiry)
        if not exp:
            return True
        import datetime
        return exp >= datetime.date.today()

    @property
    def fitness_valid(self):
        _parse = self._parse_date
        exp = _parse(self.fitness_cert_expiry)
        if not exp:
            return True
        import datetime
        return exp >= datetime.date.today()

    @property
    def documents_valid(self):
        return self.insurance_valid and self.fitness_valid


class Driver(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, db_constraint=False)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    license_number = models.CharField(max_length=50, unique=True)
    license_expiry = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    assigned_branch = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['first_name', 'last_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def license_valid(self):
        if not self.license_expiry:
            return True
        import datetime
        if isinstance(self.license_expiry, str):
            try:
                exp = datetime.date.fromisoformat(self.license_expiry)
            except (ValueError, TypeError):
                return True
        else:
            exp = self.license_expiry
        return exp >= datetime.date.today()


class DriverVehicleAssignment(models.Model):
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='vehicle_assignments')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='driver_assignments')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text='Blank = currently assigned')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.driver} → {self.vehicle.plate_number} ({self.start_date})"

    @property
    def is_current(self):
        if self.end_date:
            import datetime
            return self.end_date >= datetime.date.today()
        return True


class TripSheet(models.Model):
    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('in_transit', 'In Transit'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    trip_number = models.CharField(max_length=30, unique=True, blank=True)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name='trips')
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name='trips')
    dispatch_order = models.ForeignKey('dispatch.DispatchOrder', on_delete=models.SET_NULL, null=True, blank=True, related_name='trip_sheets')
    transfer = models.ForeignKey('transfers.StockTransfer', on_delete=models.SET_NULL, null=True, blank=True, related_name='trip_sheets')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    departure_time = models.DateTimeField(null=True, blank=True)
    estimated_arrival = models.DateTimeField(null=True, blank=True)
    actual_arrival = models.DateTimeField(null=True, blank=True)
    odometer_start = models.PositiveIntegerField(default=0)
    odometer_end = models.PositiveIntegerField(default=0)
    fuel_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    toll_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    driver_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    route = models.CharField(max_length=200, blank=True, help_text='e.g. Accra → Kumasi → Tamale')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.trip_number or f"Trip #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.trip_number:
            import datetime
            year = datetime.datetime.now().year
            prefix = f"TRIP-{year}-"
            last = TripSheet.objects.filter(
                trip_number__startswith=prefix
            ).order_by('-trip_number').values_list('trip_number', flat=True).first()
            if last:
                try:
                    num = int(last.split('-')[-1]) + 1
                except (ValueError, IndexError):
                    num = TripSheet.objects.filter(trip_number__startswith=prefix).count() + 1
            else:
                num = 1
            self.trip_number = f"{prefix}{num:04d}"
        super().save(*args, **kwargs)

    @property
    def total_trip_cost(self):
        return self.fuel_cost + self.toll_cost + self.driver_allowance

    @property
    def distance_km(self):
        if self.odometer_end and self.odometer_start:
            return self.odometer_end - self.odometer_start
        return 0

    @property
    def linked_object(self):
        if self.dispatch_order:
            return self.dispatch_order
        if self.transfer:
            return self.transfer
        return None

    @property
    def linked_type(self):
        if self.dispatch_order:
            return 'Dispatch'
        if self.transfer:
            return 'Transfer'
        return None


class ProofOfDelivery(models.Model):
    dispatch_order = models.OneToOneField(
        'dispatch.DispatchOrder', on_delete=models.CASCADE, related_name='pod'
    )
    recipient_name = models.CharField(max_length=200)
    recipient_phone = models.CharField(max_length=30, blank=True)
    signature_image = models.ImageField(upload_to='signatures/', blank=True)
    delivery_photo = models.ImageField(upload_to='delivery_photos/', blank=True)
    delivery_timestamp = models.DateTimeField(auto_now_add=True)
    gps_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    gps_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    damage_notes = models.TextField(blank=True, help_text='Describe any damage observed')
    delivery_notes = models.TextField(blank=True)
    delivered_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, db_constraint=False
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Proof of Delivery'
        verbose_name_plural = 'Proofs of Delivery'
        ordering = ['-delivery_timestamp']

    def __str__(self):
        return f"POD for {self.dispatch_order.dispatch_id} — {self.recipient_name}"

    @property
    def has_damage(self):
        return bool(self.damage_notes.strip())

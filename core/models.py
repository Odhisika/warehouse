from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator


class SiteSettings(models.Model):
    company_name = models.CharField(max_length=200, default='Nexus Warehouse')
    logo = models.ImageField(
        upload_to='brand/',
        blank=True, null=True,
        validators=[FileExtensionValidator(['png', 'jpg', 'jpeg'])]
    )
    default_branch = models.ForeignKey(
        'Branch', on_delete=models.SET_NULL, null=True, blank=True
    )
    currency = models.CharField(max_length=100, default='GHS – Ghanaian Cedi')
    timezone = models.CharField(max_length=100, default='(GMT+00:00) Africa/Accra')
    language = models.CharField(max_length=100, default='English (United States)')
    date_format = models.CharField(max_length=20, default='DD/MM/YYYY')
    theme = models.CharField(max_length=10, default='light')

    class Meta:
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        return self.company_name

    @property
    def currency_symbol(self):
        mapping = {
            'USD': '$',
            'EUR': '€',
            'GBP': '£',
            'GHS': '₵',
        }
        code = self.currency[:3] if self.currency else 'GHS'
        return mapping.get(code, '₵')

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Branch(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    location = models.CharField(max_length=100)
    manager = models.CharField(max_length=100, blank=True)
    capacity_percent = models.PositiveSmallIntegerField(default=0)
    STATUS_CHOICES = [('active', 'Active'), ('inactive', 'Inactive'), ('limited', 'Limited')]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    region = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Branches'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class SystemAlert(models.Model):
    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('warning', 'Warning'),
        ('info', 'Info'),
    ]
    title = models.CharField(max_length=200)
    description = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='info')
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class TransferNotification(models.Model):
    branch_code = models.CharField(max_length=20)
    from_branch_code = models.CharField(max_length=20, blank=True)
    transfer_pk = models.IntegerField(null=True, blank=True)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    link = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    allowed_branches = models.ManyToManyField(Branch, blank=True)
    is_global_admin = models.BooleanField(default=False, help_text='Grants access to all branches')

    def __str__(self):
        return f'{self.user.username} profile'

    def can_access_branch(self, branch_code):
        if self.is_global_admin or self.user.is_superuser:
            return True
        return self.allowed_branches.filter(code=branch_code).exists()

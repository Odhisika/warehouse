from django.contrib import admin
from inventory.models import Product, Category, Supplier, StockAlert

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_email', 'is_active']
    list_filter = ['is_active']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'category', 'stock_qty', 'unit_cost', 'condition', 'is_active']
    list_filter = ['category', 'condition', 'is_active']
    search_fields = ['name', 'sku', 'batch_number']

@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ['product', 'alert_type', 'priority', 'is_resolved', 'created_at']
    list_filter = ['alert_type', 'is_resolved', 'priority']

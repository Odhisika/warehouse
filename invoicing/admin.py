from django.contrib import admin
from invoicing.models import TransferWaybill, TransferWaybillItem, SupplierInvoice, SupplierInvoiceItem


admin.site.register(TransferWaybill)
admin.site.register(TransferWaybillItem)
admin.site.register(SupplierInvoice)
admin.site.register(SupplierInvoiceItem)

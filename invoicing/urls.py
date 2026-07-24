from django.urls import path
from invoicing import views

urlpatterns = [
    path('', views.invoice_list, name='invoice_list'),
    path('waybills/', views.waybill_list, name='waybill_list'),
    path('waybills/<int:pk>/', views.waybill_detail, name='waybill_detail'),
    path('waybills/<int:pk>/pdf/', views.waybill_pdf, name='waybill_pdf'),
    path('supplier/', views.supplier_invoice_list, name='supplier_invoice_list'),
    path('supplier/new/', views.supplier_invoice_create, name='supplier_invoice_create'),
    path('supplier/<int:pk>/', views.supplier_invoice_detail, name='supplier_invoice_detail'),
    path('supplier/<int:pk>/pdf/', views.supplier_invoice_pdf, name='supplier_invoice_pdf'),
    path('supplier/<int:pk>/match/', views.supplier_invoice_match, name='supplier_invoice_match'),
]

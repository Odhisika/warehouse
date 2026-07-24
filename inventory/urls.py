from django.urls import path
from inventory import views

urlpatterns = [
    path('', views.inventory_list, name='inventory_list'),
    path('add/', views.product_add, name='product_add'),
    path('<int:pk>/', views.product_detail, name='product_detail'),
    path('<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('export/', views.inventory_export, name='inventory_export'),
]

from django.urls import path
from dispatch import views

urlpatterns = [
    path('', views.dispatch_list, name='dispatch_list'),
    path('new/', views.dispatch_new, name='dispatch_new'),
    path('<int:pk>/', views.dispatch_detail, name='dispatch_detail'),
    path('<int:pk>/authorize/', views.dispatch_authorize, name='dispatch_authorize'),
    path('<int:pk>/ship/', views.dispatch_ship, name='dispatch_ship'),
    path('<int:pk>/deliver/', views.dispatch_deliver, name='dispatch_deliver'),
    path('<int:pk>/cancel/', views.dispatch_cancel, name='dispatch_cancel'),
    path('export/', views.dispatch_export, name='dispatch_export'),
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/new/', views.customer_new, name='customer_new'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:pk>/edit/', views.customer_edit, name='customer_edit'),
    path('customers/<int:pk>/delete/', views.customer_delete, name='customer_delete'),
]

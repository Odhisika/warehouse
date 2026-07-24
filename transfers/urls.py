from django.urls import path
from transfers import views

urlpatterns = [
    path('', views.transfers_list, name='transfers_list'),
    path('new/', views.transfers_new, name='transfers_new'),
    path('<int:pk>/', views.transfers_detail, name='transfers_detail'),
    path('<int:pk>/send/', views.transfers_send, name='transfers_send'),
    path('<int:pk>/dispatch/', views.transfers_dispatch, name='transfers_dispatch'),
    path('<int:pk>/receive/', views.transfers_receive, name='transfers_receive'),
    path('<int:pk>/verify-receive/', views.transfers_verify_receive, name='transfers_verify_receive'),
    path('<int:pk>/cancel/', views.transfers_cancel, name='transfers_cancel'),
    path('export/', views.transfers_export, name='transfers_export'),
]

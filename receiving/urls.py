from django.urls import path
from receiving import views
urlpatterns = [
    path('', views.receiving_list, name='receiving_list'),
    path('new/', views.receiving_new, name='receiving_new'),
    path('<int:pk>/', views.receiving_detail, name='receiving_detail'),
    path('<int:pk>/complete/', views.receiving_complete, name='receiving_complete'),
    path('incoming/<int:notif_pk>/', views.receiving_incoming, name='receiving_incoming'),
    path('export/', views.receiving_export, name='receiving_export'),
]

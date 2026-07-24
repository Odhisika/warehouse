from django.urls import path
from django.shortcuts import redirect
from fleet import views

urlpatterns = [
    path('', lambda r: redirect('vehicle_list', permanent=False), name='fleet_index'),
    path('vehicles/', views.vehicle_list, name='vehicle_list'),
    path('vehicles/new/', views.vehicle_new, name='vehicle_new'),
    path('vehicles/<int:pk>/', views.vehicle_detail, name='vehicle_detail'),
    path('vehicles/<int:pk>/edit/', views.vehicle_edit, name='vehicle_edit'),
    path('vehicles/<int:pk>/delete/', views.vehicle_delete, name='vehicle_delete'),

    path('drivers/', views.driver_list, name='driver_list'),
    path('drivers/new/', views.driver_new, name='driver_new'),
    path('drivers/<int:pk>/', views.driver_detail, name='driver_detail'),
    path('drivers/<int:pk>/edit/', views.driver_edit, name='driver_edit'),
    path('drivers/<int:pk>/delete/', views.driver_delete, name='driver_delete'),

    path('assign/', views.assign_driver_vehicle, name='assign_driver_vehicle'),

    path('trips/', views.trip_list, name='trip_list'),
    path('trips/new/', views.trip_new, name='trip_new'),
    path('trips/<int:pk>/', views.trip_detail, name='trip_detail'),
    path('trips/<int:pk>/depart/', views.trip_depart, name='trip_depart'),
    path('trips/<int:pk>/arrive/', views.trip_arrive, name='trip_arrive'),
    path('trips/<int:pk>/cancel/', views.trip_cancel, name='trip_cancel'),

    path('pod/<int:pk>/capture/', views.pod_capture, name='pod_capture'),
    path('pod/<int:pk>/', views.pod_detail, name='pod_detail'),
]

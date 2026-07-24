from django.urls import path
from reports import views
urlpatterns = [
    path('', views.reports_dashboard, name='reports_dashboard'),
    path('export/', views.reports_export, name='reports_export'),
]

from django.urls import path
from returns import views
urlpatterns = [
    path('', views.returns_list, name='returns_list'),
    path('new/', views.returns_new, name='returns_new'),
    path('export/', views.returns_export, name='returns_export'),
]

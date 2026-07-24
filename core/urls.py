from django.urls import path
from core import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('clear-alerts/', views.clear_alerts, name='clear_alerts'),
    path('notifications/<int:pk>/read/', views.read_notification, name='read_notification'),
    path('clear-notifications/', views.clear_notifications, name='clear_notifications'),
    path('switch-branch/<slug:code>/', views.switch_branch, name='switch_branch'),
    path('settings/', views.settings_general, name='settings_general'),
    path('settings/general/', views.settings_general, name='settings_general'),
    path('settings/roles/', views.settings_roles, name='settings_roles'),
    path('settings/branches/', views.settings_branches, name='settings_branches'),
    path('settings/security/', views.settings_security, name='settings_security'),
    path('profile/', views.profile, name='profile'),
]

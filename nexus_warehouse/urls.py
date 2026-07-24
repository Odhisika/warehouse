from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('inventory/', include('inventory.urls')),
    path('receiving/', include('receiving.urls')),
    path('dispatch/', include('dispatch.urls')),
    path('returns/', include('returns.urls')),
    path('transfers/', include('transfers.urls')),
    path('reports/', include('reports.urls')),
    path('invoicing/', include('invoicing.urls')),
    path('fleet/', include('fleet.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

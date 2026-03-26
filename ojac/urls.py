from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('marketplace.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Serve PWA files at root level
from django.views.generic import TemplateView
from django.contrib.staticfiles.storage import staticfiles_storage
from django.views.static import serve
import os
from django.conf import settings as _settings

from django.views.generic import TemplateView

urlpatterns += [
    # We use TemplateView to serve these as if they are at the root
    path('manifest.json', TemplateView.as_view(template_name='marketplace/manifest.json', content_type='application/json')),
    path('sw.js', TemplateView.as_view(template_name='marketplace/sw.js', content_type='application/javascript')),
]
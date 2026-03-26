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

urlpatterns += [
    path('manifest.json', lambda r: serve(r, 'manifest.json', document_root=_settings.STATICFILES_DIRS[0] if _settings.STATICFILES_DIRS else _settings.STATIC_ROOT or ''), name='manifest'),
    path('sw.js',         lambda r: serve(r, 'sw.js',          document_root=_settings.STATICFILES_DIRS[0] if _settings.STATICFILES_DIRS else _settings.STATIC_ROOT or ''), name='sw'),
]
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from .api import api_root
from .audio import audio_track


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api_root, name='api-root'),
    path('api/auth/', include('accounts.api_urls')),
    path('api/cards/', include('cards.urls')),
    path('api/decks/', include('decks.urls')),
    path('api/collection/', include('collects.urls')),
    path('api/banlists/', include('banlists.urls')),
    path('audio/<str:filename>/', audio_track, name='site_audio'),
    path('cards/', include('cards.page_urls')),
    path('decks/', include('decks.page_urls')),
    path('collection/', include('collects.page_urls')),
    path('ban-list/', include('banlists.page_urls')),
    path('', include('accounts.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

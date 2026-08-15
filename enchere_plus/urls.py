from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('auctions.urls', namespace='auctions')),
    path('compte/', include('accounts.urls', namespace='accounts')),
]

# Servir les fichiers media en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Pages d'erreur personnalisées
handler404 = 'auctions.views.error_404'
handler500 = 'auctions.views.error_500'

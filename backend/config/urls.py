from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    # Redirect root to batches list (site homepage)
    path('', RedirectView.as_view(url='/cards/batches/', permanent=False)),
    # Admin panel
    path('admin/', admin.site.urls),

    # API endpoints (for Flutter app)
    path('api/v1/auth/', include('accounts.urls', namespace='accounts-api')),
    path('api/v1/languages/', include('languages.urls', namespace='languages-api')),
    path('api/v1/cards/', include('cards.urls', namespace='cards-api')),

    # Web views (Django templates — for website)
    path('accounts/', include('accounts.web_urls', namespace='accounts-web')),
    path('cards/', include('cards.web_urls', namespace='cards-web')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    if getattr(settings, 'STATICFILES_DIRS', None):
        urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/stable/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.urls import path
from . import views

app_name = 'languages'

urlpatterns = [
    path('', views.LanguageListView.as_view(), name='language-list'),
    path('<str:code>/', views.LanguageDetailView.as_view(), name='language-detail'),
]


from django.urls import path
from . import views

app_name = 'cards'

urlpatterns = [
    # Batch endpoints
    path('batches/', views.BatchCreateView.as_view(), name='batch-create'),
    path('batches/list/', views.BatchListView.as_view(), name='batch-list'),
    path('batches/<int:pk>/', views.BatchDetailView.as_view(), name='batch-detail'),
    path('batches/<int:pk>/retry/', views.BatchRetryView.as_view(), name='batch-retry'),

    # Card endpoints
    path('cards/<int:pk>/', views.CardDetailView.as_view(), name='card-detail'),

    # AnkiConnect test
    path('anki/test/', views.AnkiTestConnectionView.as_view(), name='anki-test'),
]

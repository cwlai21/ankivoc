from django.urls import path
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView

app_name = 'cards-web'

urlpatterns = [
    path(
        'batches/',
        login_required(TemplateView.as_view(template_name='cards/batch_list.html')),
        name='batch-list'
    ),
    path(
        'batches/create/',
        login_required(TemplateView.as_view(template_name='cards/batch_create.html')),
        name='batch-create'
    ),
    path(
        'batches/<int:pk>/',
        login_required(TemplateView.as_view(template_name='cards/batch_detail.html')),
        name='batch-detail'
    ),
]

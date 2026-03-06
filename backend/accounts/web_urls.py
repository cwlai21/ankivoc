from django.urls import path
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required

app_name = 'accounts-web'

urlpatterns = [
    path(
        'login/',
        auth_views.LoginView.as_view(template_name='accounts/login.html'),
        name='login',
    ),
    path(
        'logout/',
        auth_views.LogoutView.as_view(),
        name='logout',
    ),
    path(
        'register/',
        TemplateView.as_view(template_name='accounts/register.html'),
        name='register',
    ),
    path(
        'profile/',
        login_required(TemplateView.as_view(template_name='accounts/profile.html')),
        name='profile',
    ),
]



from django.urls import path
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from . import views

app_name = 'accounts-web'

urlpatterns = [
    path(
        'login/',
        views.WebLoginView.as_view(),
        name='login',
    ),
    path(
        'logout/',
        views.WebLogoutView.as_view(),
        name='logout',
    ),
    path(
        'register/',
        views.RegisterView.as_view(),
        name='register',
    ),
    path(
        'verify-code/',
        views.VerifyCodeView.as_view(),
        name='verify-code',
    ),
    path(
        'resend-code/',
        views.ResendCodeView.as_view(),
        name='resend-code',
    ),
    path(
        'profile/',
        login_required(TemplateView.as_view(template_name='accounts/profile.html')),
        name='profile',
    ),
]



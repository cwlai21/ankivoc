from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change-password'),
    path('check-anki/', views.CheckAnkiStatusView.as_view(), name='check-anki'),
    path('download-ankiconnect/', views.DownloadAnkiConnectView.as_view(), name='download-ankiconnect'),
    path('verify-email/', views.VerifyEmailAPIView.as_view(), name='verify-email'),
    path('resend-verification/', views.ResendVerificationAPIView.as_view(), name='resend-verification'),
]


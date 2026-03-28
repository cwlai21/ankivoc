from rest_framework import generics, permissions
from .models import Language
from .serializers import LanguageSerializer, LanguageListSerializer


class LanguageListView(generics.ListAPIView):
    """
    GET /api/v1/languages/
    List all languages.
    """
    serializer_class = LanguageListSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # Skip auth entirely — invalid tokens must not cause 401

    def get_queryset(self):
        return Language.objects.all()


class LanguageDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/languages/{code}/
    Get language detail with its card template.
    """
    serializer_class = LanguageSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'code'

    def get_queryset(self):
        """Allow retrieving any language by code (used for template info)."""
        return Language.objects.all()
# Views for `languages` app (placeholder).

# Implement view functions or class-based views when needed.

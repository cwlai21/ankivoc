from rest_framework import generics, permissions
from .models import Language
from .serializers import LanguageSerializer, LanguageListSerializer


class LanguageListView(generics.ListAPIView):
    """
    GET /api/v1/languages/
    List all active languages.
    """
    queryset = Language.objects.filter(is_active=True)
    serializer_class = LanguageListSerializer
    permission_classes = [permissions.IsAuthenticated]


class LanguageDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/languages/{code}/
    Get language detail with its card template.
    """
    queryset = Language.objects.filter(is_active=True)
    serializer_class = LanguageSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'code'
# Views for `languages` app (placeholder).

# Implement view functions or class-based views when needed.

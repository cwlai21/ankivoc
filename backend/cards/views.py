import logging
import threading
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import VocabularyBatch, VocabularyCard
from .serializers import (
    VocabularyBatchCreateSerializer,
    VocabularyBatchListSerializer,
    VocabularyBatchDetailSerializer,
    VocabularyCardSerializer,
)
# CardPipeline is imported lazily inside handlers to avoid import-time
# errors when the pipeline implementation is not present during import.

logger = logging.getLogger(__name__)


class BatchCreateView(APIView):
    """
    POST /api/v1/cards/batches/
    Submit a new vocabulary batch for processing.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = VocabularyBatchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        # Create the batch
        # Explanation language logic
        explanation_language = data['explanation_language']
        if data['target_language'].code == 'en':
            # If target is English, force explanation to Chinese
            from languages.models import Language
            explanation_language = Language.objects.get(code='zh')
        elif data['target_language'].code == 'ja':
            # If target is Japanese, force explanation to Traditional Chinese
            from languages.models import Language
            explanation_language = Language.objects.get(code='zh')
        elif explanation_language.code not in ['en', 'fr', 'zh']:
            # Otherwise, default to English if not one of the allowed
            from languages.models import Language
            explanation_language = Language.objects.get(code='en')

        batch = VocabularyBatch.objects.create(
            user=request.user,
            target_language=data['target_language'],
            explanation_language=explanation_language,
            raw_input='\n'.join(data['vocabulary']),
            status=VocabularyBatch.Status.PENDING,
        )

        # Create individual card records
        cards = []
        for word in data['vocabulary']:
            card = VocabularyCard.objects.create(
                batch=batch,
                input_text=word,
                status=VocabularyCard.Status.PENDING,
            )
            cards.append(card)

        # Process the batch synchronously (real-time)
        try:
            from .services.pipeline import CardPipeline
            pipeline = CardPipeline(batch)
            pipeline.process()
        except Exception as e:
            logger.error(f'Pipeline error for batch {batch.id}: {e}')
            batch.status = VocabularyBatch.Status.FAILED
            batch.error_message = str(e)
            batch.save()

        # Refresh from DB to get updated status
        batch.refresh_from_db()

        # Return result
        result_serializer = VocabularyBatchDetailSerializer(batch)

        if batch.status == VocabularyBatch.Status.COMPLETED:
            return Response(result_serializer.data, status=status.HTTP_201_CREATED)
        elif batch.status == VocabularyBatch.Status.PARTIAL_FAILURE:
            return Response(result_serializer.data, status=status.HTTP_207_MULTI_STATUS)
        else:
            error_payload = {
                'error': 'Pipeline failed',
                'message': batch.error_message or 'An unexpected error occurred.',
                'batch': result_serializer.data
            }
            return Response(error_payload, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BatchListView(generics.ListAPIView):
    """
    GET /api/v1/cards/batches/
    List all batches for the current user.
    """
    serializer_class = VocabularyBatchListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return VocabularyBatch.objects.filter(
            user=self.request.user
        ).select_related('target_language')


class BatchDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/cards/batches/{id}/
    Get batch detail with all card statuses.
    """
    serializer_class = VocabularyBatchDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return VocabularyBatch.objects.filter(
            user=self.request.user
        ).prefetch_related('cards')


class BatchRetryView(APIView):
    """
    POST /api/v1/cards/batches/{id}/retry/
    Retry all failed cards in a batch.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            batch = VocabularyBatch.objects.get(pk=pk, user=request.user)
        except VocabularyBatch.DoesNotExist:
            return Response(
                {'error': 'Batch not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Reset failed cards to pending
        failed_cards = batch.cards.filter(status=VocabularyCard.Status.FAILED)
        if not failed_cards.exists():
            return Response(
                {'message': 'No failed cards to retry.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        failed_cards.update(
            status=VocabularyCard.Status.PENDING,
            error_message='',
        )
        batch.status = VocabularyBatch.Status.PENDING
        batch.save()

        # Reprocess in background thread so HTTP request returns quickly.
        def _run_pipeline(batch_id):
            try:
                from .models import VocabularyBatch
                from .services.pipeline import CardPipeline
                b = VocabularyBatch.objects.get(pk=batch_id)
                pipeline = CardPipeline(b)
                pipeline.process()
            except Exception as e:
                logger.exception(f'Retry pipeline error for batch {batch_id}: {e}')

        thread = threading.Thread(target=_run_pipeline, args=(batch.id,))
        thread.daemon = True
        thread.start()

        # Return accepted with current batch snapshot. Client may poll for updates.
        batch.refresh_from_db()
        serializer = VocabularyBatchDetailSerializer(batch)
        return Response({'message': 'Retry started', 'batch': serializer.data}, status=status.HTTP_202_ACCEPTED)


class CardDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/cards/cards/{id}/
    Get full detail of a single card.
    """
    serializer_class = VocabularyCardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return VocabularyCard.objects.filter(
            batch__user=self.request.user
        )


class AnkiTestConnectionView(APIView):
    """
    GET /api/v1/cards/anki/test/
    Test the user's AnkiConnect connection.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .services.anki_connect import AnkiConnectClient

        client = AnkiConnectClient(
            url=request.user.anki_connect_url,
            api_key=request.user.anki_connect_api_key,
        )

        try:
            version = client.test_connection()
            return Response({
                'connected': True,
                'version': version,
                'url': request.user.anki_connect_url,
                'message': 'Successfully connected to AnkiConnect!'
            })
        except Exception as e:
            return Response({
                'connected': False,
                'url': request.user.anki_connect_url,
                'message': f'Connection failed: {str(e)}'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
# Views for `cards` app (placeholder).

# Implement view functions or class-based views when needed.

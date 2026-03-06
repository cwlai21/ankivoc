from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from cards.models import VocabularyBatch, VocabularyCard
from languages.models import Language

User = get_user_model()


class RetryEndpointTest(TestCase):
    def setUp(self):
        # Create user
        self.user = User.objects.create_user(username='tuser', password='pass')
        # Ensure language exists
        self.lang = Language.objects.create(code='fr', name='French', native_name='Français')
        # Create a batch with one failed card
        self.batch = VocabularyBatch.objects.create(
            user=self.user,
            target_language=self.lang,
            explanation_language=self.lang,
            raw_input='pomme',
            status=VocabularyBatch.Status.PARTIAL_FAILURE,
        )
        self.card = VocabularyCard.objects.create(
            batch=self.batch,
            input_text='pomme',
            status=VocabularyCard.Status.FAILED,
            error_message='Simulated failure',
        )
        self.client = Client()
        self.client.login(username='tuser', password='pass')

    def test_retry_marks_failed_cards_pending_and_returns_202(self):
        url = f'/api/v1/cards/batches/{self.batch.id}/retry/'
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 202)
        data = resp.json()
        # Response should include 'message' and 'batch'
        self.assertIn('message', data)
        self.assertIn('batch', data)
        # Reload card from DB
        self.card.refresh_from_db()
        self.assertEqual(self.card.status, VocabularyCard.Status.PENDING)
        # Batch status should have been set to PENDING as view does
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, VocabularyBatch.Status.PENDING)

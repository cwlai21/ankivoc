from unittest.mock import patch
from django.test import SimpleTestCase
from cards.services.anki_connect import AnkiConnectClient


class DummyResponse:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    def raise_for_status(self):
        return None

    def json(self):
        return {'result': self._result, 'error': self._error}


def make_mock_post():
    """
    Returns a mock `requests.post` replacement that simulates AnkiConnect behavior:
      - First addNote -> error 'deck was not found'
      - createDeck -> success and deck becomes present
      - createModel -> success and model becomes present
      - Subsequent addNote -> success with note id
    """
    state = {
        'decks': set(),
        'models': set(),
        'first_addnote_called': False,
    }

    def _mock_post(url, json=None, timeout=None, **kwargs):
        action = (json or {}).get('action')

        # deckNames
        if action == 'deckNames':
            return DummyResponse(result=list(state['decks']))

        # modelNames
        if action == 'modelNames':
            return DummyResponse(result=list(state['models']))

        # createDeck
        if action == 'createDeck':
            deck = (json or {}).get('params', {}).get('deck')
            if deck:
                state['decks'].add(deck)
            return DummyResponse(result=True)

        # createModel
        if action == 'createModel':
            model = (json or {}).get('params', {}).get('modelName')
            if model:
                state['models'].add(model)
            return DummyResponse(result=True)

        # addNote
        if action == 'addNote':
            # simulate initial failure due to missing deck/model
            if not state['first_addnote_called']:
                state['first_addnote_called'] = True
                return DummyResponse(result=None, error=f'deck was not found: {json.get("params", {}).get("note", {}).get("deckName")}')
            # later succeed
            return DummyResponse(result=999999)

        # default
        return DummyResponse(result=None)

    return _mock_post


class AnkiConnectRetryMockTest(SimpleTestCase):
    @patch('cards.services.anki_connect.requests.post')
    def test_add_note_retries_and_recovers(self, mock_post):
        mock_post.side_effect = make_mock_post()

        client = AnkiConnectClient(url='http://localhost:8765')

        deck_name = 'Test::Vocab'
        model_name = 'TestModel'
        fields = {'Front': 'bonjour', 'Back': 'hello'}

        result = client.add_note(deck_name=deck_name, model_name=model_name, fields=fields)

        self.assertIn('noteId', result)
        self.assertEqual(result['noteId'], 999999)

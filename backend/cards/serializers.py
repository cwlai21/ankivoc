from rest_framework import serializers
from .models import VocabularyBatch, VocabularyCard


class VocabularyCardSerializer(serializers.ModelSerializer):
    """Full card detail serializer."""

    class Meta:
        model = VocabularyCard
        fields = [
            'id',
            'input_text',
            'target_word',
            'explanation_word',
            'synonyme',
            'conjugaison_genre',
            'audio_file',
            'exemple_target',
            'exemple_explanation',
            'exemple1_audio',
            'exemple2_target',
            'exemple2_explanation',
            'exemple2_audio',
            'extend',
            'hint',
            'status',
            'anki_note_id',
            'error_message',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class VocabularyCardSummarySerializer(serializers.ModelSerializer):
    """Lightweight card serializer for batch list views."""

    class Meta:
        model = VocabularyCard
        fields = [
            'id',
            'input_text',
            'target_word',
            'explanation_word',
            'status',
            'error_message',
        ]
        read_only_fields = fields


class VocabularyBatchDetailSerializer(serializers.ModelSerializer):
    """Batch detail with all cards."""
    cards = VocabularyCardSummarySerializer(many=True, read_only=True)
    target_language_name = serializers.CharField(
        source='target_language.name', read_only=True
    )
    explanation_language_name = serializers.CharField(
        source='explanation_language.name', read_only=True
    )
    summary = serializers.SerializerMethodField()

    class Meta:
        model = VocabularyBatch
        fields = [
            'id',
            'target_language',
            'target_language_name',
            'explanation_language',
            'explanation_language_name',
            'raw_input',
            'status',
            'error_message',
            'cards',
            'summary',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_summary(self, obj):
        return {
            'total': obj.total_cards,
            'pushed': obj.pushed_cards,
            'failed': obj.failed_cards,
            'pending': obj.cards.filter(
                status__in=['pending', 'translated', 'tts_done']
            ).count(),
        }


class VocabularyBatchListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing batches."""
    target_language_name = serializers.CharField(
        source='target_language.name', read_only=True
    )
    total_cards = serializers.IntegerField(read_only=True)
    pushed_cards = serializers.IntegerField(read_only=True)
    failed_cards = serializers.IntegerField(read_only=True)

    class Meta:
        model = VocabularyBatch
        fields = [
            'id',
            'target_language_name',
            'status',
            'total_cards',
            'pushed_cards',
            'failed_cards',
            'created_at',
        ]
        read_only_fields = fields


class VocabularyBatchCreateSerializer(serializers.Serializer):
    """
    Serializer for creating a new batch.
    Accepts a list of vocabulary words and language selections.
    """
    target_language = serializers.CharField(
        help_text='Language code, e.g. fr'
    )
    explanation_language = serializers.CharField(
        help_text='Language code, e.g. en'
    )
    vocabulary = serializers.ListField(
        child=serializers.CharField(max_length=500),
        min_length=1,
        max_length=50,
        help_text='List of vocabulary words/phrases, max 50 per batch'
    )
    deck_name = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        help_text='Override deck name (optional)'
    )

    def validate_target_language(self, value):
        from languages.models import Language
        try:
            return Language.objects.get(code=value, is_active=True)
        except Language.DoesNotExist:
            raise serializers.ValidationError(
                f'Language with code "{value}" not found or not active.'
            )

    def validate_explanation_language(self, value):
        from languages.models import Language
        try:
            return Language.objects.get(code=value, is_active=True)
        except Language.DoesNotExist:
            raise serializers.ValidationError(
                f'Language with code "{value}" not found or not active.'
            )

    def validate_vocabulary(self, value):
        # Strip whitespace and remove empty entries
        cleaned = [word.strip() for word in value if word.strip()]
        if not cleaned:
            raise serializers.ValidationError('At least one vocabulary word is required.')
        return cleaned

    def validate(self, data):
        if data['target_language'] == data['explanation_language']:
            raise serializers.ValidationError(
                'Target language and explanation language must be different.'
            )
        # Template will be auto-generated by pipeline if not exists
        # No validation needed here
        return data

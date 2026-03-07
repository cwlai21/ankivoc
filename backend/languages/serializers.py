from rest_framework import serializers
from .models import Language, CardTemplate


class CardTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CardTemplate
        fields = [
            'id',
            'anki_model_name',
            'default_deck_name',
            'fields_definition',
            'llm_prompt_template',
        ]


class LanguageSerializer(serializers.ModelSerializer):
    card_template = CardTemplateSerializer(read_only=True)

    class Meta:
        model = Language
        fields = [
            'id',
            'name',
            'code',
            'native_name',
            'azure_tts_voice',
            'azure_tts_locale',
            'is_active',
            'card_template',
            'vocab_label',
        ]


class LanguageListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for dropdowns."""
    has_template = serializers.SerializerMethodField()

    class Meta:
        model = Language
        fields = ['id', 'name', 'code', 'native_name', 'has_template', 'is_active']

    def get_has_template(self, obj):
        return hasattr(obj, 'card_template')

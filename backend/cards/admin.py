from django.contrib import admin
from .models import VocabularyBatch, VocabularyCard


class VocabularyCardInline(admin.TabularInline):
    """Show cards inline on the batch admin page."""
    model = VocabularyCard
    extra = 0
    readonly_fields = [
        'input_text', 'target_word', 'explanation_word',
        'status', 'anki_note_id', 'error_message', 'created_at'
    ]
    fields = [
        'input_text', 'target_word', 'explanation_word',
        'status', 'anki_note_id', 'error_message'
    ]
    show_change_link = True


@admin.register(VocabularyBatch)
class VocabularyBatchAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'target_language', 'explanation_language',
        'status', 'total_cards', 'pushed_cards', 'failed_cards',
        'created_at'
    ]
    list_filter = ['status', 'target_language', 'created_at']
    search_fields = ['user__username', 'raw_input']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [VocabularyCardInline]

    def total_cards(self, obj):
        return obj.total_cards
    total_cards.short_description = 'Total'

    def pushed_cards(self, obj):
        return obj.pushed_cards
    pushed_cards.short_description = 'Pushed'

    def failed_cards(self, obj):
        return obj.failed_cards
    failed_cards.short_description = 'Failed'


@admin.register(VocabularyCard)
class VocabularyCardAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'input_text', 'target_word', 'explanation_word',
        'status', 'anki_note_id', 'batch', 'created_at'
    ]
    list_filter = ['status', 'batch__target_language']
    search_fields = ['input_text', 'target_word', 'explanation_word']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Input', {
            'fields': ('batch', 'input_text')
        }),
        ('Card Content', {
            'fields': (
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
            )
        }),
        ('Status', {
            'fields': (
                'status',
                'anki_note_id',
                'error_message',
                'created_at',
                'updated_at',
            )
        }),
    )
# Admin registrations for `cards` app (placeholder).

# Add admin.site.register(...) calls when ready.

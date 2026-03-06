from django.contrib import admin
from .models import Language, CardTemplate


class CardTemplateInline(admin.StackedInline):
    """Show CardTemplate inline on the Language admin page."""
    model = CardTemplate
    extra = 0


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'native_name', 'azure_tts_voice', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code']
    inlines = [CardTemplateInline]


@admin.register(CardTemplate)
class CardTemplateAdmin(admin.ModelAdmin):
    list_display = ['language', 'anki_model_name', 'default_deck_name']
    list_filter = ['language']
# Admin registrations for `languages` app (placeholder).

# Add admin.site.register(...) calls when ready.

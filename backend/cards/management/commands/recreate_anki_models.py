"""
Django management command to recreate Anki models with new CSS templates.
Run this after updating CSS templates to apply changes to existing models.

Usage:
    python manage.py recreate_anki_models --model "中文-(R/L)"
    python manage.py recreate_anki_models --all
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from cards.services.anki_connect import AnkiConnectClient
from languages.models import CardTemplate

User = get_user_model()


class Command(BaseCommand):
    help = 'Recreate Anki models with new CSS templates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            help='Specific model name to recreate (e.g., "中文-(R/L)")',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Recreate all models',
        )

    def handle(self, *args, **options):
        if not options['model'] and not options['all']:
            self.stdout.write(self.style.ERROR('Please specify --model or --all'))
            return

        # Get first user for AnkiConnect credentials
        user = User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR('✗ No users found in database'))
            return

        # Initialize AnkiConnect client
        anki_client = AnkiConnectClient(
            url=user.anki_connect_url,
            api_key=user.anki_connect_api_key,
        )

        # Test connection
        try:
            models = anki_client.get_model_names()
            self.stdout.write(self.style.SUCCESS(f'✓ Connected to AnkiConnect (found {len(models)} models)'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Cannot connect to AnkiConnect: {e}'))
            self.stdout.write('  Make sure Anki is running with AnkiConnect addon installed')
            return

        # Get templates to recreate
        if options['all']:
            templates = CardTemplate.objects.all()
            self.stdout.write(f'\n📋 Found {templates.count()} templates to recreate')
        else:
            templates = CardTemplate.objects.filter(anki_model_name=options['model'])
            if not templates.exists():
                self.stdout.write(self.style.ERROR(f"✗ No template found with model name '{options['model']}'"))
                self.stdout.write('\nAvailable models:')
                for t in CardTemplate.objects.all():
                    self.stdout.write(f"  - {t.anki_model_name} ({t.language.name})")
                return

        # Recreate each template
        success_count = 0
        fail_count = 0

        for template in templates:
            if self.recreate_model(anki_client, template):
                success_count += 1
            else:
                fail_count += 1

        # Summary
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(self.style.SUCCESS(f'✓ Successfully recreated: {success_count}'))
        if fail_count > 0:
            self.stdout.write(self.style.ERROR(f'✗ Failed: {fail_count}'))
        self.stdout.write(f"{'='*60}")

        if success_count > 0:
            self.stdout.write(self.style.SUCCESS('\n🎉 Models recreated! Your next cards will use the new CSS templates.'))
            self.stdout.write('   Note: Existing cards in Anki will keep their old styling.')
            self.stdout.write('   To update existing cards, you\'ll need to update the card type in Anki manually.')

    def delete_anki_model(self, anki_client, model_name):
        """Delete a model from Anki."""
        try:
            existing_models = anki_client.get_model_names()
            if model_name not in existing_models:
                self.stdout.write(f"✓ Model '{model_name}' does not exist in Anki")
                return True

            # AnkiConnect does not support deleting models programmatically
            # User must delete manually in Anki
            self.stdout.write(self.style.WARNING(f"⚠️  Model '{model_name}' exists in Anki"))
            self.stdout.write(self.style.WARNING("   AnkiConnect does not support automatic model deletion"))
            self.stdout.write(self.style.WARNING("   Please manually delete the model in Anki:"))
            self.stdout.write("   1. Open Anki")
            self.stdout.write("   2. Tools → Manage Note Types")
            self.stdout.write(f"   3. Select '{model_name}' and click 'Delete'")
            self.stdout.write("   4. Then run this command again")
            return False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error checking model '{model_name}': {e}"))
            return False

    def recreate_model(self, anki_client, template):
        """Recreate an Anki model using CardTemplate."""
        model_name = template.anki_model_name
        fields = template.fields_definition

        self.stdout.write(f"\n🔄 Recreating model: {model_name}")

        # Step 1: Delete existing model
        if not self.delete_anki_model(anki_client, model_name):
            self.stdout.write(self.style.WARNING("⚠️  Warning: Could not delete existing model, proceeding anyway..."))

        # Step 2: Create new model with updated templates
        try:
            success = anki_client.create_model_if_missing(
                model_name=model_name,
                in_order_fields=fields,
                card_template=template
            )

            if success:
                self.stdout.write(self.style.SUCCESS(f"✓ Successfully recreated model '{model_name}' with new CSS templates"))
                self.stdout.write(f"  - Front template: {len(template.front_template)} chars")
                self.stdout.write(f"  - Back template: {len(template.back_template)} chars")
                self.stdout.write(f"  - CSS: {len(template.css_style)} chars")
                return True
            else:
                self.stdout.write(self.style.ERROR(f"✗ Failed to recreate model '{model_name}'"))
                return False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error creating model '{model_name}': {e}"))
            return False

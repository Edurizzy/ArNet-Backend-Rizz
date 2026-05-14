"""Remove legacy WhatsAppBusinessAccountConnection (replaced by ConnectedAccount)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("meta_integration", "0001_initial"),
        ("integrations", "0002_seed_from_whatsapp_connection"),
    ]

    operations = [
        migrations.DeleteModel(
            name="WhatsAppBusinessAccountConnection",
        ),
    ]

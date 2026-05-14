"""Copy legacy WhatsAppBusinessAccountConnection rows into ConnectedAccount."""

import uuid

from django.db import migrations


def forwards(apps, schema_editor):
    ConnectedAccount = apps.get_model("integrations", "ConnectedAccount")
    Legacy = apps.get_model("meta_integration", "WhatsAppBusinessAccountConnection")
    old_table = Legacy._meta.db_table
    q_old = schema_editor.quote_name(old_table)

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT organization_id, business_account_id, phone_number_id,
                   display_phone_number, webhook_verify_token, is_active,
                   created_at, updated_at, deleted_at
            FROM {q_old}
            """
        )
        rows = cursor.fetchall()

    for (
        organization_id,
        business_account_id,
        phone_number_id,
        display_phone_number,
        webhook_verify_token,
        is_active,
        _created_at,
        _updated_at,
        deleted_at,
    ) in rows:
        ConnectedAccount.objects.create(
            id=uuid.uuid4(),
            organization_id=organization_id,
            provider="whatsapp_cloud",
            external_id=phone_number_id,
            display_name=display_phone_number,
            access_token="",
            refresh_token=None,
            settings={"business_account_id": business_account_id},
            webhook_verify_token=webhook_verify_token,
            is_active=is_active,
            last_sync_at=None,
            deleted_at=deleted_at,
        )


def backwards(apps, schema_editor):
    ConnectedAccount = apps.get_model("integrations", "ConnectedAccount")
    ConnectedAccount.objects.filter(provider="whatsapp_cloud").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0001_initial"),
        ("meta_integration", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

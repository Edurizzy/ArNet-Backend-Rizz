# Generated manually for Meta webhook ingestion.

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="RawWebhookEvent",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, help_text="Timestamp when the record was created")),
                ("updated_at", models.DateTimeField(auto_now=True, help_text="Timestamp when the record was last updated")),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, help_text="Unique identifier for this record", primary_key=True, serialize=False)),
                ("deleted_at", models.DateTimeField(blank=True, help_text="Timestamp when the record was soft deleted", null=True)),
                ("provider", models.CharField(default="meta", max_length=50)),
                ("event_type", models.CharField(max_length=100)),
                ("payload", models.JSONField()),
                ("headers", models.JSONField(default=dict)),
                ("correlation_id", models.UUIDField(db_index=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("processing", "Processing"), ("processed", "Processed"), ("failed", "Failed")], default="pending", max_length=20)),
                ("error_message", models.TextField(blank=True, null=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("organization", models.ForeignKey(blank=True, help_text="Organization this record belongs to", null=True, on_delete=django.db.models.deletion.CASCADE, to="organizations.organization")),
            ],
            options={
                "verbose_name": "Raw Meta Webhook Event",
                "verbose_name_plural": "Raw Meta Webhook Events",
            },
        ),
        migrations.CreateModel(
            name="ProcessedProviderMessage",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, help_text="Timestamp when the record was created")),
                ("updated_at", models.DateTimeField(auto_now=True, help_text="Timestamp when the record was last updated")),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, help_text="Unique identifier for this record", primary_key=True, serialize=False)),
                ("deleted_at", models.DateTimeField(blank=True, help_text="Timestamp when the record was soft deleted", null=True)),
                ("provider", models.CharField(max_length=50)),
                ("provider_message_id", models.CharField(db_index=True, max_length=255, unique=True)),
                ("correlation_id", models.UUIDField(db_index=True)),
                ("processed_at", models.DateTimeField()),
                ("organization", models.ForeignKey(blank=True, help_text="Organization this record belongs to", null=True, on_delete=django.db.models.deletion.CASCADE, to="organizations.organization")),
            ],
            options={
                "verbose_name": "Processed Provider Message",
                "verbose_name_plural": "Processed Provider Messages",
            },
        ),
        migrations.CreateModel(
            name="WhatsAppBusinessAccountConnection",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, help_text="Timestamp when the record was created")),
                ("updated_at", models.DateTimeField(auto_now=True, help_text="Timestamp when the record was last updated")),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, help_text="Unique identifier for this record", primary_key=True, serialize=False)),
                ("deleted_at", models.DateTimeField(blank=True, help_text="Timestamp when the record was soft deleted", null=True)),
                ("business_account_id", models.CharField(max_length=255)),
                ("phone_number_id", models.CharField(db_index=True, max_length=255)),
                ("display_phone_number", models.CharField(max_length=50)),
                ("webhook_verify_token", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("organization", models.ForeignKey(blank=True, help_text="Organization this record belongs to", null=True, on_delete=django.db.models.deletion.CASCADE, to="organizations.organization")),
            ],
            options={
                "verbose_name": "WhatsApp Business Account Connection",
                "verbose_name_plural": "WhatsApp Business Account Connections",
            },
        ),
        migrations.AddIndex(
            model_name="rawwebhookevent",
            index=models.Index(fields=["correlation_id"], name="meta_raw_corr_idx"),
        ),
        migrations.AddIndex(
            model_name="rawwebhookevent",
            index=models.Index(fields=["status"], name="meta_raw_status_idx"),
        ),
        migrations.AddIndex(
            model_name="rawwebhookevent",
            index=models.Index(fields=["created_at"], name="meta_raw_created_idx"),
        ),
        migrations.AddIndex(
            model_name="processedprovidermessage",
            index=models.Index(fields=["provider", "provider_message_id"], name="meta_msg_provider_idx"),
        ),
        migrations.AddIndex(
            model_name="processedprovidermessage",
            index=models.Index(fields=["correlation_id"], name="meta_msg_corr_idx"),
        ),
        migrations.AddConstraint(
            model_name="processedprovidermessage",
            constraint=models.UniqueConstraint(fields=("provider", "provider_message_id"), name="meta_unique_provider_message"),
        ),
        migrations.AddIndex(
            model_name="whatsappbusinessaccountconnection",
            index=models.Index(fields=["organization"], name="meta_conn_org_idx"),
        ),
        migrations.AddIndex(
            model_name="whatsappbusinessaccountconnection",
            index=models.Index(fields=["phone_number_id"], name="meta_conn_phone_idx"),
        ),
        migrations.AddIndex(
            model_name="whatsappbusinessaccountconnection",
            index=models.Index(fields=["organization", "phone_number_id"], name="meta_conn_org_phone_idx"),
        ),
    ]

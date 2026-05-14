# Generated manually for ConnectedAccount.

import uuid

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConnectedAccount",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="Timestamp when the record was created",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True,
                        help_text="Timestamp when the record was last modified",
                    ),
                ),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        help_text="Unique identifier for this record",
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Timestamp when the record was soft deleted",
                        null=True,
                    ),
                ),
                (
                    "provider",
                    models.CharField(
                        choices=[
                            ("whatsapp_cloud", "WhatsApp Cloud API"),
                            ("instagram", "Instagram"),
                            ("telegram", "Telegram"),
                            ("email", "Email"),
                            ("webchat", "Webchat"),
                            ("sms", "SMS"),
                            ("internal_automation", "Internal automation"),
                        ],
                        db_index=True,
                        max_length=64,
                    ),
                ),
                ("external_id", models.CharField(db_index=True, max_length=255)),
                ("display_name", models.CharField(max_length=255)),
                ("access_token", models.TextField(blank=True, default="")),
                ("refresh_token", models.TextField(blank=True, null=True)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("webhook_verify_token", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("last_sync_at", models.DateTimeField(blank=True, null=True)),
                (
                    "organization",
                    models.ForeignKey(
                        blank=True,
                        help_text="Organization this record belongs to",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "verbose_name": "Connected account",
                "verbose_name_plural": "Connected accounts",
            },
        ),
        migrations.AddIndex(
            model_name="connectedaccount",
            index=models.Index(
                fields=["organization", "provider", "is_active"],
                name="integ_conn_org_prov_act_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="connectedaccount",
            index=models.Index(
                fields=["provider", "external_id"],
                name="integ_conn_prov_ext_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="connectedaccount",
            constraint=models.UniqueConstraint(
                fields=("provider", "external_id"),
                name="integ_unique_provider_external_id",
            ),
        ),
        migrations.AddConstraint(
            model_name="connectedaccount",
            constraint=models.UniqueConstraint(
                condition=Q(is_active=True),
                fields=("webhook_verify_token",),
                name="integ_unique_active_webhook_verify_token",
            ),
        ),
    ]

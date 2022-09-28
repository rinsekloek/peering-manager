# Generated by Django 4.0.6 on 2022-08-09 12:15

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("peering", "0091_rename_config_context_to_local_context_data")]

    def move_session_enabled_to_status(apps, schema_editor):
        DirectPeeringSession = apps.get_model("peering.DirectPeeringSession")
        InternetExchangePeeringSession = apps.get_model(
            "peering.InternetExchangePeeringSession"
        )

        DirectPeeringSession.objects.using(schema_editor.connection.alias).filter(
            enabled=True
        ).update(status="enabled")
        DirectPeeringSession.objects.using(schema_editor.connection.alias).filter(
            enabled=False
        ).update(status="disabled")
        InternetExchangePeeringSession.objects.using(
            schema_editor.connection.alias
        ).filter(enabled=True).update(status="enabled")
        InternetExchangePeeringSession.objects.using(
            schema_editor.connection.alias
        ).filter(enabled=False).update(status="disabled")

    operations = [
        migrations.AddField(
            model_name="directpeeringsession",
            name="status",
            field=models.CharField(
                choices=[
                    ("enabled", "Enabled"),
                    ("maintenance", "Maintenance"),
                    ("disabled", "Disabled"),
                ],
                default="enabled",
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="internetexchangepeeringsession",
            name="status",
            field=models.CharField(
                choices=[
                    ("enabled", "Enabled"),
                    ("maintenance", "Maintenance"),
                    ("disabled", "Disabled"),
                ],
                default="enabled",
                max_length=50,
            ),
        ),
        migrations.RunPython(move_session_enabled_to_status, migrations.RunPython.noop),
        migrations.AddField(
            model_name="bgpgroup",
            name="status",
            field=models.CharField(
                choices=[
                    ("enabled", "Enabled"),
                    ("maintenance", "Maintenance"),
                    ("disabled", "Disabled"),
                ],
                default="enabled",
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="internetexchange",
            name="status",
            field=models.CharField(
                choices=[
                    ("enabled", "Enabled"),
                    ("maintenance", "Maintenance"),
                    ("disabled", "Disabled"),
                ],
                default="enabled",
                max_length=50,
            ),
        ),
    ]
# Generated by Django 1.11.4 on 2017-08-20 16:09


import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("peering", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="ConfigurationTemplate",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=128)),
                ("template", models.TextField()),
                ("updated", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AlterField(
            model_name="autonomoussystem",
            name="comment",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="internetexchange",
            name="comment",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="peeringsession",
            name="comment",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="internetexchange",
            name="configuration_template",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="peering.ConfigurationTemplate",
            ),
        ),
    ]

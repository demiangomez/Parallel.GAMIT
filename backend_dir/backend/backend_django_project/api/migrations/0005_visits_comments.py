# Generated by Django 5.0.4 on 2024-09-09 13:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_alter_campaigns_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='visits',
            name='comments',
            field=models.CharField(blank=True),
        ),
    ]
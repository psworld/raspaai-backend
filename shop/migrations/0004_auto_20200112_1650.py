# Generated by Django 2.2.8 on 2020-01-12 11:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0003_auto_20200107_1848'),
    ]

    operations = [
        migrations.AlterField(
            model_name='planqueue',
            name='order_id',
            field=models.UUIDField(blank=True, null=True, unique=True),
        ),
    ]

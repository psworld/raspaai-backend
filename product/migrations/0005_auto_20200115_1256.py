# Generated by Django 2.2.8 on 2020-01-15 07:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('product', '0004_auto_20200114_1856'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='is_food',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='brand',
            name='username',
            field=models.CharField(max_length=50, unique=True),
        ),
    ]

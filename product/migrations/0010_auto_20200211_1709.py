# Generated by Django 2.2.8 on 2020-02-11 11:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('product', '0009_auto_20200128_2159'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='thumb_overlay_text',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AlterField(
            model_name='productimage',
            name='position',
            field=models.IntegerField(default=0),
        ),
    ]

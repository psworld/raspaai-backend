# Generated by Django 2.2.8 on 2020-02-09 10:53

from django.db import migrations
import versatileimagefield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0008_shop_about'),
    ]

    operations = [
        migrations.AddField(
            model_name='popularplace',
            name='image',
            field=versatileimagefield.fields.VersatileImageField(null=True, upload_to='popular_places'),
        ),
    ]

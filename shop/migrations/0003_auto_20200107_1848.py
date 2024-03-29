# Generated by Django 2.2.8 on 2020-01-07 13:18

from django.db import migrations, models
import uuid
import versatileimagefield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0002_auto_20200107_1302'),
    ]

    operations = [
        migrations.AddField(
            model_name='planqueue',
            name='order_id',
            field=models.UUIDField(default=uuid.uuid4, unique=True),
        ),
        migrations.AlterField(
            model_name='shop',
            name='hero_image',
            field=versatileimagefield.fields.VersatileImageField(null=True, upload_to='shop_images/', verbose_name='shop hero image'),
        ),
    ]

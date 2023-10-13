# Generated by Django 2.2.8 on 2020-01-14 13:26

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('product', '0003_planqueue_order_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='is_service',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='product',
            name='brand',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to='product.Brand'),
        ),
        migrations.AlterField(
            model_name='product',
            name='mrp',
            field=models.DecimalField(blank=True, decimal_places=0, max_digits=9, null=True),
        ),
    ]

# Generated by Django 2.2.8 on 2020-01-07 07:32

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('reference_id', models.CharField(db_index=True, default='', max_length=18)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('unfulfilled', 'Unfulfilled'), ('partially fulfilled', 'Partially fulfilled'), ('fulfilled', 'Fulfilled'), ('canceled', 'Canceled')], default='unfulfilled', max_length=32)),
                ('user_email', models.EmailField(blank=True, default='', max_length=254)),
                ('user_phone', models.CharField(max_length=10)),
                ('user_full_name', models.CharField(max_length=100)),
                ('total', models.DecimalField(decimal_places=2, default=0, max_digits=9)),
                ('total_items', models.IntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='OrderItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('product_title', models.CharField(blank=True, max_length=255, null=True)),
                ('quantity', models.IntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=9)),
            ],
        ),
        migrations.CreateModel(
            name='ShopOrderLine',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('unfulfilled', 'Unfulfilled'), ('partially fulfilled', 'Partially fulfilled'), ('fulfilled', 'Fulfilled'), ('canceled', 'Canceled')], default='unfulfilled', max_length=32)),
                ('client_tracking_id', models.CharField(max_length=12)),
                ('total', models.DecimalField(blank=True, decimal_places=2, max_digits=9, null=True)),
                ('total_items', models.IntegerField(default=0)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shop_orders', to='order.Order')),
            ],
        ),
    ]

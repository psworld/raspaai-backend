# Generated by Django 3.0.3 on 2020-03-07 11:02

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0015_remove_shopapplication_status'),
        ('product', '0016_remove_measurementunit_unit'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='brandapplication',
            name='status',
        ),
        migrations.DeleteModel(
            name='ApplicationStatus',
        ),
    ]

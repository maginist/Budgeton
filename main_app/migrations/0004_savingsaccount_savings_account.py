# Generated manually for Budgeton

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('main_app', '0003_alter_category_options_alter_expense_date_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='SavingsAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='savings_accounts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': "Compte d'épargne",
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='savings',
            name='account',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='movements', to='main_app.savingsaccount'),
        ),
    ]

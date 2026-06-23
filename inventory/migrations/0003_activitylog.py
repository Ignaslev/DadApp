from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('inventory', '0002_product_excel_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('action', models.CharField(choices=[('CLIENT_CREATED', 'Client created'), ('CLIENT_UPDATED', 'Client updated'), ('PRODUCT_CREATED', 'Product created'), ('PRODUCT_UPDATED', 'Product updated'), ('PURCHASE_CREATED', 'Purchase created'), ('INVOICE_CREATED', 'Invoice created'), ('INVOICE_UPDATED', 'Invoice updated'), ('PAYMENT_RECORDED', 'Payment recorded'), ('PRODUCT_SOLD', 'Product sold')], max_length=40)),
                ('model_name', models.CharField(max_length=80)),
                ('object_id', models.CharField(max_length=80)),
                ('object_label', models.CharField(max_length=255)),
                ('message', models.CharField(max_length=500)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at', '-id'],
                'indexes': [models.Index(fields=['model_name', 'object_id', '-created_at'], name='actlog_obj_idx'), models.Index(fields=['action', '-created_at'], name='actlog_action_idx')],
            },
        ),
    ]

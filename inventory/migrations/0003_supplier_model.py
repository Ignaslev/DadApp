from django.db import migrations, models
import django.db.models.deletion
import re


def _supplier_code_from_name(name):
    raw = (name or '').strip()
    if not raw:
        return 'SUPPLIER'
    cleaned = re.sub(r'[^A-Za-z0-9]+', '_', raw.upper()).strip('_')
    return cleaned[:50] or 'SUPPLIER'


def forwards(apps, schema_editor):
    Purchase = apps.get_model('inventory', 'Purchase')
    Supplier = apps.get_model('inventory', 'Supplier')

    used_codes = set(Supplier.objects.values_list('code', flat=True))
    supplier_cache = {}

    for purchase in Purchase.objects.all():
        old_name = (purchase.supplier or '').strip() or 'Nežinomas tiekėjas'
        cache_key = old_name.lower()

        supplier = supplier_cache.get(cache_key)
        if supplier is None:
            supplier = Supplier.objects.filter(name__iexact=old_name).first()
            if supplier is None:
                base_code = _supplier_code_from_name(old_name)
                code = base_code
                suffix = 1
                while code in used_codes:
                    suffix_str = f'_{suffix}'
                    code = f"{base_code[:50 - len(suffix_str)]}{suffix_str}"
                    suffix += 1
                supplier = Supplier.objects.create(name=old_name, code=code)
                used_codes.add(code)
            supplier_cache[cache_key] = supplier

        purchase.supplier_ref_id = supplier.pk
        purchase.save(update_fields=['supplier_ref'])


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0002_product_excel_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='Supplier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('country', models.CharField(blank=True, max_length=100)),
                ('country_code', models.CharField(blank=True, max_length=10)),
                ('code', models.CharField(max_length=50, unique=True)),
                ('vat_code', models.CharField(blank=True, max_length=100)),
                ('address', models.TextField(blank=True)),
                ('contacts', models.TextField(blank=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='purchase',
            name='supplier_ref',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='purchases_temp', to='inventory.supplier'),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='purchase',
            name='supplier',
        ),
        migrations.RenameField(
            model_name='purchase',
            old_name='supplier_ref',
            new_name='supplier',
        ),
        migrations.AlterField(
            model_name='purchase',
            name='supplier',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='purchases', to='inventory.supplier'),
        ),
    ]

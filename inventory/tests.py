from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import transaction
from django.test import TestCase
from django.urls import reverse

from .forms import InvoiceLineFormSet
from .models import ActivityLog, Client, Invoice, Product, Sale
from .services import replace_invoice_lines, restock_invoice


class BusinessFlowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username='tester', password='pass')
        self.client.force_login(self.user)
        self.customer = Client.objects.create(name='Test Client', code='TEST-CLIENT')
        self.product = Product.objects.create(
            code='TEST-PROD',
            description1='Test Product',
            unit='vnt',
            quantity=Decimal('5.0000'),
            avg_cost=Decimal('10.000000'),
            sale_price=Decimal('15.0000'),
        )

    def invoice_payload(self, quantity='2'):
        return {
            'number': 'TEST-INV-001',
            'client': str(self.customer.pk),
            'date': '2026-06-23',
            'due_date': '',
            'invoice_type': 'PVM',
            'language': 'LT',
            'notes': '',
            'seller_name': 'UAB "TEKILA PLIUS"',
            'seller_address': 'Justiniskiu g. 144B-41, LT05268 Vilnius',
            'seller_code': '300106323',
            'seller_vat': 'LT100001696415',
            'seller_bank': 'LT35 7044 0600 0800 4199',
            'seller_email': 'info@tequila.lt',
            'lines-TOTAL_FORMS': '1',
            'lines-INITIAL_FORMS': '0',
            'lines-MIN_NUM_FORMS': '1',
            'lines-MAX_NUM_FORMS': '1000',
            'lines-0-product': str(self.product.pk),
            'lines-0-description': 'Test Product',
            'lines-0-unit': 'vnt',
            'lines-0-quantity': quantity,
            'lines-0-unit_price': '15',
            'lines-0-vat_rate': '21',
            'lines-0-weight_kg': '0',
        }

    def test_invoice_reduces_stock_and_writes_activity(self):
        response = self.client.post(reverse('invoice_create'), self.invoice_payload())
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, Decimal('3.0000'))
        invoice = Invoice.objects.get(number='TEST-INV-001')
        self.assertEqual(Sale.objects.filter(invoice=invoice).count(), 1)
        self.assertTrue(ActivityLog.objects.filter(action='INVOICE_CREATED', object_id=str(invoice.pk)).exists())

    def test_oversell_is_blocked_and_stock_rolls_back(self):
        self.client.post(reverse('invoice_create'), self.invoice_payload())
        invoice = Invoice.objects.get(number='TEST-INV-001')
        line = invoice.lines.get()
        payload = self.invoice_payload(quantity='10')
        payload['lines-INITIAL_FORMS'] = '1'
        payload['lines-0-id'] = str(line.pk)
        formset = InvoiceLineFormSet(payload, instance=invoice)
        self.assertTrue(formset.is_valid())

        with self.assertRaises(ValidationError):
            with transaction.atomic():
                restock_invoice(invoice)
                replace_invoice_lines(invoice, formset)

        self.product.refresh_from_db()
        line.refresh_from_db()
        self.assertEqual(self.product.quantity, Decimal('3.0000'))
        self.assertEqual(line.quantity, Decimal('2.0000'))

    def test_payment_updates_status_and_writes_activity(self):
        self.client.post(reverse('invoice_create'), self.invoice_payload())
        invoice = Invoice.objects.get(number='TEST-INV-001')
        response = self.client.post(reverse('payment_create', args=[invoice.pk]), {
            'date': '2026-06-23',
            'amount': '10.00',
            'method': 'TRANSFER',
            'notes': '',
        })
        self.assertEqual(response.status_code, 302)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'PARTIAL')
        self.assertTrue(ActivityLog.objects.filter(action='PAYMENT_RECORDED', object_id=str(invoice.pk)).exists())


class BackupCommandTests(TestCase):
    def test_backup_db_creates_file(self):
        with TemporaryDirectory() as tmpdir:
            call_command('backup_db', output=tmpdir, keep=5, verbosity=0)
            backups = list(Path(tmpdir).glob('db-*.sqlite3'))
        self.assertEqual(len(backups), 1)

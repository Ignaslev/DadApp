from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import ValidationError

from .models import InvoiceLine, Product, Sale


class InvoiceStockError(ValidationError):
    pass


def _normalize_line_specs(formset):
    line_specs = []
    for form in formset.forms:
        if not hasattr(form, 'cleaned_data'):
            continue
        cleaned = form.cleaned_data
        if not cleaned or cleaned.get('DELETE'):
            continue
        product = cleaned.get('product')
        description = cleaned.get('description') or (product.description1 if product else '—')
        quantity = cleaned.get('quantity') or Decimal('0')
        unit_price = cleaned.get('unit_price') or Decimal('0')
        vat_rate = cleaned.get('vat_rate') or Decimal('0')
        weight_kg = cleaned.get('weight_kg') or Decimal('0')
        unit = cleaned.get('unit') or (product.unit if product else 'vnt')

        if not description and not product:
            continue

        line_specs.append({
            'product': product,
            'description': description,
            'unit': unit,
            'quantity': quantity,
            'unit_price': unit_price,
            'vat_rate': vat_rate,
            'weight_kg': weight_kg,
        })
    return line_specs


def validate_invoice_stock(line_specs):
    requested = defaultdict(Decimal)
    products = {}

    for spec in line_specs:
        product = spec['product']
        quantity = spec['quantity']
        if quantity < 0:
            raise InvoiceStockError('Invoice line quantity cannot be negative.')
        if product and quantity > 0:
            requested[product.pk] += quantity
            products[product.pk] = product

    errors = []
    for product_id, qty in requested.items():
        product = products[product_id]
        if qty > product.quantity:
            errors.append(
                f'{product.code}: requested {qty}, available {product.quantity}'
            )

    if errors:
        raise InvoiceStockError('Insufficient stock for: ' + '; '.join(errors))


def restock_invoice(invoice):
    for line in invoice.lines.select_related('product'):
        if line.product and line.quantity > 0:
            line.product.increase_stock(line.quantity)


def replace_invoice_lines(invoice, formset):
    line_specs = _normalize_line_specs(formset)

    # ModelChoiceField instances are loaded before edit-time restocking happens.
    # Replace them with one fresh shared object per product so stock changes are
    # based on the current database quantity and accumulate across duplicate lines.
    product_ids = {
        spec['product'].pk
        for spec in line_specs
        if spec['product']
    }
    products = Product.objects.in_bulk(product_ids)
    for spec in line_specs:
        if spec['product']:
            spec['product'] = products[spec['product'].pk]

    validate_invoice_stock(line_specs)

    invoice.sales.all().delete()
    invoice.lines.all().delete()

    for line_number, spec in enumerate(line_specs, start=1):
        product = spec['product']
        line = InvoiceLine.objects.create(
            invoice=invoice,
            line_number=line_number,
            product=product,
            description=spec['description'],
            unit=spec['unit'],
            quantity=spec['quantity'],
            unit_price=spec['unit_price'],
            vat_rate=spec['vat_rate'],
            weight_kg=spec['weight_kg'],
        )
        if product and spec['quantity'] > 0:
            product.reduce_stock(spec['quantity'])
            Sale.objects.create(
                invoice=invoice,
                invoice_line=line,
                product=product,
                date=invoice.date,
                client=invoice.client,
                quantity=spec['quantity'],
                unit_price=spec['unit_price'],
                cost_price=product.avg_cost,
            )

    invoice.update_status()
    return invoice

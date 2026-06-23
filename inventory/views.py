from decimal import Decimal
import datetime
import json
import logging

from django.utils.text import slugify
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from .forms import (
    ClientForm,
    SupplierForm,
    InvoiceForm,
    InvoiceLineFormSet,
    PaymentForm,
    ProductForm,
    PurchaseForm,
)
from .models import ActivityLog, Client, Supplier, Invoice, Payment, Product, Purchase, Sale
from .services import replace_invoice_lines, restock_invoice

logger = logging.getLogger(__name__)


def log_activity(request, action, obj, message):
    user = request.user if getattr(request.user, 'is_authenticated', False) else None
    ActivityLog.objects.create(
        user=user,
        action=action,
        model_name=obj.__class__.__name__,
        object_id=str(obj.pk),
        object_label=str(obj)[:255],
        message=message[:500],
    )


@login_required
def dashboard(request):
    now = timezone.now().date()
    invoices = Invoice.objects.all()

    total_clients = Client.objects.count()
    total_products = Product.objects.count()
    low_stock = Product.objects.filter(quantity__lt=10, quantity__gt=0).count()
    out_of_stock = Product.objects.filter(quantity__lte=0).count()

    this_month = invoices.filter(date__month=now.month, date__year=now.year)
    monthly_revenue = sum(inv.total_with_vat for inv in this_month)

    outstanding = [inv for inv in invoices.filter(status__in=['ISSUED', 'PARTIAL', 'OVERDUE'])]
    total_outstanding = sum(inv.balance for inv in outstanding)
    overdue_count = invoices.filter(status='OVERDUE').count()

    recent_invoices = invoices.select_related('client')[:8]
    recent_purchases = Purchase.objects.select_related('product', 'supplier').order_by('-created_at')[:5]
    products = Product.objects.all()
    total_stock_value = sum(p.stock_value for p in products)

    chart_data = []
    for i in range(5, -1, -1):
        month_date = timezone.now().date().replace(day=1)
        year = month_date.year
        month = month_date.month - i
        while month <= 0:
            month += 12
            year -= 1
        month_invoices = invoices.filter(date__month=month, date__year=year)
        revenue = sum(inv.total_with_vat for inv in month_invoices)
        chart_data.append({
            'month': datetime.date(year, month, 1).strftime('%b %Y'),
            'revenue': float(revenue),
        })

    context = {
        'total_clients': total_clients,
        'total_products': total_products,
        'low_stock': low_stock,
        'out_of_stock': out_of_stock,
        'monthly_revenue': monthly_revenue,
        'total_outstanding': total_outstanding,
        'overdue_count': overdue_count,
        'recent_invoices': recent_invoices,
        'recent_purchases': recent_purchases,
        'total_stock_value': total_stock_value,
        'chart_data': json.dumps(chart_data),
    }
    return render(request, 'inventory/dashboard.html', context)


@login_required
def client_list(request):
    q = request.GET.get('q', '')
    clients = Client.objects.all()
    if q:
        clients = clients.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(country__icontains=q))
    return render(request, 'inventory/client_list.html', {'clients': clients, 'q': q})


@login_required
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    invoices = client.invoices.all().order_by('-date')
    return render(request, 'inventory/client_detail.html', {'client': client, 'invoices': invoices})


@login_required
def client_create(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            log_activity(request, 'CLIENT_CREATED', client, f'Client {client.name} created.')
            messages.success(request, f'Client "{client.name}" created.')
            return redirect('client_detail', pk=client.pk)
    else:
        form = ClientForm()
    return render(request, 'inventory/client_form.html', {'form': form, 'title': 'New Client'})


@login_required
def client_edit(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            client = form.save()
            log_activity(request, 'CLIENT_UPDATED', client, f'Client {client.name} updated.')
            messages.success(request, 'Client updated.')
            return redirect('client_detail', pk=client.pk)
    else:
        form = ClientForm(instance=client)
    return render(request, 'inventory/client_form.html', {'form': form, 'title': f'Edit {client.name}', 'client': client})


@login_required
def supplier_list(request):
    q = request.GET.get('q', '')
    suppliers = Supplier.objects.all()
    if q:
        suppliers = suppliers.filter(
            Q(name__icontains=q) | Q(code__icontains=q) | Q(country__icontains=q) | Q(vat_code__icontains=q)
        )
    return render(request, 'inventory/supplier_list.html', {'suppliers': suppliers, 'q': q})


@login_required
def supplier_detail(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    purchases = supplier.purchases.select_related('product').order_by('-invoice_date', '-id')[:50]
    total_purchased = sum(p.total_incl_vat for p in supplier.purchases.all())
    return render(request, 'inventory/supplier_detail.html', {
        'supplier': supplier,
        'purchases': purchases,
        'total_purchased': total_purchased,
    })


@login_required
def supplier_create(request):
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save()
            messages.success(request, f'Supplier "{supplier.name}" created.')
            return redirect('supplier_detail', pk=supplier.pk)
    else:
        form = SupplierForm()
    return render(request, 'inventory/supplier_form.html', {'form': form, 'title': 'New Supplier'})


@login_required
def supplier_edit(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, 'Supplier updated.')
            return redirect('supplier_detail', pk=supplier.pk)
    else:
        form = SupplierForm(instance=supplier)
    return render(request, 'inventory/supplier_form.html', {
        'form': form,
        'title': f'Edit {supplier.name}',
        'supplier': supplier,
    })


@login_required
def product_list(request):
    q = request.GET.get('q', '')
    ptype = request.GET.get('type', '')
    products = Product.objects.all()
    if q:
        products = products.filter(
            Q(code__icontains=q) | Q(description1__icontains=q) | Q(description2__icontains=q)
        )
    if ptype:
        products = products.filter(product_type=ptype)
    return render(request, 'inventory/product_list.html', {
        'products': products,
        'q': q,
        'ptype': ptype,
        'product_types': Product.PRODUCT_TYPES,
    })


@login_required
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    purchases = product.purchases.select_related('supplier').order_by('-invoice_date')[:10]
    return render(request, 'inventory/product_detail.html', {
        'product': product,
        'purchases': purchases,
    })


@login_required
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            log_activity(request, 'PRODUCT_CREATED', product, f'Product {product.code} created.')
            messages.success(request, f'Product "{product.code}" created.')
            return redirect('product_detail', pk=product.pk)
    else:
        form = ProductForm()
    return render(request, 'inventory/product_form.html', {'form': form, 'title': 'New Product'})


@login_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            product = form.save()
            log_activity(request, 'PRODUCT_UPDATED', product, f'Product {product.code} updated.')
            messages.success(request, 'Product updated.')
            return redirect('product_detail', pk=product.pk)
    else:
        form = ProductForm(instance=product)
    return render(request, 'inventory/product_form.html', {
        'form': form,
        'title': f'Edit {product.code}',
        'product': product,
    })


@login_required
def purchase_list(request):
    q = request.GET.get('q', '')
    purchases = Purchase.objects.select_related('product', 'supplier').order_by('-invoice_date', '-id')
    if q:
        purchases = purchases.filter(
            Q(invoice_number__icontains=q)
            | Q(supplier__name__icontains=q)
            | Q(supplier__code__icontains=q)
            | Q(description__icontains=q)
        )
    return render(request, 'inventory/purchase_list.html', {'purchases': purchases, 'q': q})


@login_required
def purchase_create(request):
    if request.method == 'POST':
        form = PurchaseForm(request.POST)
        if form.is_valid():
            purchase = form.save()
            log_activity(request, 'PURCHASE_CREATED', purchase, f'Purchase {purchase.invoice_number} recorded.')
            messages.success(request, f'Purchase "{purchase.invoice_number}" recorded. Stock updated.')
            return redirect('purchase_list')
    else:
        form = PurchaseForm()
    return render(request, 'inventory/purchase_form.html', {'form': form, 'title': 'New Purchase'})


@login_required
def purchase_detail(request, pk):
    purchase = get_object_or_404(Purchase.objects.select_related('supplier', 'product'), pk=pk)
    return render(request, 'inventory/purchase_detail.html', {'purchase': purchase})


@login_required
def invoice_list(request):
    q = request.GET.get('q', '')
    status = request.GET.get('status', '')
    invoices = Invoice.objects.select_related('client').order_by('-date', '-id')
    if q:
        invoices = invoices.filter(Q(number__icontains=q) | Q(client__name__icontains=q))
    if status:
        invoices = invoices.filter(status=status)
    return render(request, 'inventory/invoice_list.html', {
        'invoices': invoices,
        'q': q,
        'status': status,
        'status_choices': Invoice.STATUS_CHOICES,
    })


@login_required
def invoice_create(request):
    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        formset = InvoiceLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    invoice = form.save(commit=False)
                    invoice.status = 'ISSUED'
                    invoice.save()
                    replace_invoice_lines(invoice, formset)
                    log_activity(request, 'INVOICE_CREATED', invoice, f'Invoice {invoice.number} created.')
                messages.success(request, f'Invoice {invoice.number} created.')
                return redirect('invoice_detail', pk=invoice.pk)
            except ValidationError as exc:
                form.add_error(None, exc)
    else:
        form = InvoiceForm()
        formset = InvoiceLineFormSet()
    return render(request, 'inventory/invoice_form.html', {
        'form': form,
        'formset': formset,
        'title': 'New Invoice',
    })


@login_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    payment_form = PaymentForm(initial={'date': timezone.now().date(), 'amount': invoice.balance})
    return render(request, 'inventory/invoice_detail.html', {
        'invoice': invoice,
        'payment_form': payment_form,
    })


@login_required
def invoice_edit(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice)
        formset = InvoiceLineFormSet(request.POST, instance=invoice)
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    invoice = form.save()
                    restock_invoice(invoice)
                    replace_invoice_lines(invoice, formset)
                    log_activity(request, 'INVOICE_UPDATED', invoice, f'Invoice {invoice.number} updated.')
                messages.success(request, 'Invoice updated. Stock and sales were resynchronized.')
                return redirect('invoice_detail', pk=invoice.pk)
            except ValidationError as exc:
                form.add_error(None, exc)
    else:
        form = InvoiceForm(instance=invoice)
        formset = InvoiceLineFormSet(instance=invoice)
    return render(request, 'inventory/invoice_form.html', {
        'form': form,
        'formset': formset,
        'title': f'Edit Invoice {invoice.number}',
        'invoice': invoice,
    })


@login_required
def invoice_pdf(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    html = render_to_string(
        'inventory/invoice_pdf.html',
        {'invoice': invoice, 'request': request},
    )

    safe_number = slugify(invoice.number) or f"invoice-{invoice.pk}"
    filename = f"{safe_number}.pdf"

    try:
        from weasyprint import HTML

        pdf = HTML(
            string=html,
            base_url=request.build_absolute_uri('/'),
        ).write_pdf()

        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
    except ImportError:
        messages.error(request, 'WeasyPrint is not installed.')
        return redirect('invoice_detail', pk=pk)

    except OSError:
        logger.exception("PDF native dependency failure for invoice %s", invoice.pk)
        messages.error(
            request,
            'PDF generation is unavailable. WeasyPrint or its native libraries are missing.',
        )
        return redirect('invoice_detail', pk=pk)

    except Exception as exc:
        logger.exception("Failed to generate PDF for invoice %s", invoice.pk)
        messages.error(request, f'Nepavyko sugeneruoti PDF: {exc}')
        return redirect('invoice_detail', pk=pk)


@login_required
def payment_create(request, invoice_pk):
    invoice = get_object_or_404(Invoice, pk=invoice_pk)
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.invoice = invoice
            payment.save()
            log_activity(request, 'PAYMENT_RECORDED', invoice, f'Payment of {payment.amount} recorded for invoice {invoice.number}.')
            messages.success(request, f'Payment of €{payment.amount} recorded.')
            return redirect('invoice_detail', pk=invoice.pk)
    return redirect('invoice_detail', pk=invoice.pk)


@login_required
def payment_list(request):
    payments = Payment.objects.select_related('invoice', 'invoice__client').order_by('-date')
    return render(request, 'inventory/payment_list.html', {'payments': payments})


@login_required
def product_api(request):
    code = request.GET.get('code', '').strip()

    try:
        p = Product.objects.get(code=code)
        return HttpResponse(json.dumps({
            'code': p.code,
            'description': p.description1,
            'unit': p.unit,
            'price': float(p.sale_price),
            'cost': float(p.avg_cost),
            'quantity': float(p.quantity),
            'weight': float(p.weight_kg),
            'package_code': p.package_code or '',
        }), content_type='application/json')
    except Product.DoesNotExist:
        return HttpResponse('{}', content_type='application/json')


@login_required
def reports(request):
    year = int(request.GET.get('year', datetime.date.today().year))
    sales = Sale.objects.filter(date__year=year).select_related('product', 'client')

    sale_years = [date.year for date in Sale.objects.dates('date', 'year')]
    available_years = sorted(set(sale_years + [year, timezone.now().year]), reverse=True)

    monthly = {}
    for s in sales:
        m = s.date.month
        if m not in monthly:
            monthly[m] = {'revenue': Decimal(0), 'cost': Decimal(0), 'profit': Decimal(0)}
        monthly[m]['revenue'] += s.revenue
        monthly[m]['cost'] += s.cost
        monthly[m]['profit'] += s.profit

    monthly_data = []
    chart_data = []
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    for i in range(1, 13):
        data = monthly.get(i, {'revenue': Decimal(0), 'cost': Decimal(0), 'profit': Decimal(0)})
        monthly_data.append({
            'month': month_names[i - 1],
            'revenue': data['revenue'],
            'cost': data['cost'],
            'profit': data['profit'],
        })
        chart_data.append({
            'month': month_names[i - 1],
            'revenue': float(data['revenue']),
            'profit': float(data['profit']),
        })

    client_totals = {}
    product_totals = {}
    product_revenue_totals = {}
    total_revenue = Decimal(0)
    total_cost = Decimal(0)
    total_profit = Decimal(0)
    for sale in sales:
        total_revenue += sale.revenue
        total_cost += sale.cost
        total_profit += sale.profit
        client_totals[sale.client.name] = client_totals.get(sale.client.name, Decimal(0)) + sale.revenue
        if sale.product:
            product_totals[sale.product.code] = product_totals.get(sale.product.code, Decimal(0)) + sale.quantity
            product_revenue_totals[sale.product.code] = product_revenue_totals.get(sale.product.code, Decimal(0)) + sale.revenue

    top_clients = sorted(
        ({'client__name': name, 'revenue': value} for name, value in client_totals.items()),
        key=lambda item: item['revenue'],
        reverse=True,
    )[:10]
    top_products = sorted(
        (
            {'product__code': code, 'quantity': qty, 'revenue': product_revenue_totals.get(code, Decimal(0))}
            for code, qty in product_totals.items()
        ),
        key=lambda item: item['revenue'],
        reverse=True,
    )[:10]

    available_years = list(range(2020, datetime.date.today().year + 1))

    return render(request, 'inventory/reports.html', {
        'year': year,
        'available_years': available_years,
        'monthly_data': monthly_data,
        'top_clients': top_clients,
        'top_products': top_products,
        'total_revenue': total_revenue,
        'total_cost': total_cost,
        'total_profit': total_profit,
        'chart_data': json.dumps(chart_data),
        'available_years': available_years,
    })

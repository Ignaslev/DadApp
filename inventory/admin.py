from django.contrib import admin
from .models import Client, Product, Purchase, Invoice, InvoiceLine, Sale, Payment


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'country', 'vat_code']
    search_fields = ['name', 'code', 'vat_code']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['code', 'description1', 'product_type', 'quantity', 'unit', 'avg_cost', 'sale_price']
    search_fields = ['code', 'description1']
    list_filter = ['product_type']


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'invoice_date', 'supplier', 'description', 'quantity', 'unit_price']
    search_fields = ['invoice_number', 'supplier', 'description']
    list_filter = ['purchase_type']


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['number', 'date', 'client', 'status', 'invoice_type']
    search_fields = ['number', 'client__name']
    list_filter = ['status', 'invoice_type', 'language']
    inlines = [InvoiceLineInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'date', 'amount', 'method']
    list_filter = ['method']

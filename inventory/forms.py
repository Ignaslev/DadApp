from django import forms
from django.forms import inlineformset_factory

from .models import Client, Supplier, Product, Purchase, Invoice, InvoiceLine, Payment


def client_choice_label(client):
    return f"{client.name} — {client.code}" if client.code else client.name


def supplier_choice_label(supplier):
    return f"{supplier.name} — {supplier.code}" if supplier.code else supplier.name


def product_choice_label(product):
    return f"{product.code} — {product.description1}" if product.description1 else product.code


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['name', 'country', 'country_code', 'code', 'vat_code', 'address', 'contacts', 'notes']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
            'contacts': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'country', 'country_code', 'code', 'vat_code', 'address', 'contacts', 'notes']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
            'contacts': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['code', 'product_type', 'description1', 'description2', 'description3',
                  'description4', 'unit', 'sale_price', 'weight_kg', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class PurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = ['invoice_number', 'invoice_date', 'due_date', 'supplier', 'purchase_type',
                  'product', 'description', 'unit', 'quantity', 'unit_price', 'vat_rate', 'notes']
        widgets = {
            'invoice_date': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supplier'].queryset = Supplier.objects.order_by('name')
        self.fields['supplier'].empty_label = '— Pasirinkite tiekėją —'
        self.fields['supplier'].label_from_instance = supplier_choice_label

        self.fields['product'].queryset = Product.objects.order_by('code', 'description1')
        self.fields['product'].empty_label = '— Pasirinkite prekę (nebūtina) —'
        self.fields['product'].required = False
        self.fields['product'].label_from_instance = product_choice_label


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['number', 'date', 'due_date', 'client', 'invoice_type', 'language', 'notes',
                  'seller_name', 'seller_address', 'seller_code', 'seller_vat', 'seller_bank', 'seller_email']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['client'].queryset = Client.objects.order_by('name')
        self.fields['client'].empty_label = '— Pasirinkite klientą —'
        self.fields['client'].label_from_instance = client_choice_label


class InvoiceLineForm(forms.ModelForm):
    class Meta:
        model = InvoiceLine
        fields = ['product', 'description', 'unit', 'quantity', 'unit_price', 'vat_rate', 'weight_kg']
        widgets = {
            'quantity': forms.NumberInput(attrs={'step': '0.0001', 'min': '0'}),
            'unit_price': forms.NumberInput(attrs={'step': '0.000001', 'min': '0'}),
            'vat_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'weight_kg': forms.NumberInput(attrs={'step': '0.0001', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.order_by('code', 'description1')
        self.fields['product'].empty_label = '— Pasirinkite prekę —'
        self.fields['product'].required = False
        self.fields['product'].label_from_instance = product_choice_label


InvoiceLineFormSet = inlineformset_factory(
    Invoice, InvoiceLine,
    form=InvoiceLineForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['date', 'amount', 'method', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class ProductStockAdjustForm(forms.Form):
    quantity = forms.DecimalField(max_digits=14, decimal_places=4, label='Adjustment quantity (+/-)')
    reason = forms.CharField(max_length=255, label='Reason')

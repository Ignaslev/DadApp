from decimal import Decimal

from django.db import models
from django.utils import timezone


class Client(models.Model):
    name = models.CharField(max_length=255)
    country = models.CharField(max_length=100, blank=True)
    country_code = models.CharField(max_length=10, blank=True)
    code = models.CharField(max_length=50, unique=True)
    vat_code = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    contacts = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_balance(self):
        total = sum(inv.total_with_vat for inv in self.invoices.all())
        paid = sum(p.amount for p in Payment.objects.filter(invoice__client=self))
        return total - paid


class Supplier(models.Model):
    name = models.CharField(max_length=255)
    country = models.CharField(max_length=100, blank=True)
    country_code = models.CharField(max_length=10, blank=True)
    code = models.CharField(max_length=50, unique=True)
    vat_code = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    contacts = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def total_purchased(self):
        return sum(p.total_incl_vat for p in self.purchases.all())


class Product(models.Model):
    PRODUCT_TYPES = [
        ('Prekės', 'Goods'),
        ('Paslaugos', 'Services'),
        ('Ilgalaikis turtas', 'Fixed Assets'),
        ('Finansinis turtas', 'Financial Assets'),
    ]

    code = models.CharField(max_length=100, unique=True)
    product_type = models.CharField(max_length=50, choices=PRODUCT_TYPES, default='Prekės')
    description1 = models.CharField(max_length=255)
    description2 = models.CharField(max_length=255, blank=True)
    description3 = models.CharField(max_length=255, blank=True)
    description4 = models.CharField(max_length=255, blank=True)
    unit = models.CharField(max_length=30, default='vnt')
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    avg_cost = models.DecimalField(max_digits=14, decimal_places=6, default=0)
    sale_price = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    weight_kg = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    sold_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    consignment_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    stock_adjustment = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    package_code = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['description1']

    def __str__(self):
        return f"{self.code} — {self.description1}"

    @property
    def stock_value(self):
        return self.quantity * self.avg_cost

    def update_avg_cost(self, new_qty, new_unit_cost):
        """Recalculate weighted average cost after a purchase and increase stock."""
        new_qty = Decimal(str(new_qty or 0))
        new_unit_cost = Decimal(str(new_unit_cost or 0))
        old_value = self.quantity * self.avg_cost
        new_value = new_qty * new_unit_cost
        total_qty = self.quantity + new_qty
        if total_qty > 0:
            self.avg_cost = (old_value + new_value) / total_qty
        self.quantity = total_qty
        self.save(update_fields=['avg_cost', 'quantity', 'updated_at'])

    def increase_stock(self, qty):
        qty = Decimal(str(qty or 0))
        self.quantity += qty
        self.save(update_fields=['quantity', 'updated_at'])

    def reduce_stock(self, qty):
        """Reduce stock after a sale. Overselling is treated as an error."""
        qty = Decimal(str(qty or 0))
        if qty < 0:
            raise ValueError('Stock reduction quantity cannot be negative.')
        if qty > self.quantity:
            raise ValueError(
                f'Insufficient stock for {self.code}. Requested {qty}, available {self.quantity}.'
            )
        self.quantity -= qty
        self.save(update_fields=['quantity', 'updated_at'])


class Purchase(models.Model):
    PURCHASE_TYPES = [
        ('Prekės', 'Goods'),
        ('Paslaugos', 'Services'),
        ('Ilgalaikis turtas', 'Fixed Assets'),
        ('Finansinis turtas', 'Financial Assets'),
    ]

    invoice_number = models.CharField(max_length=100)
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchases')
    purchase_type = models.CharField(max_length=50, choices=PURCHASE_TYPES, default='Prekės')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='purchases', null=True, blank=True)
    description = models.CharField(max_length=255)
    unit = models.CharField(max_length=30, default='vnt')
    quantity = models.DecimalField(max_digits=14, decimal_places=4)
    unit_price = models.DecimalField(max_digits=14, decimal_places=6)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=21)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-invoice_date', '-id']

    def __str__(self):
        return f"{self.invoice_number} — {self.description}"

    @property
    def total_excl_vat(self):
        return self.quantity * self.unit_price

    @property
    def vat_amount(self):
        return self.total_excl_vat * (self.vat_rate / 100)

    @property
    def total_incl_vat(self):
        return self.total_excl_vat + self.vat_amount

    def save(self, *args, skip_stock_update=False, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and self.product and not skip_stock_update:
            self.product.update_avg_cost(self.quantity, self.unit_price)


class Invoice(models.Model):
    INVOICE_TYPES = [
        ('PVM', 'VAT Invoice'),
        ('BE_PVM', 'Invoice without VAT'),
        ('ISANKSTINE', 'Proforma Invoice'),
    ]
    LANGUAGES = [
        ('LT', 'Lithuanian'),
        ('EN', 'English'),
        ('RU', 'Russian'),
    ]
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ISSUED', 'Issued'),
        ('PAID', 'Paid'),
        ('PARTIAL', 'Partially Paid'),
        ('OVERDUE', 'Overdue'),
    ]

    number = models.CharField(max_length=50, unique=True)
    date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='invoices')
    invoice_type = models.CharField(max_length=20, choices=INVOICE_TYPES, default='PVM')
    language = models.CharField(max_length=5, choices=LANGUAGES, default='LT')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    notes = models.TextField(blank=True)
    seller_name = models.CharField(max_length=255, default='UAB "TEKILA PLIUS"')
    seller_address = models.CharField(max_length=255, default='Justiniškių g. 144B-41, LT05268 Vilnius')
    seller_code = models.CharField(max_length=50, default='300106323')
    seller_vat = models.CharField(max_length=50, default='LT100001696415')
    seller_bank = models.CharField(max_length=100, default='LT35 7044 0600 0800 4199')
    seller_email = models.CharField(max_length=100, default='info@tequila.lt')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return self.number

    @property
    def total_excl_vat(self):
        return sum(line.line_total for line in self.lines.all())

    @property
    def total_vat(self):
        return sum(line.vat_amount for line in self.lines.all())

    @property
    def total_with_vat(self):
        return self.total_excl_vat + self.total_vat

    @property
    def total_paid(self):
        return sum(p.amount for p in self.payments.all())

    @property
    def total_weight(self):
        return sum(line.total_weight for line in self.lines.all())

    @property
    def balance(self):
        return self.total_with_vat - self.total_paid

    def update_status(self):
        balance = self.balance
        if balance <= 0:
            self.status = 'PAID'
        elif self.total_paid > 0:
            self.status = 'PARTIAL'
        elif self.due_date and self.due_date < timezone.now().date():
            self.status = 'OVERDUE'
        else:
            self.status = 'ISSUED'
        self.save(update_fields=['status', 'updated_at'])


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='lines')
    line_number = models.PositiveIntegerField()
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=255)
    unit = models.CharField(max_length=30, default='vnt')
    quantity = models.DecimalField(max_digits=14, decimal_places=4)
    unit_price = models.DecimalField(max_digits=14, decimal_places=6)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=21)
    weight_kg = models.DecimalField(max_digits=10, decimal_places=4, default=0)

    class Meta:
        ordering = ['line_number']

    def __str__(self):
        return f"{self.invoice.number} — Line {self.line_number}"

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    @property
    def vat_amount(self):
        return self.line_total * (self.vat_rate / 100)

    @property
    def total_with_vat(self):
        return self.line_total + self.vat_amount

    @property
    def total_weight(self):
        return self.quantity * self.weight_kg


class Sale(models.Model):
    """Links invoice lines to sales tracking (mirrors PARDAVIMAI sheet)."""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='sales')
    invoice_line = models.OneToOneField(InvoiceLine, on_delete=models.CASCADE, related_name='sale')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField()
    client = models.ForeignKey(Client, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=4)
    unit_price = models.DecimalField(max_digits=14, decimal_places=6)
    cost_price = models.DecimalField(max_digits=14, decimal_places=6, default=0)

    class Meta:
        ordering = ['-date', '-id']

    @property
    def revenue(self):
        return self.quantity * self.unit_price

    @property
    def cost(self):
        return self.quantity * self.cost_price

    @property
    def profit(self):
        return self.revenue - self.cost


class Payment(models.Model):
    PAYMENT_METHODS = [
        ('TRANSFER', 'Bank Transfer'),
        ('CASH', 'Cash'),
        ('CARD', 'Card'),
        ('OTHER', 'Other'),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='TRANSFER')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Payment {self.amount} for {self.invoice.number}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invoice.update_status()

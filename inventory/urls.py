from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # Clients
    path('clients/', views.client_list, name='client_list'),
    path('clients/new/', views.client_create, name='client_create'),
    path('clients/<int:pk>/', views.client_detail, name='client_detail'),
    path('clients/<int:pk>/edit/', views.client_edit, name='client_edit'),

    # Suppliers
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/new/', views.supplier_create, name='supplier_create'),
    path('suppliers/<int:pk>/', views.supplier_detail, name='supplier_detail'),
    path('suppliers/<int:pk>/edit/', views.supplier_edit, name='supplier_edit'),

    # Products / Warehouse
    path('warehouse/', views.product_list, name='product_list'),
    path('warehouse/new/', views.product_create, name='product_create'),
    path('warehouse/<int:pk>/', views.product_detail, name='product_detail'),
    path('warehouse/<int:pk>/edit/', views.product_edit, name='product_edit'),

    # Purchases
    path('purchases/', views.purchase_list, name='purchase_list'),
    path('purchases/new/', views.purchase_create, name='purchase_create'),
    path('purchases/<int:pk>/', views.purchase_detail, name='purchase_detail'),

    # Invoices
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/new/', views.invoice_create, name='invoice_create'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:pk>/edit/', views.invoice_edit, name='invoice_edit'),
    path('invoices/<int:pk>/pdf/', views.invoice_pdf, name='invoice_pdf'),

    # Payments
    path('invoices/<int:invoice_pk>/pay/', views.payment_create, name='payment_create'),
    path('payments/', views.payment_list, name='payment_list'),

    # API
    path('api/product/', views.product_api, name='product_api'),
    path('ataskaitos/', views.reports, name='reports'),
]

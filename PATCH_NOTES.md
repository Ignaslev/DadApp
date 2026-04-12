# Patch Notes

This package is a cleaned and improved version of the original Claude-generated project.

## Main fixes

1. Corrected `PIRKIMAI` column mapping to match the Excel workbook.
2. Preserved stock snapshot from `SANDELIS` by default to avoid double-counting history.
3. Added optional `--history-updates-stock` import mode for deliberate stock rebuilds.
4. Reworked invoice create/edit flow so stock and `Sale` rows stay synchronized.
5. Prevented silent overselling by raising a validation error when stock is insufficient.
6. Added missing migrations into the main project package.
7. Added extra product fields imported from Excel:
   - `sold_quantity`
   - `consignment_quantity`
   - `stock_adjustment`
   - `package_code`
8. Cleaned the delivered project so it can be zipped as a single coherent Django app.

## Static validation performed

- Python syntax compiled successfully for the patched Django modules.
- Excel workbook structure was re-checked against the import mapping.
- Estimated import volumes from the provided workbook under patched logic:
  - clients: 272
  - products: 293
  - purchases: 586
  - invoices: 633
  - invoice lines: 1466
  - payments: 4

## Not fully covered yet

- VBA macro behavior from the original workbook
- `KPO` workflow replication
- full pivot/report parity with `PARDAVIMU LENTELE`
- runtime browser/UI testing in this container (Django is not installed here)

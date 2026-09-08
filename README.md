# Day Close & Credit

An Odoo 17 app for shops that take cash, mobile money and card, sell on credit,
and need to know at the end of the day whether the money is actually there.

Odoo tells you your margin. It does not tell you whether the takings add up, who
owes you, or whether the day's work got done.

## The day close

Count what you are holding, per channel, against what the day's confirmed orders
say you should have. The day will not close while:

- shop tasks are unfinished
- credit was given without naming a customer
- the day is out beyond tolerance with no reason written

You can force it. Forcing is recorded with a reason and your name, and
overridden days are filterable — a shop whose days are mostly overridden is
telling you something.

## Credit becomes a real debt

Credit given at the close raises a **posted customer invoice**, so the money owed
reaches the customer's balance rather than sitting as a note. Print a signed slip
for the customer at the same time.

## True profit

Payment gateway fees, courier costs and operating expenses — the costs Odoo does
not model — turn gross margin into contribution profit on every order. Built on
Odoo's own `sale_margin`, so cost of goods, unit conversion and currency
conversion come from core rather than being recalculated.

## Receipts

Three, on an 80mm roll: sale receipt, credit slip with signature lines, and the
day-close summary.

## Requirements

- Odoo **17.0** (Community or Enterprise)
- `wkhtmltopdf` for the receipts

## Install

The module lives in a subdirectory, so point Odoo at the **repository root**:

```bash
python odoo-bin -d <database> \
  --addons-path=/path/to/odoo/addons,/path/to/odoo_neobuk \
  -i neobuk_trueprofit --stop-after-init
```

Then: **Shop Day → Day Close**, and **Sales → Configuration → Settings** for fee
rules, courier costs and the variance tolerance.

## Tests

```bash
python odoo-bin -d <database> \
  --addons-path=/path/to/odoo/addons,/path/to/odoo_neobuk \
  -i neobuk_trueprofit --test-enable --test-tags neobuk --stop-after-init
```

31 tests. They cover the blocking rules, the pro-rata allocation, and that credit
actually moves the customer's balance.

## Notes from building it

- **Order-level costs are allocated pro-rata by line value.** The largest line
  carries the rounding remainder so an order's contribution equals the sum of its
  lines; without that a pivot disagrees with the orders it came from.
- **Receipts do not use Odoo's monetary widget.** It emits `$\xa0`, and through
  the receipt paperformat wkhtmltopdf draws that non-breaking space as a stray
  glyph. `res.currency.neobuk_format()` exists for that reason.
- **`neobuk.profit.report` is a database view.** Stored computes must be flushed
  before it can see them.

## Licence

OPL-1. Copyright (c) Codzure Solutions.

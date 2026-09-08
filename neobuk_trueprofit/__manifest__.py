# -*- coding: utf-8 -*-
{
    # Odoo's vendor guidelines cap this at 25 characters and ask that it avoid
    # adjectives and the company name. Leads with the two things the store
    # does not already sell - a day close (0 apps) and credit on sale orders
    # (1 app, POS only) - rather than profit, where 462 apps compete.
    'name': 'Day Close & Credit',
    'version': '17.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Close the shop day properly: count takings against recorded sales, '
               'record credit given, clear the day\'s tasks. Payment gateway fees, '
               'courier costs and expenses turn margin into real profit.',
    'description': """
Day Close & Credit
==================

Odoo tells you your margin. It does not tell you what you actually made, and it does not tell you whether the money is in the drawer.

The day close
-------------

* Count takings per channel - cash, mobile money, card - against what the day's confirmed orders say you should hold.
* Record credit given today against a named customer, so a short till is explained rather than a mystery.
* Work through the day's shop tasks. The day will not close while any are unfinished.
* Override is allowed, but it is recorded with a reason and shows in the override report.

True profit
-----------

* Payment gateway fee rules per provider, as a percentage of the order plus a fixed amount.
* Courier cost rules per delivery method, as a flat cost or a percentage of what the customer was charged.
* Operating expenses, so net profit is a real figure rather than gross margin.
* Contribution profit on every order, grouped and filtered like any other Odoo field.

Built on Odoo's own margin
--------------------------

Cost of goods, the cost snapshot taken when a line is created, unit conversion and currency conversion all come from Odoo's standard sale margin. This module adds the costs Odoo does not model rather than recalculating the ones it does.

Tested against Odoo 17.0.

""",
    'author': 'Codzure Solutions',
    'website': 'https://github.com/mutugileo',
    'support': 'codzuresolutions@gmail.com',
    'license': 'OPL-1',
    # Comparables checked on the store 2026-09-08. The nearest functional
    # competitor is Pos Credit (CUCU) at $65.55 with 4 reviews - credit sales,
    # but POS only. Sale/POS profitability (BROWSEINFO) is $80.19 with 57
    # reviews. Payment fee handling runs $59-99, POS direct printing $231.
    #
    # $69 sits just above the credit module, which this exceeds in scope, and
    # below the reviewed profitability incumbent - which an unknown seller
    # should not price over. After Odoo's 30% that nets $48.30, so the EUR 400
    # payout threshold arrives in roughly nine sales. Worth revisiting at $99
    # once there are five or more reviews.
    'price': 69.00,
    'currency': 'USD',
    'depends': [
        'sale_margin',      # purchase_price / margin - the cost snapshot we build on
        'delivery',         # carrier_id on the order, for courier cost rules
        'payment',          # payment.provider, for gateway fee rules
        'account',
    ],
    'data': [
        'security/neobuk_security.xml',
        'security/ir.model.access.csv',
        'data/paperformat_data.xml',
        'data/fee_rule_data.xml',
        'views/fee_rule_views.xml',
        'views/shipping_rule_views.xml',
        'views/expense_views.xml',
        'views/shop_task_views.xml',
        'views/day_close_views.xml',
        'views/sale_order_views.xml',
        'views/res_config_settings_views.xml',
        'report/profit_report_views.xml',
        'report/receipt_templates.xml',
        'report/receipt_reports.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}

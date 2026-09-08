# -*- coding: utf-8 -*-
from odoo import api, fields, models


class NeobukFeeRule(models.Model):
    """What a payment provider charges the merchant to take the money.

    Odoo models the fee a customer is charged (surcharges) in several community
    modules, but nothing models the fee the *merchant* pays. That cost is the
    difference between margin and real profit, so it lives here.
    """

    _name = 'neobuk.fee.rule'
    _description = 'Payment Gateway Fee Rule'
    _order = 'sequence, id'

    name = fields.Char(
        required=True,
        help="How this appears in reports, e.g. 'M-Pesa Paybill' or 'Visa via Stripe'.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    provider_id = fields.Many2one(
        'payment.provider',
        string='Payment Provider',
        ondelete='set null',
        help="Matched automatically against the order's payment transaction. "
             "Leave empty and set a code instead for methods taken outside Odoo, "
             "such as cash or a till-side mobile money number.",
    )
    provider_code = fields.Char(
        string='Method Code',
        help="Used when there is no Odoo payment provider - for example 'cash', "
             "'mpesa' or 'cod'. Matched against the method chosen on the order.",
    )

    percent = fields.Float(
        string='Percentage Fee',
        digits=(6, 4),
        help="Percent of the fee base. Enter 2.9 for 2.9%.",
    )
    fixed = fields.Monetary(
        string='Fixed Fee',
        help="Flat amount charged per transaction, on top of the percentage.",
    )

    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        related='company_id.currency_id', readonly=True)

    _sql_constraints = [
        ('percent_positive', 'CHECK(percent >= 0)',
         'A percentage fee cannot be negative.'),
        ('fixed_positive', 'CHECK(fixed >= 0)',
         'A fixed fee cannot be negative.'),
    ]

    def compute_fee(self, base):
        """Fee charged on ``base``.

        Mirrors the original OpenCart engine: percentage of the base plus a flat
        amount. A base of zero or less pays nothing at all - not even the fixed
        part - because there was no transaction to charge for.
        """
        self.ensure_one()
        if base <= 0:
            return 0.0
        return (base * (self.percent / 100.0)) + self.fixed

    @api.model
    def _match(self, company, provider=None, code=None):
        """Find the rule for a provider or a method code, provider first."""
        domain = [('company_id', '=', company.id)]
        if provider:
            rule = self.search(domain + [('provider_id', '=', provider.id)], limit=1)
            if rule:
                return rule
        if code:
            rule = self.search(domain + [('provider_code', '=ilike', code)], limit=1)
            if rule:
                return rule
        return self.browse()

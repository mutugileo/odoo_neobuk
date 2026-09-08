# -*- coding: utf-8 -*-
from odoo import api, fields, models


class NeobukExpense(models.Model):
    """Shop overheads - rent, airtime, transport, wages.

    These never touch an order, so they cannot reduce contribution profit. They
    sit below it: contribution pays for them, and what survives is net profit.
    """

    _name = 'neobuk.expense'
    _description = 'Operating Expense'
    _order = 'date desc, id desc'

    name = fields.Char(string='Description', required=True)
    category = fields.Selection(
        [('advertising', 'Advertising'),
         ('packaging', 'Packaging'),
         ('transport', 'Transport'),
         ('rent', 'Rent & Utilities'),
         ('wages', 'Wages'),
         ('software', 'Software'),
         ('operations', 'Operations'),
         ('other', 'Other')],
        default='operations', required=True, index=True,
    )
    amount = fields.Monetary(required=True)
    date = fields.Date(
        required=True, default=fields.Date.context_today, index=True)
    is_recurring = fields.Boolean(
        string='Recurring',
        help="Marks a standing cost such as rent. This is a label for your own "
             "filtering - it does not create future entries by itself.",
    )
    note = fields.Text()

    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        related='company_id.currency_id', readonly=True)

    _sql_constraints = [
        ('amount_positive', 'CHECK(amount >= 0)',
         'An expense cannot be negative. Record a refund as a separate entry.'),
    ]

    @api.model
    def total_for_period(self, company, date_from, date_to):
        groups = self.read_group(
            [('company_id', '=', company.id),
             ('date', '>=', date_from),
             ('date', '<=', date_to)],
            ['amount:sum'], [],
        )
        return groups[0]['amount'] if groups else 0.0

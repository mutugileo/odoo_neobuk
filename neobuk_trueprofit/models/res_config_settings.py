# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    neobuk_credit_account_id = fields.Many2one(
        'account.account',
        string='Credit Income Account',
        domain="[('account_type', '=', 'income'), ('deprecated', '=', False)]",
        help="Income account used when credit given at the day close is turned "
             "into a customer invoice. Left empty, the first income account on "
             "the chart is used - fine for a single shop, but worth setting "
             "deliberately if your chart of accounts is considered.",
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    neobuk_credit_account_id = fields.Many2one(
        related='company_id.neobuk_credit_account_id', readonly=False)

    neobuk_variance_tolerance = fields.Float(
        string='Variance Tolerance',
        config_parameter='neobuk_trueprofit.variance_tolerance',
        help="How far the day may be out before a written reason is required. "
             "Zero means any difference must be explained.",
    )
    neobuk_fee_base_untaxed = fields.Boolean(
        string='Charge Fees on Untaxed Amount',
        config_parameter='neobuk_trueprofit.fee_base_untaxed',
        help="Most providers take their percentage of the total the customer "
             "paid, tax included, which is the default. Turn this on if yours "
             "charges on the untaxed amount instead.",
    )

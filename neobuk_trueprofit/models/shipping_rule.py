# -*- coding: utf-8 -*-
from odoo import api, fields, models


class NeobukShippingRule(models.Model):
    """What the courier actually costs you, as opposed to what you charged.

    The gap between the two is usually invisible: Odoo records the delivery
    revenue on the order but never the cost of the delivery, so a shop offering
    free delivery looks like it delivered for nothing.
    """

    _name = 'neobuk.shipping.rule'
    _description = 'Courier Cost Rule'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Delivery Method',
        ondelete='cascade',
        help="The delivery method on the order this cost applies to.",
    )

    cost_percent = fields.Float(
        string='Percent of Charged',
        digits=(6, 4),
        help="Courier cost as a percentage of what the customer was charged for "
             "delivery. Takes precedence over the flat cost when both are set and "
             "the customer was actually charged something.",
    )
    default_cost = fields.Monetary(
        string='Flat Cost',
        help="What the courier charges you per delivery. Used when there is no "
             "percentage, or when delivery was free to the customer - free "
             "delivery still costs you.",
    )

    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        related='company_id.currency_id', readonly=True)

    _sql_constraints = [
        ('cost_positive', 'CHECK(default_cost >= 0)',
         'A courier cost cannot be negative.'),
        ('percent_positive', 'CHECK(cost_percent >= 0)',
         'A courier percentage cannot be negative.'),
    ]

    def compute_cost(self, delivery_revenue):
        """Actual courier cost for a delivery that earned ``delivery_revenue``.

        Percentage wins when it is set and the customer paid for delivery;
        otherwise the flat cost applies. This is deliberately the same precedence
        as the original engine, where 'free' delivery still carries a real cost.
        """
        self.ensure_one()
        if self.cost_percent > 0 and delivery_revenue > 0:
            return delivery_revenue * (self.cost_percent / 100.0)
        return self.default_cost

    @api.model
    def _match(self, company, carrier=None):
        if not carrier:
            return self.browse()
        return self.search([
            ('company_id', '=', company.id),
            ('carrier_id', '=', carrier.id),
        ], limit=1)

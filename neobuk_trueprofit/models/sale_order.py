# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ------------------------------------------------------------------
    # How the order was paid
    # ------------------------------------------------------------------
    # Core sale.order has no payment method field: providers live on
    # payment.transaction, which only exists for orders paid online. A shop
    # taking cash over the counter has no transaction at all, so this is
    # settable and merely defaults from the transaction when there is one.
    neobuk_fee_rule_id = fields.Many2one(
        'neobuk.fee.rule',
        string='Payment Method',
        compute='_compute_neobuk_fee_rule_id',
        store=True,
        readonly=False,
        help="Which gateway fee applies. Filled in automatically from the "
             "payment transaction when the order was paid online; set it "
             "yourself for counter sales.",
    )

    neobuk_payment_fee = fields.Monetary(
        string='Payment Fee',
        compute='_compute_neobuk_costs',
        store=True,
        help="What the payment provider charges you to take this money.",
    )
    neobuk_delivery_revenue = fields.Monetary(
        string='Delivery Charged',
        compute='_compute_neobuk_costs',
        store=True,
        help="What the customer paid for delivery.",
    )
    neobuk_delivery_cost = fields.Monetary(
        string='Courier Cost',
        compute='_compute_neobuk_costs',
        store=True,
        help="What the delivery actually costs you.",
    )
    neobuk_delivery_margin = fields.Monetary(
        string='Delivery Margin',
        compute='_compute_neobuk_costs',
        store=True,
        help="Delivery charged less courier cost. Negative means you subsidised "
             "the delivery.",
    )

    neobuk_contribution = fields.Monetary(
        string='Contribution Profit',
        compute='_compute_neobuk_costs',
        store=True,
        help="Margin after the payment fee and the delivery shortfall. This is "
             "what the order contributes before shop overheads.",
    )
    neobuk_contribution_margin = fields.Float(
        string='Contribution Margin (%)',
        compute='_compute_neobuk_costs',
        store=True,
        group_operator='avg',
    )
    neobuk_is_loss = fields.Boolean(
        string='Loss-Making',
        compute='_compute_neobuk_costs',
        store=True,
        help="The order cost more to fulfil than it earned.",
    )

    # ------------------------------------------------------------------

    @api.depends('transaction_ids.provider_id', 'company_id')
    def _compute_neobuk_fee_rule_id(self):
        for order in self:
            # Never overwrite a rule someone picked by hand.
            if order.neobuk_fee_rule_id:
                continue
            provider = order.transaction_ids[:1].provider_id
            order.neobuk_fee_rule_id = self.env['neobuk.fee.rule']._match(
                order.company_id, provider=provider) or False

    @api.depends(
        'order_line.price_subtotal', 'order_line.margin', 'order_line.is_delivery',
        'amount_total', 'amount_untaxed', 'neobuk_fee_rule_id', 'carrier_id',
        'company_id', 'state',
    )
    def _compute_neobuk_costs(self):
        fee_base_untaxed = self.env['ir.config_parameter'].sudo().get_param(
            'neobuk_trueprofit.fee_base_untaxed', 'False') == 'True'

        for order in self:
            # Delivery revenue is whatever sits on delivery lines. `is_delivery`
            # comes from the delivery module and is the same flag core uses in
            # _compute_amount_total_without_delivery.
            delivery_revenue = sum(
                line.price_subtotal for line in order.order_line if line.is_delivery
            )

            rule = order.neobuk_fee_rule_id
            base = order.amount_untaxed if fee_base_untaxed else order.amount_total
            fee = rule.compute_fee(base) if rule else 0.0

            ship_rule = self.env['neobuk.shipping.rule']._match(
                order.company_id, carrier=order.carrier_id)
            delivery_cost = ship_rule.compute_cost(delivery_revenue) if ship_rule else 0.0

            # sale_margin already gives us revenue less cost of goods per line,
            # correctly snapshotted and currency converted. Delivery lines carry
            # no cost of goods, so they are excluded to avoid counting delivery
            # revenue as margin before its courier cost is applied.
            goods_margin = sum(
                line.margin for line in order.order_line if not line.is_delivery
            )

            delivery_margin = delivery_revenue - delivery_cost
            contribution = goods_margin - fee + delivery_margin

            order.neobuk_delivery_revenue = delivery_revenue
            order.neobuk_delivery_cost = delivery_cost
            order.neobuk_delivery_margin = delivery_margin
            order.neobuk_payment_fee = fee
            order.neobuk_contribution = contribution
            order.neobuk_contribution_margin = (
                (contribution / order.amount_untaxed * 100.0)
                if order.amount_untaxed else 0.0
            )
            order.neobuk_is_loss = contribution < 0 and order.state in ('sale', 'done')

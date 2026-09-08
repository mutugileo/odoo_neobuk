# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    neobuk_allocated_fee = fields.Monetary(
        string='Allocated Payment Fee',
        compute='_compute_neobuk_allocation',
        store=True,
        help="This line's share of the order's payment fee.",
    )
    neobuk_allocated_delivery = fields.Monetary(
        string='Allocated Delivery Margin',
        compute='_compute_neobuk_allocation',
        store=True,
        help="This line's share of the delivery margin or shortfall.",
    )
    neobuk_contribution = fields.Monetary(
        string='Line Contribution',
        compute='_compute_neobuk_allocation',
        store=True,
        help="Line margin after its share of the payment fee and delivery.",
    )

    @api.depends(
        'margin', 'price_subtotal', 'is_delivery',
        'order_id.neobuk_payment_fee', 'order_id.neobuk_delivery_margin',
        'order_id.neobuk_contribution', 'order_id.order_line.price_subtotal',
    )
    def _compute_neobuk_allocation(self):
        """Spread order-level costs across lines, weighted by line value.

        The OpenCart original divided the payment fee evenly by line count and
        put the whole delivery figure on whichever line happened to be first. On
        a 500 + 5 order that charged half the fee to the five-shilling line,
        which made per-product profitability meaningless.
        """
        cache = {}
        for line in self:
            order = line.order_id
            if order.id not in cache:
                cache[order.id] = self._neobuk_allocate(order)
            fee, delivery, contribution = cache[order.id].get(
                line.id, (0.0, 0.0, 0.0))
            line.neobuk_allocated_fee = fee
            line.neobuk_allocated_delivery = delivery
            line.neobuk_contribution = contribution

    @api.model
    def _neobuk_allocate(self, order):
        """Allocation for a whole order at once: {line_id: (fee, delivery, contribution)}.

        Done per order rather than per line because the parts have to add back to
        the whole. Rounding each line independently leaves the total a cent short,
        so a pivot of line contributions would not agree with the order figure -
        and in a module about knowing what you made, that is the kind of small
        wrongness that costs trust. The largest line carries the remainder, which
        is the ordinary accounting treatment. Ties break on the lowest id so the
        carrier does not move between recomputes.
        """
        goods = order.order_line.filtered(lambda l: not l.is_delivery)
        result = {l.id: (0.0, 0.0, 0.0) for l in order.order_line}
        if not goods:
            return result

        base = sum(goods.mapped('price_subtotal'))
        currency = order.currency_id
        rnd = currency.round if currency else (lambda v: v)

        def share(line):
            # An even split beats dividing by zero when nothing has value.
            return (line.price_subtotal / base) if base else (1.0 / len(goods))

        fees = {l.id: rnd(order.neobuk_payment_fee * share(l)) for l in goods}
        deliveries = {l.id: rnd(order.neobuk_delivery_margin * share(l)) for l in goods}

        carrier = max(goods, key=lambda l: (l.price_subtotal, -l.id))
        fees[carrier.id] += order.neobuk_payment_fee - sum(fees.values())
        deliveries[carrier.id] += order.neobuk_delivery_margin - sum(deliveries.values())

        contributions = {
            l.id: rnd(l.margin - fees[l.id] + deliveries[l.id]) for l in goods
        }
        # The same treatment for contribution itself: each line's figure is stored
        # as a rounded monetary value, so without this the sum drifts from the
        # order total by a cent.
        contributions[carrier.id] += (
            rnd(order.neobuk_contribution) - sum(contributions.values()))

        for line in goods:
            result[line.id] = (
                fees[line.id], deliveries[line.id], contributions[line.id])
        return result

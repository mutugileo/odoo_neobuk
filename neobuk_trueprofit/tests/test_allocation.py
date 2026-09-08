# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'neobuk')
class TestAllocation(TransactionCase):
    """Order-level costs spread across lines by value, not by line count.

    This is the headline fix over the OpenCart original, which divided the
    payment fee evenly by line count. On the 500 + 5 order below that put half
    the fee on the five-shilling line and made per-product profitability
    meaningless. These tests exist so it cannot regress.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Test Customer'})
        cls.rule = cls.env['neobuk.fee.rule'].create({
            'name': 'Test Card', 'provider_code': 'testcard',
            'percent': 10.0, 'fixed': 0.0,
        })
        cls.big = cls.env['product.product'].create({
            'name': 'Expensive', 'list_price': 500.0, 'standard_price': 300.0,
        })
        cls.small = cls.env['product.product'].create({
            'name': 'Cheap', 'list_price': 5.0, 'standard_price': 3.0,
        })

    def _order(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {'product_id': self.big.id, 'product_uom_qty': 1,
                        'price_unit': 500.0}),
                (0, 0, {'product_id': self.small.id, 'product_uom_qty': 1,
                        'price_unit': 5.0}),
            ],
        })
        order.neobuk_fee_rule_id = self.rule
        return order

    def test_01_fee_is_allocated_by_value_not_by_line_count(self):
        order = self._order()
        big_line = order.order_line.filtered(lambda l: l.product_id == self.big)
        small_line = order.order_line.filtered(lambda l: l.product_id == self.small)

        # An even split would give each line half the fee. Value weighting gives
        # the 500 line ~99% of it.
        self.assertGreater(big_line.neobuk_allocated_fee,
                           small_line.neobuk_allocated_fee * 50,
                           "fee was not weighted by line value")

        total = big_line.neobuk_allocated_fee + small_line.neobuk_allocated_fee
        self.assertAlmostEqual(total, order.neobuk_payment_fee, places=2,
                               msg="allocated fees must add back to the order fee")

    def test_02_allocation_is_proportional(self):
        order = self._order()
        big_line = order.order_line.filtered(lambda l: l.product_id == self.big)
        # Derived from the actual subtotals rather than the list prices: tax
        # configuration can move them, and the rule under test is the weighting,
        # not the tax setup of whichever database this runs in.
        base = sum(order.order_line.mapped('price_subtotal'))
        expected = big_line.price_subtotal / base
        share = big_line.neobuk_allocated_fee / order.neobuk_payment_fee
        self.assertAlmostEqual(share, expected, places=2)

    def test_03_line_contribution_nets_off_its_own_fee(self):
        """Holds exactly on ordinary lines.

        Not asserted on the largest line: that one absorbs the rounding
        remainder so the order total equals the sum of its lines (test 05).
        Something has to carry the odd cent, and a line being out by one is a
        better trade than a report that does not add up.
        """
        order = self._order()
        line = order.order_line.filtered(lambda l: l.product_id == self.small)
        self.assertAlmostEqual(
            line.neobuk_contribution,
            line.margin - line.neobuk_allocated_fee + line.neobuk_allocated_delivery,
            places=4)

    def test_03b_only_the_largest_line_carries_the_remainder(self):
        order = self._order()
        carrier = order.order_line.filtered(lambda l: l.product_id == self.big)
        naive = (carrier.margin - carrier.neobuk_allocated_fee
                 + carrier.neobuk_allocated_delivery)
        drift = abs(carrier.neobuk_contribution - naive)
        # At most one rounding unit of the order currency.
        self.assertLessEqual(drift, order.currency_id.rounding)

    def test_04_zero_value_order_does_not_divide_by_zero(self):
        free = self.env['product.product'].create({
            'name': 'Free Sample', 'list_price': 0.0, 'standard_price': 0.0,
        })
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {'product_id': free.id, 'product_uom_qty': 1,
                        'price_unit': 0.0}),
                (0, 0, {'product_id': free.id, 'product_uom_qty': 1,
                        'price_unit': 0.0}),
            ],
        })
        order.neobuk_fee_rule_id = self.rule
        # No exception, and an even split as the documented fallback.
        for line in order.order_line:
            self.assertEqual(line.neobuk_allocated_fee, 0.0)

    def test_05_order_contribution_matches_sum_of_lines(self):
        order = self._order()
        self.assertAlmostEqual(
            order.neobuk_contribution,
            sum(order.order_line.mapped('neobuk_contribution')),
            places=2)

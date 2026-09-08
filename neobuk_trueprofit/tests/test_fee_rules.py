# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'neobuk')
class TestFeeRules(TransactionCase):
    """The gateway fee table.

    Values ported straight from the OpenCart suite, which pinned them as the
    specification of correct behaviour.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Rule = cls.env['neobuk.fee.rule']

    def _rule(self, percent, fixed, code='x'):
        return self.Rule.create({
            'name': f'{percent}%+{fixed}',
            'provider_code': code,
            'percent': percent,
            'fixed': fixed,
        })

    def test_01_stripe(self):
        self.assertAlmostEqual(self._rule(2.9, 0.30).compute_fee(250), 7.55, places=4)

    def test_02_paypal(self):
        self.assertAlmostEqual(self._rule(3.4, 0.30).compute_fee(150), 5.40, places=4)

    def test_03_mpesa(self):
        self.assertAlmostEqual(self._rule(1.0, 0.0).compute_fee(80), 0.80, places=4)

    def test_04_cod_flat_only(self):
        self.assertAlmostEqual(self._rule(0.0, 1.50).compute_fee(45), 1.50, places=4)

    def test_05_bank_transfer_is_free(self):
        self.assertAlmostEqual(self._rule(0.0, 0.0).compute_fee(500), 0.0, places=4)

    def test_06_zero_order_pays_nothing(self):
        """Not even the fixed part - there was no transaction to charge for."""
        self.assertEqual(self._rule(2.9, 0.30).compute_fee(0), 0.0)
        self.assertEqual(self._rule(2.9, 0.30).compute_fee(-10), 0.0)

    def test_07_match_prefers_provider_over_code(self):
        provider = self.env['payment.provider'].search([], limit=1)
        if not provider:
            self.skipTest("no payment provider in this database")
        by_code = self._rule(1.0, 0.0, code='card')
        by_provider = self.Rule.create({
            'name': 'By provider', 'provider_id': provider.id,
            'percent': 5.0, 'fixed': 0.0,
        })
        found = self.Rule._match(self.env.company, provider=provider, code='card')
        self.assertEqual(found, by_provider)
        self.assertNotEqual(found, by_code)

    def test_08_match_falls_back_to_code(self):
        # Deliberately not 'mpesa' or 'card': the module ships seeded rules for
        # those, and _match would correctly return the seeded one first.
        rule = self._rule(1.0, 0.0, code='test-wallet')
        self.assertEqual(
            self.Rule._match(self.env.company, provider=None, code='test-wallet'),
            rule)

    def test_09_no_match_returns_empty(self):
        self.assertFalse(
            self.Rule._match(self.env.company, provider=None, code='nothing-here'))

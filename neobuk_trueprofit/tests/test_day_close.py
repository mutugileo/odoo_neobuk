# -*- coding: utf-8 -*-
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'neobuk')
class TestDayClose(TransactionCase):
    """The blocking rule - the part of this module that is genuinely new."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Date.context_today(cls.env.user)
        cls.partner = cls.env['res.partner'].create({'name': 'Debtor'})
        cls.Close = cls.env['neobuk.day.close']
        cls.Task = cls.env['neobuk.shop.task']

    def _close(self, **vals):
        return self.Close.create(dict({'date': self.today}, **vals))

    # --- variance ------------------------------------------------------

    def test_01_counted_total_sums_channels(self):
        day = self._close(counted_cash=100, counted_mobile=50, counted_card=25)
        self.assertEqual(day.counted_total, 175)

    def test_02_credit_explains_a_short_till(self):
        """Money missing because someone took goods on credit is not missing."""
        day = self._close(counted_cash=0)
        # No sales in this test database, so expected is zero; the point is that
        # credit moves variance in the positive direction.
        before = day.variance
        self.env['neobuk.day.close.credit'].create({
            'day_close_id': day.id, 'partner_id': self.partner.id, 'amount': 300,
        })
        day.invalidate_recordset()
        self.assertEqual(day.variance, before + 300)
        self.assertEqual(day.credit_total, 300)

    # --- blocking ------------------------------------------------------

    def test_03_unfinished_task_blocks_the_close(self):
        day = self._close()
        self.Task.create({'name': 'Bank the takings', 'date': self.today})
        day.invalidate_recordset()
        with self.assertRaises(UserError):
            day.action_close()

    def test_04_finished_task_does_not_block(self):
        # A reason is supplied because this database may already hold orders
        # dated today, which would block on variance instead and mask what this
        # test is actually about.
        day = self._close(variance_reason='Checked')
        task = self.Task.create({'name': 'Bank the takings', 'date': self.today})
        task.action_done()
        day.invalidate_recordset()
        day.action_close()
        self.assertEqual(day.state, 'closed')
        self.assertFalse(day.was_overridden)

    def test_05_unnamed_credit_blocks_the_close(self):
        """Credit without a customer is a hole, not a receivable."""
        day = self._close()
        self.env['neobuk.day.close.credit'].create({
            'day_close_id': day.id, 'amount': 300,   # no partner_id
        })
        day.invalidate_recordset()
        with self.assertRaises(UserError):
            day.action_close()

    def test_06_named_credit_does_not_block(self):
        day = self._close()
        self.env['neobuk.day.close.credit'].create({
            'day_close_id': day.id, 'partner_id': self.partner.id, 'amount': 300,
        })
        day.variance_reason = 'Credit to regular customer'
        day.invalidate_recordset()
        day.action_close()
        self.assertEqual(day.state, 'closed')

    def test_07_unexplained_variance_blocks_the_close(self):
        day = self._close(counted_cash=250)
        day.invalidate_recordset()
        self.assertNotEqual(day.variance, 0)
        with self.assertRaises(UserError):
            day.action_close()

    def test_08_explained_variance_does_not_block(self):
        day = self._close(counted_cash=250, variance_reason='Float taken for transport')
        day.invalidate_recordset()
        day.action_close()
        self.assertEqual(day.state, 'closed')

    # --- override ------------------------------------------------------

    def test_09_override_requires_a_reason(self):
        day = self._close()
        self.Task.create({'name': 'Unfinished', 'date': self.today})
        day.invalidate_recordset()
        with self.assertRaises(UserError):
            day.action_close_anyway()

    def test_10_override_is_recorded_against_a_name(self):
        day = self._close()
        self.Task.create({'name': 'Unfinished', 'date': self.today})
        day.override_reason = 'Owner travelling, will finish tomorrow'
        day.invalidate_recordset()
        day.action_close_anyway()

        self.assertEqual(day.state, 'closed')
        self.assertTrue(day.was_overridden)
        self.assertEqual(day.closed_by_id, self.env.user)
        self.assertTrue(day.closed_on)

    # --- recurring tasks ------------------------------------------------

    def test_11_recurring_tasks_are_seeded_onto_a_new_day(self):
        self.Task.create({
            'name': 'Count the stock', 'date': '2020-01-01', 'is_recurring': True,
        })
        day = self._close()
        names = day.task_ids.mapped('name')
        self.assertIn('Count the stock', names)
        # Copied as a normal task, not another template.
        copied = day.task_ids.filtered(lambda t: t.name == 'Count the stock')
        self.assertFalse(copied.is_recurring)
        self.assertEqual(copied.state, 'todo')

    def test_12_one_close_per_day_per_company(self):
        self._close()
        from psycopg2 import IntegrityError
        from odoo.tools import mute_logger
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self._close()

    # --- credit becomes a real debt --------------------------------------

    def test_13_closing_raises_an_invoice_for_credit(self):
        """The point of the whole feature: the debt must reach the books."""
        day = self._close(variance_reason='Credit given')
        credit = self.env['neobuk.day.close.credit'].create({
            'day_close_id': day.id, 'partner_id': self.partner.id,
            'amount': 760.0, 'note': 'Sugar and oil',
        })
        day.invalidate_recordset()
        day.action_close()

        self.assertTrue(credit.invoice_id, "no invoice was raised for the credit")
        self.assertEqual(credit.invoice_id.state, 'posted',
                         "a draft invoice never reaches the customer balance")
        self.assertEqual(credit.invoice_id.partner_id, self.partner)
        self.assertAlmostEqual(credit.invoice_id.amount_total, 760.0, places=2)

    def test_14_debt_moves_the_customer_balance(self):
        before = self.partner.credit
        day = self._close(variance_reason='Credit given')
        self.env['neobuk.day.close.credit'].create({
            'day_close_id': day.id, 'partner_id': self.partner.id, 'amount': 500.0,
        })
        day.invalidate_recordset()
        day.action_close()

        self.partner.invalidate_recordset()
        self.assertAlmostEqual(self.partner.credit, before + 500.0, places=2,
                               msg="the customer does not actually owe anything")

    def test_15_reclosing_does_not_double_the_debt(self):
        day = self._close(variance_reason='Credit given')
        credit = self.env['neobuk.day.close.credit'].create({
            'day_close_id': day.id, 'partner_id': self.partner.id, 'amount': 300.0,
        })
        day.invalidate_recordset()
        day.action_close()
        first = credit.invoice_id

        day.action_reopen()
        day.action_close()
        self.assertEqual(credit.invoice_id, first,
                         "reopening and closing again charged the customer twice")

    def test_16_override_close_still_raises_the_debt(self):
        day = self._close()
        self.Task.create({'name': 'Unfinished', 'date': self.today})
        credit = self.env['neobuk.day.close.credit'].create({
            'day_close_id': day.id, 'partner_id': self.partner.id, 'amount': 200.0,
        })
        day.override_reason = 'Closing early'
        day.invalidate_recordset()
        day.action_close_anyway()

        self.assertTrue(credit.invoice_id,
                        "forcing the close must not silently drop the debt")

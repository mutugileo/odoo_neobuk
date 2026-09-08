# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class NeobukDayClose(models.Model):
    """Closing the shop for the day.

    Three questions, in order:

      1. Is the money there?      counted takings against recorded sales
      2. If not, why?             credit given, named to a customer
      3. Is the work finished?    the day's shop tasks

    The day will not close while any of those is unanswered. It can be forced,
    but forcing is recorded with a reason and a name, because a pattern of
    overrides is itself the most interesting report in the module.
    """

    _name = 'neobuk.day.close'
    _description = 'Shop Day Close'
    _order = 'date desc'
    _rec_name = 'date'

    date = fields.Date(
        required=True, default=fields.Date.context_today, index=True)
    state = fields.Selection(
        [('draft', 'Open'), ('closed', 'Closed')],
        default='draft', required=True, index=True)

    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        related='company_id.currency_id', readonly=True)

    # --- what the books say -------------------------------------------------
    expected_total = fields.Monetary(
        string='Recorded Sales', compute='_compute_expected', store=True,
        help="Total of orders confirmed on this day.")
    order_count = fields.Integer(
        string='Orders', compute='_compute_expected', store=True)
    expected_fees = fields.Monetary(
        string='Expected Fees', compute='_compute_expected', store=True,
        help="What the payment providers are expected to keep.")

    # --- what is actually in hand ------------------------------------------
    counted_cash = fields.Monetary(string='Cash Counted')
    counted_mobile = fields.Monetary(string='Mobile Money Counted')
    counted_card = fields.Monetary(string='Card / Bank Counted')
    counted_total = fields.Monetary(
        string='Total Counted', compute='_compute_variance', store=True)

    # --- what legitimately explains a gap -----------------------------------
    credit_line_ids = fields.One2many(
        'neobuk.day.close.credit', 'day_close_id', string='Credit Entries')
    credit_total = fields.Monetary(
        string='Credit Given', compute='_compute_variance', store=True,
        help="Goods that left the shop today without payment.")

    variance = fields.Monetary(
        string='Variance', compute='_compute_variance', store=True,
        help="Counted, plus credit given, less recorded sales. Negative means "
             "money is missing.")
    variance_reason = fields.Text(string='Reason for Variance')

    # --- the day's work -----------------------------------------------------
    task_ids = fields.One2many(
        'neobuk.shop.task', compute='_compute_tasks', string='Tasks')
    open_task_count = fields.Integer(
        string='Unfinished Tasks', compute='_compute_tasks')

    # --- forcing it ---------------------------------------------------------
    was_overridden = fields.Boolean(string='Closed With Override', readonly=True)
    override_reason = fields.Text(
        string='Override Reason',
        help="Why the day was closed with items outstanding. Required to force "
             "a close, and kept on the record afterwards.",
    )
    closed_by_id = fields.Many2one('res.users', string='Closed By', readonly=True)
    closed_on = fields.Datetime(readonly=True)

    _sql_constraints = [
        ('date_company_uniq', 'UNIQUE(date, company_id)',
         'This day has already been opened for this company.'),
    ]

    # ------------------------------------------------------------------

    @api.depends('date', 'company_id')
    def _compute_expected(self):
        for rec in self:
            orders = self.env['sale.order'].search([
                ('company_id', '=', rec.company_id.id),
                ('state', 'in', ('sale', 'done')),
                ('date_order', '>=', f'{rec.date} 00:00:00'),
                ('date_order', '<=', f'{rec.date} 23:59:59'),
            ]) if rec.date else self.env['sale.order']
            rec.order_count = len(orders)
            rec.expected_total = sum(orders.mapped('amount_total'))
            rec.expected_fees = sum(orders.mapped('neobuk_payment_fee'))

    @api.depends('counted_cash', 'counted_mobile', 'counted_card',
                 'credit_line_ids.amount', 'expected_total')
    def _compute_variance(self):
        for rec in self:
            rec.counted_total = (
                rec.counted_cash + rec.counted_mobile + rec.counted_card)
            rec.credit_total = sum(rec.credit_line_ids.mapped('amount'))
            # Credit given is money you are owed rather than money missing, so it
            # counts towards explaining the day.
            rec.variance = (
                rec.counted_total + rec.credit_total - rec.expected_total)

    @api.depends('date', 'company_id')
    def _compute_tasks(self):
        Task = self.env['neobuk.shop.task']
        for rec in self:
            tasks = Task.search([
                ('company_id', '=', rec.company_id.id),
                ('date', '=', rec.date),
            ]) if rec.date else Task
            rec.task_ids = tasks
            rec.open_task_count = len(tasks.filtered(lambda t: t.state != 'done'))

    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._seed_recurring_tasks()
        return records

    def _seed_recurring_tasks(self):
        """Copy every-day jobs onto this day so nobody retypes them."""
        Task = self.env['neobuk.shop.task']
        for rec in self:
            templates = Task.search([
                ('company_id', '=', rec.company_id.id),
                ('is_recurring', '=', True),
                ('date', '!=', rec.date),
            ])
            seen = Task.search([
                ('company_id', '=', rec.company_id.id),
                ('date', '=', rec.date),
            ]).mapped('name')
            for template in templates:
                if template.name in seen:
                    continue
                template.copy({
                    'date': rec.date,
                    'state': 'todo',
                    'is_recurring': False,
                })
                seen.append(template.name)

    # ------------------------------------------------------------------

    def _blockers(self):
        """Everything standing between this day and a clean close."""
        self.ensure_one()
        problems = []

        if self.open_task_count:
            problems.append(_(
                "%s shop task(s) are not finished.", self.open_task_count))

        unnamed = self.credit_line_ids.filtered(lambda c: not c.partner_id)
        if unnamed:
            problems.append(_(
                "%s credit entry(ies) have no customer named. Credit without a "
                "name is not a debt you can collect.", len(unnamed)))

        tolerance = float(self.env['ir.config_parameter'].sudo().get_param(
            'neobuk_trueprofit.variance_tolerance', '0'))
        if abs(self.variance) > tolerance and not (self.variance_reason or '').strip():
            problems.append(_(
                "The day is out by %(amount)s and no reason has been given.",
                amount=self.variance))

        return problems

    def action_close(self):
        for rec in self:
            problems = rec._blockers()
            if problems:
                raise UserError(_(
                    "This day cannot be closed yet:\n\n%(problems)s\n\n"
                    "Resolve them, or use Close Anyway to record an override.",
                    problems="\n".join("- %s" % p for p in problems),
                ))
            rec._mark_closed(overridden=False)

    def action_close_anyway(self):
        """Force the close, on the record, with a reason.

        A hard block at closing time gets worked around - invented customers,
        rounded numbers - and then the data is worse than if nothing had been
        enforced. So forcing is allowed and simply recorded. A shop whose days
        are mostly overridden is telling you something, and that is a more useful
        signal than a wall nobody respects.
        """
        for rec in self:
            if not (rec.override_reason or '').strip():
                raise UserError(_(
                    "Give a reason before closing with items outstanding. "
                    "It is kept on the day for whoever reviews it later."))
            rec._mark_closed(overridden=True)

    def action_reopen(self):
        self.write({'state': 'draft'})

    def action_print_credit_slips(self):
        """One slip per debtor, for signing."""
        self.ensure_one()
        if not self.credit_line_ids:
            raise UserError(_("No credit was given on this day."))
        return self.env.ref(
            'neobuk_trueprofit.action_report_credit_slip'
        ).report_action(self.credit_line_ids)

    def _mark_closed(self, overridden):
        self.credit_line_ids._create_receivable()
        self.write({
            'state': 'closed',
            'was_overridden': overridden,
            'closed_by_id': self.env.user.id,
            'closed_on': fields.Datetime.now(),
        })

    def action_view_credit_invoices(self):
        self.ensure_one()
        invoices = self.credit_line_ids.invoice_id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Debts From This Day'),
            'res_model': 'account.move',
            'view_mode': 'list,form' if len(invoices) > 1 else 'form',
            'domain': [('id', 'in', invoices.ids)],
            'res_id': invoices.id if len(invoices) == 1 else False,
        }


class NeobukDayCloseCredit(models.Model):
    """Goods that left the shop today against a promise to pay.

    In a credit-heavy shop this is the usual reason the till is short, and the
    point of capturing it here is that an unexplained shortfall becomes a named
    receivable instead.
    """

    _name = 'neobuk.day.close.credit'
    _description = 'Credit Given'

    day_close_id = fields.Many2one(
        'neobuk.day.close', required=True, ondelete='cascade')
    partner_id = fields.Many2one(
        'res.partner', string='Customer',
        help="Who owes this. Required before the day can close.")
    amount = fields.Monetary(required=True)
    note = fields.Char()
    currency_id = fields.Many2one(
        related='day_close_id.currency_id', readonly=True)
    invoice_id = fields.Many2one(
        'account.move', string='Debt', readonly=True, copy=False,
        help="The customer invoice raised for this credit when the day closed. "
             "Until one exists the debt is only a note; this is what puts it in "
             "the customer's balance.",
    )

    def _create_receivable(self):
        """Turn signed-for credit into a real receivable.

        Without this the module prints a slip, the day balances, and Odoo's
        books know nothing: the customer's balance does not move and no ledger
        shows the debt. The whole claim - that a short till becomes a debt you
        can collect - depends on the invoice actually existing.

        Posted rather than left in draft, because only a posted move reaches the
        customer's balance, and the customer has already signed the slip.
        """
        for credit in self:
            if credit.invoice_id or not credit.partner_id or credit.amount <= 0:
                continue

            company = credit.day_close_id.company_id
            # Configured account first. Falling back to whichever income account
            # happens to sort first is a guess, so it is only a last resort and
            # the setting exists to remove the guesswork.
            # company_id, not company_ids: that became a many2many in Odoo 18
            # and this module targets 17.0.
            account = company.neobuk_credit_account_id or self.env[
                'account.account'].search([
                    ('company_id', '=', company.id),
                    ('account_type', '=', 'income'),
                    ('deprecated', '=', False),
                ], limit=1)
            if not account:
                raise UserError(_(
                    "No income account is configured for %s, so the debt cannot "
                    "be recorded. Set up a chart of accounts first.",
                    company.display_name))

            # sudo: whoever closes the day is not necessarily an accounting
            # user, but the debt still has to reach the books. Access to the
            # day close itself is what gates this.
            invoice = self.env['account.move'].sudo().create({
                'move_type': 'out_invoice',
                'partner_id': credit.partner_id.id,
                'invoice_date': credit.day_close_id.date,
                'company_id': company.id,
                'currency_id': credit.currency_id.id,
                'ref': _('Credit given %s', credit.day_close_id.date),
                'invoice_line_ids': [(0, 0, {
                    'name': credit.note or _('Goods taken on account'),
                    'quantity': 1.0,
                    'price_unit': credit.amount,
                    'account_id': account.id,
                    'tax_ids': [(5, 0, 0)],
                })],
            })
            invoice.action_post()
            credit.invoice_id = invoice.id

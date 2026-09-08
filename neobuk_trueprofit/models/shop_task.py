# -*- coding: utf-8 -*-
from odoo import api, fields, models


class NeobukShopTask(models.Model):
    """A job to be done in the shop today.

    Deliberately not project.task: that model carries nine dependencies
    (portal, rating, resource, digest and more) and its vocabulary is built for
    software teams - 'Changes Requested', 'Approved'. Deliberately not
    mail.activity either: its states are derived from the deadline, so there is
    no way to say a job is underway.

    Kept minimal on purpose. The value is not in having a task list - everyone
    has a phone - it is that the day will not close while one is unfinished.
    """

    _name = 'neobuk.shop.task'
    _description = 'Shop Task'
    _order = 'date desc, sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    date = fields.Date(
        required=True, default=fields.Date.context_today, index=True,
        help="The shop day this job belongs to.",
    )
    state = fields.Selection(
        [('todo', 'To Do'),
         ('in_progress', 'In Progress'),
         ('done', 'Done')],
        default='todo', required=True, index=True,
    )
    user_id = fields.Many2one(
        'res.users', string='Assigned To', default=lambda self: self.env.user)
    note = fields.Text()

    is_recurring = fields.Boolean(
        string='Every Day',
        help="Jobs like banking the takings or counting stock. Recurring jobs "
             "are copied onto each new day close so nobody has to retype them.",
    )

    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_reset(self):
        self.write({'state': 'todo'})

    @api.model
    def _open_for_date(self, company, date):
        """Tasks still blocking the close on this day."""
        return self.search([
            ('company_id', '=', company.id),
            ('date', '=', date),
            ('state', '!=', 'done'),
        ])

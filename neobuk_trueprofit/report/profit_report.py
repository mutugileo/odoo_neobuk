# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class NeobukProfitReport(models.Model):
    """Read-only view for pivoting profit by product, customer, salesperson or date.

    Follows the pattern of addons/sale/report/sale_report.py: a database view
    rather than a stored table, so there is nothing to refresh and nothing to go
    stale. The OpenCart original kept a daily rollup table that no code ever read;
    Odoo aggregates this live instead.
    """

    _name = 'neobuk.profit.report'
    _description = 'Profit Analysis'
    _auto = False
    _rec_name = 'date'
    _order = 'date desc'

    date = fields.Datetime(string='Order Date', readonly=True)
    order_id = fields.Many2one('sale.order', string='Order', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    user_id = fields.Many2one('res.users', string='Salesperson', readonly=True)
    team_id = fields.Many2one('crm.team', string='Sales Team', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    categ_id = fields.Many2one(
        'product.category', string='Product Category', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    state = fields.Selection(
        [('draft', 'Quotation'), ('sent', 'Quotation Sent'),
         ('sale', 'Sales Order'), ('done', 'Locked'), ('cancel', 'Cancelled')],
        string='Status', readonly=True)

    quantity = fields.Float(string='Quantity', readonly=True)
    revenue = fields.Monetary(string='Revenue', readonly=True)
    cogs = fields.Monetary(string='Cost of Goods', readonly=True)
    gross_margin = fields.Monetary(string='Gross Margin', readonly=True)
    payment_fee = fields.Monetary(string='Payment Fee', readonly=True)
    delivery_margin = fields.Monetary(string='Delivery Margin', readonly=True)
    contribution = fields.Monetary(string='Contribution Profit', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    l.id                                   AS id,
                    s.date_order                           AS date,
                    s.id                                   AS order_id,
                    s.partner_id                           AS partner_id,
                    s.user_id                              AS user_id,
                    s.team_id                              AS team_id,
                    l.product_id                           AS product_id,
                    t.categ_id                             AS categ_id,
                    s.company_id                           AS company_id,
                    s.currency_id                          AS currency_id,
                    s.state                                AS state,
                    l.product_uom_qty                      AS quantity,
                    l.price_subtotal                       AS revenue,
                    (l.purchase_price * l.product_uom_qty) AS cogs,
                    l.margin                               AS gross_margin,
                    l.neobuk_allocated_fee                 AS payment_fee,
                    l.neobuk_allocated_delivery            AS delivery_margin,
                    l.neobuk_contribution                  AS contribution
                FROM sale_order_line l
                JOIN sale_order s ON (l.order_id = s.id)
                LEFT JOIN product_product p ON (l.product_id = p.id)
                LEFT JOIN product_template t ON (p.product_tmpl_id = t.id)
                WHERE l.display_type IS NULL
                  AND COALESCE(l.is_delivery, FALSE) = FALSE
            )
        """)

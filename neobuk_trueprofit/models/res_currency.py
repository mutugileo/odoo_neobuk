# -*- coding: utf-8 -*-
from odoo import models
from odoo.tools.misc import formatLang


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    def neobuk_format(self, amount):
        """Money formatted for a receipt.

        Odoo's monetary widget emits the symbol followed by U+00A0, a
        non-breaking space: '$\\xa0<span>760.00</span>'. On the A4 reports that
        renders fine, but through the receipt paperformat wkhtmltopdf draws the
        nbsp as a stray glyph, so a customer's slip reads '$Å 760.00'. Verified
        by print - it is not the font, since swapping the whole stack to Arial
        changed nothing.

        formatLang still gives correct grouping, decimals and symbol position;
        this only replaces the space with an ordinary one.
        """
        self.ensure_one()
        return formatLang(
            self.env, amount, currency_obj=self
        ).replace(' ', ' ')

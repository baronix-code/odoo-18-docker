# Copyright 2020-23 ForgeFlow S.L.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.depends()
    @api.depends_context("so_line_info")
    def _compute_display_name(self):
        if not self.env.context.get("so_line_info", False):
            return super()._compute_display_name()
        for line in self.sudo():
            name = (
                f"[{line.order_id.name}] {line.product_id.name} - "
                f"({line.order_id.state})"
            )
            line.display_name = name

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        res["sale_line_id"] = self.id
        return res

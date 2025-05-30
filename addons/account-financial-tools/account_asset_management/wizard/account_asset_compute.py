# Copyright 2009-2018 Noviat
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountAssetCompute(models.TransientModel):
    _name = "account.asset.compute"
    _description = "Compute Assets"

    date_end = fields.Date(
        string="Date",
        required=True,
        default=fields.Date.today,
        help="All depreciation lines prior to this date will be automatically"
        " posted",
    )
    note = fields.Text()

    def asset_compute(self):
        assets = self.env["account.asset"].search([("state", "=", "open")])
        created_move_ids, error_log = assets._compute_entries(
            self.date_end, check_triggers=True
        )

        if error_log:
            module = __name__.split("addons.")[1].split(".")[0]
            result_view = self.env.ref(f"{module}.{self._table}_view_form_result")
            self.note = self.env._("Compute Assets errors") + ":\n" + error_log
            return {
                "name": self.env._("Compute Assets result"),
                "res_id": self.id,
                "view_mode": "form",
                "res_model": "account.asset.compute",
                "view_id": result_view.id,
                "target": "new",
                "type": "ir.actions.act_window",
                "context": {"asset_move_ids": created_move_ids},
            }

        return {
            "name": self.env._("Created Asset Moves"),
            "view_mode": "list,form",
            "res_model": "account.move",
            "view_id": False,
            "domain": [("id", "in", created_move_ids)],
            "type": "ir.actions.act_window",
        }

    def view_asset_moves(self):
        self.ensure_one()
        domain = [("id", "in", self.env.context.get("asset_move_ids", []))]
        return {
            "name": self.env._("Created Asset Moves"),
            "view_mode": "list,form",
            "res_model": "account.move",
            "view_id": False,
            "domain": domain,
            "type": "ir.actions.act_window",
        }

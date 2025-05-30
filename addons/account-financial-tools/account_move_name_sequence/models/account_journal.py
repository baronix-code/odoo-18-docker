# Copyright 2021 Akretion France (http://www.akretion.com/)
# Copyright 2022 Vauxoo (https://www.vauxoo.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# @author: Moisés López <moylop260@vauxoo.com>
# @author: Francisco Luna <fluna@vauxoo.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class AccountJournal(models.Model):
    _inherit = "account.journal"

    sequence_id = fields.Many2one(
        "ir.sequence",
        string="Entry Sequence",
        copy=False,
        check_company=True,
        domain="[('company_id', '=', company_id)]",
        help="This sequence will be used to generate the journal entry number.",
    )
    refund_sequence_id = fields.Many2one(
        "ir.sequence",
        string="Credit Note Entry Sequence",
        copy=False,
        check_company=True,
        domain="[('company_id', '=', company_id)]",
        help="This sequence will be used to generate the journal entry number for "
        "refunds.",
    )
    # Redefine the default to True as <=v13.0
    refund_sequence = fields.Boolean(default=True)
    # has_sequence_holes is not relevant anymore (since based on sequence_prefix/number)
    # -> compute=False to improve perf and to avoid displaying warning
    has_sequence_holes = fields.Boolean(compute=False)

    @api.constrains("refund_sequence_id", "sequence_id")
    def _check_journal_sequence(self):
        for journal in self:
            if (
                journal.refund_sequence_id
                and journal.sequence_id
                and journal.refund_sequence_id == journal.sequence_id
            ):
                raise ValidationError(
                    self.env._(
                        "On journal '%s', the same sequence is used as "
                        "Entry Sequence and Credit Note Entry Sequence.",
                        journal.display_name,
                    )
                )
            if journal.sequence_id and not journal.sequence_id.company_id:
                msg = self.env._(
                    "The company is not set on sequence '%(sequence)s' configured on "
                    "journal '%(journal)s'.",
                    sequence=journal.sequence_id.display_name,
                    journal=journal.display_name,
                )
                raise ValidationError(msg)
            if journal.refund_sequence_id and not journal.refund_sequence_id.company_id:
                msg = self.env._(
                    "The company is not set on sequence '%(sequence)s' configured as "
                    "credit note sequence of journal '%(journal)s'.",
                    sequence=journal.refund_sequence_id.display_name,
                    journal=journal.display_name,
                )
                raise ValidationError(msg)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("sequence_id"):
                vals["sequence_id"] = self._create_sequence(vals).id
            if (
                vals.get("type") in ("sale", "purchase")
                and vals.get("refund_sequence", True)
                and not vals.get("refund_sequence_id")
            ):
                vals["refund_sequence_id"] = self._create_sequence(vals, refund=True).id
        return super().create(vals_list)

    @api.model
    def _prepare_sequence(self, vals, refund=False):
        code = vals.get("code") and vals["code"].upper() or ""
        prefix = "{}{}/%(range_year)s/".format(refund and "R" or "", code)
        seq_vals = {
            "name": "{}{}".format(
                vals.get("name", self.env._("Sequence")),
                refund and " " + self.env._("Refund") or "",
            ),
            "company_id": vals.get("company_id") or self.env.company.id,
            "implementation": "no_gap",
            "prefix": prefix,
            "padding": 4,
            "use_date_range": True,
        }
        return seq_vals

    @api.model
    def _create_sequence(self, vals, refund=False):
        seq_vals = self._prepare_sequence(vals, refund=refund)
        domain = [(key, "=", value) for key, value in seq_vals.items()]
        existing = self.env["ir.sequence"].search(domain, limit=1)
        if existing:
            return existing
        return self.env["ir.sequence"].sudo().create(seq_vals)

    def _prepare_sequence_current_moves(self, refund=False):
        """Get sequence dict values the journal based on current moves"""
        self.ensure_one()
        move_domain = [
            ("journal_id", "=", self.id),
            ("name", "!=", "/"),
        ]
        if self.refund_sequence:
            #  Based on original Odoo behavior
            if refund:
                move_domain.append(("move_type", "in", ("out_refund", "in_refund")))
            else:
                move_domain.append(("move_type", "not in", ("out_refund", "in_refund")))
        last_move = self.env["account.move"].search(
            move_domain, limit=1, order="id DESC"
        )
        msg_err = (
            "Journal {} could not get sequence {} values based on current moves. "
            "Using default values.".format(self.id, refund and "refund" or "")
        )
        if not last_move:
            _logger.warning("%s %s", msg_err, "No moves found")
            return {}
        try:
            with self.env.cr.savepoint():
                # get the current sequence values could be buggy to get
                # But even we can use the default values
                # or do manual changes instead of raising errors
                last_sequence = last_move._get_last_sequence()
                if not last_sequence:
                    last_sequence = (
                        last_move._get_last_sequence(relaxed=True)
                        or last_move._get_starting_sequence()
                    )

                __, seq_format_values = last_move._get_sequence_format_param(
                    last_sequence
                )
                prefix1 = seq_format_values["prefix1"]
                prefix = prefix1
                if seq_format_values["year_length"] == 4:
                    prefix += "%(range_year)s"
                elif seq_format_values["year_length"] == 2:
                    prefix += "%(range_y)s"
                else:
                    # If there is not year so current values are valid
                    seq_vals = {
                        "padding": seq_format_values["seq_length"],
                        "suffix": seq_format_values["suffix"],
                        "prefix": prefix,
                        "date_range_ids": [],
                        "use_date_range": False,
                        "number_next_actual": seq_format_values["seq"] + 1,
                    }
                    return seq_vals
                prefix2 = seq_format_values.get("prefix2") or ""
                prefix += prefix2
                month = seq_format_values.get("month")  # It is 0 if only have year
                if month:
                    prefix += "%(range_month)s"
                prefix3 = seq_format_values.get("prefix3") or ""
                where_name_value = "{}{}{}{}{}%".format(
                    prefix1,
                    "_" * seq_format_values["year_length"],
                    prefix2,
                    "_" * bool(month) * 2,
                    prefix3,
                )
                prefixes = prefix1 + prefix2
                select_year = (
                    f"split_part(name, '{prefix2}', {prefixes.count(prefix2)})"
                    if prefix2
                    else "''"
                )
                prefixes += prefix3
                select_month = (
                    f"split_part(name, '{prefix3}', {prefixes.count(prefix3)})"
                    if prefix3
                    else "''"
                )
                select_max_number = (
                    f"MAX(split_part(name, '{prefixes[-1]}', "
                    f"{prefixes.count(prefixes[-1]) + 1}):"
                    f":INTEGER) AS max_number"
                )
                query = (
                    f"SELECT {select_year}, {select_month}, "
                    f"{select_max_number} FROM account_move "
                    f"WHERE name LIKE %s AND journal_id=%s GROUP BY 1,2"
                )

                # It is not using user input
                # pylint: disable=sql-injection
                self.env.cr.execute(query, (where_name_value, self.id))
                res = self.env.cr.fetchall()
                prefix += prefix3
                seq_vals = {
                    "padding": seq_format_values["seq_length"],
                    "suffix": seq_format_values["suffix"],
                    "prefix": prefix,
                    "date_range_ids": [],
                    "use_date_range": True,
                }
                for year, month, max_number in res:
                    if not year and not month:
                        seq_vals.update(
                            {
                                "use_date_range": False,
                                "number_next_actual": max_number + 1,
                            }
                        )
                        continue
                    if len(year) == 2:
                        # Year >=50 will be considered as last century 1950
                        # Year <=49 will be considered as current century 2049
                        if int(year) >= 50:
                            year = "19" + year
                        else:
                            year = "20" + year
                    if month:
                        date_from = fields.Date.to_date(f"{year}-{month}-1")
                        date_to = fields.Date.end_of(date_from, "month")
                    else:
                        date_from = fields.Date.to_date(f"{year}-1-1")
                        date_to = fields.Date.to_date(f"{year}-12-31")
                    seq_vals["date_range_ids"].append(
                        Command.create(
                            {
                                "date_from": date_from,
                                "date_to": date_to,
                                "number_next_actual": max_number + 1,
                            }
                        )
                    )
                return seq_vals
        except Exception as e:
            _logger.warning("%s %s", msg_err, e)
        return {}

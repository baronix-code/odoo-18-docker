from openupgradelib import openupgrade


def migrate(cr, version):
    openupgrade.logged_query(
        cr,
        """
        ALTER TABLE account_move_line
        ADD COLUMN IF NOT EXISTS oca_purchase_line_id INTEGER;
        """,
    )

    openupgrade.logged_query(
        cr,
        """
        UPDATE account_move_line
        SET oca_purchase_line_id = purchase_line_id;
        """,
    )

    openupgrade.logged_query(
        cr,
        """
        UPDATE account_move_line
        SET purchase_line_id = NULL
        FROM account_move
        WHERE account_move_line.move_id = account_move.id
            AND account_move.move_type = 'entry';
        """,
    )

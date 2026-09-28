# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
from odoo import fields, models


class LoyaltyProgram(models.Model):
    _inherit = "loyalty.program"

    reminder_line_ids = fields.One2many(
        "loyalty.program.reminder.line", "program_id", string="Reminder Lines",
        help="Default reminder lines, copied onto every new card of this program "
             "(overridable independently per card afterwards).",
    )

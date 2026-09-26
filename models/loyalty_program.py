# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
from odoo import fields, models


class LoyaltyProgram(models.Model):
    _inherit = "loyalty.program"

    reminder_line_ids = fields.One2many(
        "loyalty.program.reminder.line", "program_id", string="Reminder Lines",
        help="Lignes de rappel par défaut, copiées sur chaque nouvelle carte de ce "
             "programme (overridables ensuite indépendamment par carte).",
    )

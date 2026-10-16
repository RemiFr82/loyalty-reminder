# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
from odoo import fields, models


class LoyaltyProgramReminderLine(models.Model):
    _name = "loyalty.program.reminder.line"
    _description = "Loyalty Program Reminder Line (Default Configuration)"
    _order = "sequence, id"

    program_id = fields.Many2one(
        "loyalty.program", string="Program", required=True, ondelete="cascade",
        help="Program carrying this default reminder line.",
    )
    sequence = fields.Integer(default=10)
    trigger_type = fields.Selection(
        selection=[
            ("points_remaining", "Points Remaining"),
            ("before_expiry", "Before Expiry"),
        ],
        string="Trigger", required=True,
        help="Criterion triggering the sending: remaining points balance, or proximity "
             "of the card expiry date.",
    )
    points_remaining = fields.Integer(
        string="Points Remaining Threshold",
        help="Remaining points balance at or below which the reminder is sent. Only "
             "used by the 'Points Remaining' trigger.",
    )
    days_before = fields.Integer(
        string="Days Before Expiry",
        help="Number of days before the card expiry date "
             "(loyalty.card.expiration_date) from which the reminder is sent. Only used "
             "by the 'Before Expiry' trigger.",
    )
    mail_template_id = fields.Many2one(
        "mail.template", string="Email Template", required=True,
        domain=[("model", "=", "loyalty.card")],
        help="Template sent to the card holder when the trigger is satisfied.",
    )

# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
from odoo import fields, models


class LoyaltyProgramReminderLine(models.Model):
    _name = "loyalty.program.reminder.line"
    _description = "Loyalty Program Reminder Line (Default Configuration)"
    _order = "sequence, id"

    program_id = fields.Many2one(
        "loyalty.program", string="Program", required=True, ondelete="cascade",
        help="Programme portant cette ligne de rappel par défaut.",
    )
    sequence = fields.Integer(default=10)
    trigger_type = fields.Selection(
        selection=[
            ("points_remaining", "Points Remaining"),
            ("before_expiry", "Before Expiry"),
        ],
        string="Trigger", required=True,
        help="Critère déclenchant l'envoi : solde de points restant, ou proximité de "
             "l'échéance de la carte.",
    )
    points_remaining = fields.Integer(
        string="Points Remaining Threshold",
        help="Nombre de points restants en dessous ou à hauteur duquel le rappel est "
             "envoyé. Utilisé uniquement par le déclencheur 'Points Remaining'.",
    )
    days_before = fields.Integer(
        string="Days Before Expiry",
        help="Nombre de jours avant l'échéance de la carte (loyalty.card.expiration_date) "
             "à partir duquel le rappel est envoyé. Utilisé uniquement par le déclencheur "
             "'Before Expiry'.",
    )
    mail_template_id = fields.Many2one(
        "mail.template", string="Email Template", required=True,
        domain=[("model", "=", "loyalty.card")],
        help="Template envoyé au titulaire de la carte quand le déclencheur est satisfait.",
    )

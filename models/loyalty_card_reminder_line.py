# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
from odoo import fields, models


class LoyaltyCardReminderLine(models.Model):
    _name = "loyalty.card.reminder.line"
    _description = "Loyalty Card Reminder Line (Effective Configuration)"
    _order = "sequence, id"

    card_id = fields.Many2one(
        "loyalty.card", string="Card", required=True, ondelete="cascade",
        help="Carte portant cette ligne de rappel effective.",
    )
    sequence = fields.Integer(default=10)
    trigger_type = fields.Selection(
        selection=[
            ("points_remaining", "Points Remaining"),
            ("before_expiry", "Before Expiry"),
        ],
        string="Trigger", required=True,
    )
    points_remaining = fields.Integer(string="Points Remaining Threshold")
    days_before = fields.Integer(string="Days Before Expiry")
    mail_template_id = fields.Many2one(
        "mail.template", string="Email Template", required=True,
        domain=[("model", "=", "loyalty.card")],
    )
    active = fields.Boolean(
        default=True,
        help="Décoché automatiquement une fois le rappel envoyé (anti-doublon) — sert "
             "surtout à l'affichage, la carte et ses lignes restent conservées.",
    )

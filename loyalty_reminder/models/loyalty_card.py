# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
from dateutil.relativedelta import relativedelta

from odoo import Command, api, fields, models


class LoyaltyCard(models.Model):
    _inherit = "loyalty.card"

    reminder_line_ids = fields.One2many(
        "loyalty.card.reminder.line", "card_id", string="Reminder Lines",
        compute="_compute_reminder_line_ids", store=True, readonly=False, copy=True,
        context={"active_test": False},
        help="Effective reminder lines of the card, copied from the program at creation "
             "then overridable independently. `active_test: False` is required here: "
             "`active` is only a display status (reminder already sent), not standard "
             "Odoo archiving - without this context, the ORM silently hides the "
             "deactivated lines of this One2many (including in Python, not only in the "
             "views), which would empty `reminder_line_ids` as soon as a reminder has "
             "been sent.",
    )

    @api.depends("program_id")
    def _compute_reminder_line_ids(self):
        """Emulate an onchange at creation: copy the program's default lines onto the
        card. Analogous to `_compute_event_mail_ids` (event/models/event_event.py),
        never touches a line already overridden by the user."""
        for card in self:
            if not card.program_id or card.reminder_line_ids:
                continue
            card.reminder_line_ids = [
                Command.create({
                    "sequence": line.sequence,
                    "trigger_type": line.trigger_type,
                    "points_remaining": line.points_remaining,
                    "days_before": line.days_before,
                    "mail_template_id": line.mail_template_id.id,
                })
                for line in card.program_id.reminder_line_ids
            ]

    def _cron_send_reminders(self):
        """Daily cron - sweep the active cards and send the template of every active
        reminder line whose trigger is satisfied, with a duplicate guard through
        mail.message + deactivation of the line."""
        subtype = self.env.ref("loyalty_reminder.mt_card_reminder_sent")
        cards = self.search([
            ("points", ">", 0),
            ("partner_id", "!=", False),
            ("reminder_line_ids.active", "=", True),
        ])
        today = fields.Date.context_today(self)
        for card in cards:
            for line in card.reminder_line_ids.filtered("active"):
                if line.trigger_type == "points_remaining":
                    triggered = card.points <= line.points_remaining
                elif line.trigger_type == "before_expiry":
                    # today <= expiration_date excludes the already expired cards:
                    # without this guard, an expired card would stay eligible forever,
                    # which contradicts the spec's rule "expired cards never trigger".
                    triggered = bool(card.expiration_date) and \
                        today <= card.expiration_date and \
                        card.expiration_date - relativedelta(days=line.days_before) <= today
                else:
                    continue
                if not triggered:
                    continue
                line.mail_template_id.send_mail(
                    card.id, email_layout_xmlid="mail.mail_notification_light")
                card.message_post(
                    subtype_id=subtype.id, body=f"reminder_line_id={line.id}",
                    author_id=self.env.ref("base.partner_root").id)
                line.active = False

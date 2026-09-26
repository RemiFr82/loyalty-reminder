# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
from dateutil.relativedelta import relativedelta

from odoo import Command, api, fields, models


class LoyaltyCard(models.Model):
    _inherit = "loyalty.card"

    reminder_line_ids = fields.One2many(
        "loyalty.card.reminder.line", "card_id", string="Reminder Lines",
        compute="_compute_reminder_line_ids", store=True, readonly=False, copy=True,
        context={"active_test": False},
        help="Lignes de rappel effectives de la carte, copiées depuis le programme à la "
             "création puis overridables indépendamment. `active_test: False` est requis "
             "ici : `active` sert uniquement de statut d'affichage (rappel déjà envoyé), "
             "pas d'archivage Odoo standard — sans ce contexte, l'ORM masque "
             "silencieusement les lignes desactivées de ce One2many (y compris en Python, "
             "pas seulement dans les vues), ce qui viderait `reminder_line_ids` dès qu'un "
             "rappel a été envoyé.",
    )

    @api.depends("program_id")
    def _compute_reminder_line_ids(self):
        """Emule un onchange à la création : copie les lignes par défaut du programme
        sur la carte. Analogue à `_compute_event_mail_ids` (event/models/event_event.py),
        ne retouche jamais une ligne déjà overridée par l'utilisateur."""
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
        """Cron quotidien — balaie les cartes actives et envoie le template de chaque
        ligne de rappel active dont le déclencheur est satisfait, avec anti-doublon
        par mail.message + désactivation de la ligne."""
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
                    # today <= expiration_date exclut les cartes déjà échues : sans ce
                    # garde-fou, une carte échue resterait éligible indéfiniment, ce qui
                    # contredit la règle "cartes échues ne déclenchent jamais" de la spec.
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

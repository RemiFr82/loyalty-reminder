# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
from datetime import timedelta

from odoo.fields import Date
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestLoyaltyReminder(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Test Customer"})
        cls.other_partner = cls.env["res.partner"].create({"name": "Other Customer"})
        cls.mail_template = cls._create_template("Threshold Template")
        cls.other_mail_template = cls._create_template("Expiry Template")
        cls.program = cls.env["loyalty.program"].create({
            "name": "Test Program",
            "program_type": "loyalty",
        })

    @classmethod
    def _create_template(cls, name):
        return cls.env["mail.template"].create({
            "name": name,
            "model_id": cls.env["ir.model"]._get_id("loyalty.card"),
            "subject": "Reminder",
            "body_html": "<div>Reminder for <t t-out=\"object.code\"/></div>",
        })

    def _create_card(self, partner, points=5, expiration_date=False, program=None):
        return self.env["loyalty.card"].create({
            "program_id": (program or self.program).id,
            "partner_id": partner.id,
            "points": points,
            "expiration_date": expiration_date,
        })

    def _add_program_line(self, trigger_type, template, **extra):
        values = {
            "program_id": self.program.id,
            "trigger_type": trigger_type,
            "mail_template_id": template.id,
        }
        values.update(extra)
        return self.env["loyalty.program.reminder.line"].create(values)

    # -- Program -> card copy ------------------------------------------

    def test_reminder_lines_copied_from_program_on_card_creation(self):
        self._add_program_line("points_remaining", self.mail_template, points_remaining=1)
        card = self._create_card(self.partner)
        self.assertEqual(len(card.reminder_line_ids), 1)
        self.assertEqual(card.reminder_line_ids.trigger_type, "points_remaining")
        self.assertEqual(card.reminder_line_ids.points_remaining, 1)

    def test_card_override_does_not_impact_program_or_other_cards(self):
        self._add_program_line("points_remaining", self.mail_template, points_remaining=1)
        card_a = self._create_card(self.partner)
        card_b = self._create_card(self.other_partner)
        card_a.reminder_line_ids.points_remaining = 3
        self.assertEqual(card_a.reminder_line_ids.points_remaining, 3)
        self.assertEqual(card_b.reminder_line_ids.points_remaining, 1)
        self.assertEqual(self.program.reminder_line_ids.points_remaining, 1)

    # -- points_remaining trigger ----------------------------------------

    def test_points_remaining_triggers_at_threshold_not_before(self):
        self._add_program_line("points_remaining", self.mail_template, points_remaining=1)
        card = self._create_card(self.partner, points=2)
        card._cron_send_reminders()
        self.assertTrue(card.reminder_line_ids.active)

        card.points = 1
        card._cron_send_reminders()
        self.assertFalse(card.reminder_line_ids.active)
        self.assertTrue(self._reminder_message(card))

    def test_points_remaining_no_repeat_after_send(self):
        self._add_program_line("points_remaining", self.mail_template, points_remaining=1)
        card = self._create_card(self.partner, points=1)
        card._cron_send_reminders()
        messages_after_first = len(self._reminder_message(card))

        card._cron_send_reminders()
        self.assertEqual(len(self._reminder_message(card)), messages_after_first)

    def test_points_recredit_after_send_does_not_reset_reminder(self):
        self._add_program_line("points_remaining", self.mail_template, points_remaining=1)
        card = self._create_card(self.partner, points=1)
        card._cron_send_reminders()
        self.assertFalse(card.reminder_line_ids.active)

        card.points = 5
        card._cron_send_reminders()
        self.assertFalse(card.reminder_line_ids.active)
        self.assertEqual(len(self._reminder_message(card)), 1)

    def test_exhausted_card_never_triggers(self):
        self._add_program_line("points_remaining", self.mail_template, points_remaining=1)
        card = self._create_card(self.partner, points=0)
        card._cron_send_reminders()
        self.assertTrue(card.reminder_line_ids.active)
        self.assertFalse(self._reminder_message(card))
        self.assertTrue(card.exists())

    # -- before_expiry trigger -------------------------------------------

    def test_before_expiry_triggers_within_window(self):
        self._add_program_line("before_expiry", self.other_mail_template, days_before=5)
        today = Date.context_today(self.env["loyalty.card"])
        card = self._create_card(self.partner, expiration_date=today + timedelta(days=10))
        card._cron_send_reminders()
        self.assertTrue(card.reminder_line_ids.active)

        card.expiration_date = today + timedelta(days=5)
        card._cron_send_reminders()
        self.assertFalse(card.reminder_line_ids.active)

    def test_before_expiry_without_expiration_date_never_triggers(self):
        self._add_program_line("before_expiry", self.other_mail_template, days_before=5)
        card = self._create_card(self.partner, expiration_date=False)
        card._cron_send_reminders()
        self.assertTrue(card.reminder_line_ids.active)
        self.assertFalse(self._reminder_message(card))

    def test_expired_card_never_triggers(self):
        self._add_program_line("before_expiry", self.other_mail_template, days_before=5)
        today = Date.context_today(self.env["loyalty.card"])
        card = self._create_card(self.partner, expiration_date=today - timedelta(days=1))
        card._cron_send_reminders()
        self.assertTrue(card.reminder_line_ids.active)
        self.assertFalse(self._reminder_message(card))
        self.assertTrue(card.exists())

    def test_two_cards_same_partner_same_expiry_window_send_two_emails(self):
        self._add_program_line("before_expiry", self.other_mail_template, days_before=5)
        today = Date.context_today(self.env["loyalty.card"])
        card_a = self._create_card(self.partner, expiration_date=today + timedelta(days=1))
        card_b = self._create_card(self.partner, expiration_date=today + timedelta(days=1))
        card_a._cron_send_reminders()
        self.assertFalse(card_a.reminder_line_ids.active)
        self.assertFalse(card_b.reminder_line_ids.active)
        self.assertTrue(self._reminder_message(card_a))
        self.assertTrue(self._reminder_message(card_b))

    # -- Multiple lines ----------------------------------------------------

    def test_multiple_trigger_lines_send_independently(self):
        self._add_program_line("points_remaining", self.mail_template, points_remaining=1)
        self._add_program_line(
            "before_expiry", self.other_mail_template, days_before=5, sequence=20)
        today = Date.context_today(self.env["loyalty.card"])
        card = self._create_card(
            self.partner, points=1, expiration_date=today + timedelta(days=5))
        card._cron_send_reminders()
        self.assertFalse(card.reminder_line_ids.mapped("active")[0])
        self.assertFalse(card.reminder_line_ids.mapped("active")[1])
        self.assertEqual(len(self._reminder_message(card)), 2)

    # -- Traceability --------------------------------------------------

    def test_reminder_sent_traced_on_chatter_with_dedicated_subtype(self):
        self._add_program_line("points_remaining", self.mail_template, points_remaining=1)
        card = self._create_card(self.partner, points=1)
        card._cron_send_reminders()
        messages = self._reminder_message(card)
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            messages.subtype_id, self.env.ref("loyalty_reminder.mt_card_reminder_sent"))

    def _reminder_message(self, card):
        subtype = self.env.ref("loyalty_reminder.mt_card_reminder_sent")
        return card.message_ids.filtered(lambda m: m.subtype_id == subtype)

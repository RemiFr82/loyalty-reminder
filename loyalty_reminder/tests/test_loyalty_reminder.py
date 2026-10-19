# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
from datetime import timedelta

from odoo.exceptions import AccessError
from odoo.fields import Date
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged("post_install", "-at_install")
class TestLoyaltyReminder(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # `_cron_send_reminders` sweeps the whole database (`self.search([...])` ignores
        # `self`), so every reminder line already in base -- starting with the ones this
        # very module ships as demo data -- would be evaluated by every cron call below.
        # The state of those lines is captured first, because the demo set is asserted
        # from it, then they are switched off so no assertion of this suite depends on
        # whether demo data is loaded. The cron itself must stay global:
        # `test_two_cards_same_partner_same_expiry_window_send_two_emails` relies on it.
        pre_existing = cls.env["loyalty.card.reminder.line"].with_context(
            active_test=False).search([])
        cls.pre_existing_active_line_ids = set(pre_existing.filtered("active").ids)
        pre_existing.active = False
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

    def test_before_expiry_triggers_on_the_expiry_day_itself(self):
        """Inclusive upper bound: a card is still eligible on its expiry day, only the
        day after stops triggering (`today <= card.expiration_date`)."""
        self._add_program_line("before_expiry", self.other_mail_template, days_before=5)
        today = Date.context_today(self.env["loyalty.card"])
        card = self._create_card(self.partner, expiration_date=today)
        card._cron_send_reminders()
        self.assertFalse(card.reminder_line_ids.active)
        self.assertEqual(len(self._reminder_message(card)), 1)

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

    def test_sent_line_stays_in_the_one2many_despite_active_false(self):
        """`context={'active_test': False}` on `reminder_line_ids` is a structural
        constraint: without it the ORM would hide the deactivated line from the One2many
        in Python too, emptying the field as soon as a reminder has been sent and
        breaking both the display and the cron's `filtered('active')`."""
        self._add_program_line("points_remaining", self.mail_template, points_remaining=1)
        card = self._create_card(self.partner, points=1)
        card._cron_send_reminders()
        card.invalidate_recordset()
        self.assertEqual(len(card.reminder_line_ids), 1)
        self.assertFalse(card.reminder_line_ids.active)

    def test_card_without_holder_never_triggers(self):
        """The cron only sweeps cards having a holder to email (`partner_id` guard of
        the search domain)."""
        self._add_program_line("points_remaining", self.mail_template, points_remaining=1)
        card = self.env["loyalty.card"].create({
            "program_id": self.program.id,
            "points": 1,
        })
        card._cron_send_reminders()
        self.assertTrue(card.reminder_line_ids.active)
        self.assertFalse(self._reminder_message(card))

    def test_program_change_never_rewrites_materialised_card_lines(self):
        """The copy guard (`if ... or card.reminder_line_ids: continue`) protects for good
        the effective lines a card already carries, override included: a later program
        change recomputes `reminder_line_ids` and leaves them untouched.

        `reminder_line_ids` carries `precompute=True`, so the copy happens inside
        `create()`: the state the guard protects is already reached here, and reading the
        lines before the override is a convenience rather than a precondition."""
        self._add_program_line("points_remaining", self.mail_template, points_remaining=1)
        other_program = self.env["loyalty.program"].create({
            "name": "Other Program",
            "program_type": "loyalty",
        })
        self.env["loyalty.program.reminder.line"].create({
            "program_id": other_program.id,
            "trigger_type": "before_expiry",
            "days_before": 30,
            "mail_template_id": self.other_mail_template.id,
        })
        card = self._create_card(self.partner)
        card.reminder_line_ids.points_remaining = 3
        line = card.reminder_line_ids

        card.program_id = other_program
        self.assertEqual(card.reminder_line_ids, line)
        self.assertEqual(card.reminder_line_ids.trigger_type, "points_remaining")
        self.assertEqual(card.reminder_line_ids.points_remaining, 3)

    def test_program_change_without_any_read_still_never_retargets_the_copy(self):
        """Same guarantee as above, reached by the other path: nothing reads
        `reminder_line_ids` between the creation and the program change. Before
        `precompute=True` this was the one window where a program change did retarget
        the copy, which made the behaviour depend on the read order; the copy now happens
        inside `create()`, so the outcome no longer depends on who looked at the field
        first. This test exists to pin exactly that."""
        self._add_program_line("points_remaining", self.mail_template, points_remaining=1)
        other_program = self.env["loyalty.program"].create({
            "name": "Other Program",
            "program_type": "loyalty",
        })
        self.env["loyalty.program.reminder.line"].create({
            "program_id": other_program.id,
            "trigger_type": "before_expiry",
            "days_before": 30,
            "mail_template_id": self.other_mail_template.id,
        })
        card = self._create_card(self.partner)

        card.program_id = other_program
        self.assertEqual(len(card.reminder_line_ids), 1)
        self.assertEqual(card.reminder_line_ids.trigger_type, "points_remaining")
        self.assertEqual(card.reminder_line_ids.points_remaining, 1)

    def test_daily_cron_is_declared_on_the_card_model(self):
        cron = self.env.ref("loyalty_reminder.ir_cron_loyalty_reminder")
        self.assertEqual(cron.model_id, self.env["ir.model"]._get("loyalty.card"))
        self.assertEqual(cron.state, "code")
        self.assertEqual(cron.code, "model._cron_send_reminders()")
        self.assertEqual(cron.interval_number, 1)
        self.assertEqual(cron.interval_type, "days")
        self.assertTrue(cron.active)

    def test_reminder_subtype_is_internal_and_not_subscribed_by_default(self):
        subtype = self.env.ref("loyalty_reminder.mt_card_reminder_sent")
        self.assertEqual(subtype.res_model, "loyalty.card")
        self.assertFalse(subtype.default)
        self.assertTrue(subtype.internal)

    def test_internal_user_may_configure_lines_but_never_delete_them(self):
        """Access table of the spec: read/write/create granted to `base.group_user` on
        both new models, deletion denied."""
        user = new_test_user(self.env, login="loyalty_reminder_user")
        program_line = self.env["loyalty.program.reminder.line"].with_user(user).create({
            "program_id": self.program.id,
            "trigger_type": "points_remaining",
            "points_remaining": 2,
            "mail_template_id": self.mail_template.id,
        })
        program_line.points_remaining = 3
        self.assertEqual(program_line.read(["points_remaining"])[0]["points_remaining"], 3)
        with self.assertRaises(AccessError):
            program_line.unlink()

        card_line = self._create_card(self.partner).reminder_line_ids.with_user(user)
        card_line.points_remaining = 4
        self.assertEqual(card_line.read(["points_remaining"])[0]["points_remaining"], 4)
        with self.assertRaises(AccessError):
            card_line.unlink()

    # -- Hermeticity and demo data --------------------------------------

    def test_cron_pass_is_insensitive_to_pre_existing_reminder_lines(self):
        """Inverse of the usual rule: a test must not depend on demo data, but a cron
        that queries the whole database is broken *by* the demo this module itself adds.
        The guard asserted here is the neutralisation done in `setUpClass`: after it, a
        cron pass finds no line left to evaluate outside the fixtures of a test."""
        active_left = self.env["loyalty.card.reminder.line"].search(
            [("id", "in", list(self.pre_existing_active_line_ids))])
        self.assertFalse(active_left)

        card = self._create_card(self.partner, points=1)
        card._cron_send_reminders()
        self.assertFalse(card.reminder_line_ids)
        self.assertFalse(self.env["loyalty.card.reminder.line"].search(
            [("card_id", "!=", card.id), ("active", "=", True)]))

    def test_demo_data_extends_a_core_demo_program_without_creating_one(self):
        """The module depends on `loyalty` only, so its demo cannot reference the family
        pivot of `loyalty_expiration_management`. It extends a core demo program by
        external reference instead, and creates no `loyalty.program` of its own -- a
        parallel program set would silently shadow the pivot, with no load error."""
        lines = self._demo_program_lines()
        core_program = self.env.ref("loyalty.3_cabinets_plus_1_free")
        self.assertEqual(lines.program_id, core_program)
        self.assertEqual(
            self.env["ir.model.data"].search_count([
                ("module", "=", "loyalty_reminder"), ("model", "=", "loyalty.program")]),
            0)

    def test_demo_data_covers_both_triggers_and_the_already_sent_state(self):
        """A reminder engine whose reminders are never seen demonstrates nothing: the
        demo set has to make the module's behaviour legible in the UI with no prior
        manipulation. Pinned here: both triggers configured at program level, a card
        whose reminder has already been sent (deactivated line plus its chatter trace),
        and a card-level override that differs from the program default."""
        lines = self._demo_program_lines()
        self.assertEqual(
            set(lines.mapped("trigger_type")), {"points_remaining", "before_expiry"})

        sent_line = self.env.ref("loyalty_reminder.card_reminder_line_sent_balance")
        pending_line = self.env.ref("loyalty_reminder.card_reminder_line_pending_expiry")
        self.assertNotIn(sent_line.id, self.pre_existing_active_line_ids)
        self.assertIn(pending_line.id, self.pre_existing_active_line_ids)
        self.assertTrue(self._reminder_message(sent_line.card_id))

        override = self.env.ref("loyalty_reminder.card_reminder_line_custom_threshold")
        program_default = lines.filtered(
            lambda line: line.trigger_type == "points_remaining")
        self.assertNotEqual(
            override.points_remaining, program_default.points_remaining)

    def _demo_program_lines(self):
        lines = self.env["loyalty.program.reminder.line"].browse([
            self.env.ref(f"loyalty_reminder.{xml_id}", raise_if_not_found=False).id
            for xml_id in (
                "program_reminder_line_expiry",
                "program_reminder_line_last_use",
            )
            if self.env.ref(f"loyalty_reminder.{xml_id}", raise_if_not_found=False)
        ])
        if len(lines) != 2:
            self.skipTest("demo data of loyalty_reminder is not loaded")
        return lines

    def _reminder_message(self, card):
        subtype = self.env.ref("loyalty_reminder.mt_card_reminder_sent")
        return card.message_ids.filtered(lambda m: m.subtype_id == subtype)

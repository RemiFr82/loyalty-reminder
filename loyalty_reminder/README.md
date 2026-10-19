# Loyalty Reminder

`loyalty_reminder` — Odoo 17.0 Community — version `17.0.1.3.0` — LGPL-3

## Role

A `loyalty.program` whose cards expire, or run out of points, gives Odoo core no way to warn
the holder before it is too late: no email is sent when a card nears its expiry date or its
remaining balance drops to a low threshold. This module adds that reminder, configurable once
at program level and overridable independently on each card.

## What it adds

Two new models:

| Model | Role |
|---|---|
| `loyalty.program.reminder.line` | Default reminder configuration, carried by `loyalty.program`. |
| `loyalty.card.reminder.line` | The per-card copy, overridable without touching the program or any other card. |

Each line carries a `trigger_type` (`points_remaining` or `before_expiry`), the matching
threshold (`points_remaining` or `days_before`), and the `mail_template_id` (required,
domained to `loyalty.card`) sent when the trigger fires.

On card creation, the program's lines are copied onto the card (`reminder_line_ids`,
`precompute=True` so the copy happens before any other value written in the same `create`,
not lazily at first read). From that point on, editing a line on the card never touches the
program, and editing the program never touches a card created before the change.

A daily `ir.cron` (`_cron_send_reminders`, on `loyalty.card`) sweeps every active line of
every card: a line whose trigger is satisfied sends its template, logs a chatter message
under the dedicated subtype `Loyalty Card Reminder Sent`, and deactivates itself so it never
fires twice for the same card.

## Scope

Out of scope, deliberately: no new `loyalty.program` type, no change to how a program is
earned or redeemed, no reminder channel other than email, no reminder repeated after it has
fired once (a fired line stays inactive, it does not rearm). Extending the native
`loyalty.mail` (the core's own `create`/`points_reach` communication plan) instead of adding
a dedicated model was considered and rejected: `loyalty.mail` is tied to program-wide
triggers evaluated at specific lifecycle events, not to a per-card, per-trigger override that
must survive independently of the program.

**Structural dependency constraint**: `depends` carries `loyalty` only, never
`sale_loyalty`. The module must stay usable without the sale/coupon stack — a card existing
and expiring is enough to justify a reminder, selling anything is not a prerequisite. This
excludes referencing the socle module of the `loyalty_expiration_management` family (and
anything downstream of it) from this module's own code or demo data.

Installing the module changes no behaviour on its own: without at least one reminder line
configured on a program, no mail is ever sent.

## Demo data

The demo set extends a core demo program by external reference, `loyalty.3_cabinets_plus_1_free`,
and creates no `loyalty.program` of its own — nothing here can shadow or duplicate the
family pivot published by `loyalty_expiration_management` when both modules are installed.
`3_cabinets_plus_1_free` is chosen deliberately over the more obvious coupon program
`loyalty.10_percent_coupon`: that one carries a `create`-triggered communication plan whose
template attaches a QWeb report, and rendering it inside the demo load hangs indefinitely
without a working `wkhtmltopdf`.

The two reminder templates referenced by the demo set (`mail_template_card_expiry_reminder`,
`mail_template_card_balance_reminder`) are **not** demo data: `mail_template_id` is required
on both line models, and the module ships no other template, so these two live in `data/`
and are always present, demo loaded or not. The demo cards exercise both triggers, a card
whose reminder has already been sent (deactivated line plus its chatter trace), and a
card-level override that differs from its program's default — a reminder engine whose
reminders are never seen in the UI demonstrates nothing.

## Structure

```
__manifest__.py
models/
    loyalty_program.py             reminder_line_ids on loyalty.program
    loyalty_program_reminder_line.py
    loyalty_card.py                reminder_line_ids on loyalty.card, the precompute copy, the cron
    loyalty_card_reminder_line.py
views/
    loyalty_program_views.xml
    loyalty_card_views.xml
data/
    mail_message_subtype_data.xml  chatter subtype for a sent reminder
    mail_template_data.xml         the two reminder templates (functional, not demo)
    ir_cron_data.xml               the daily sweep
demo/
    loyalty_reminder_demo.xml
tests/
    test_loyalty_reminder.py
```

## State of the work

Alpha. Code written against the 17.0 Community source of `loyalty`, with tests covering the
program-to-card copy, both triggers, card-level overrides, hermeticity of the cron sweep
against pre-existing data, and the independence of the two templates from demo state.

Last test run, 2026-10-19, on an Odoo 17.0 Community instance with demo data:

```
odoo-bin -u loyalty_reminder --test-enable --test-tags=/loyalty_reminder \
         --workers=0 --stop-after-init --log-level=test
```

**24 tests, 0 failed, 0 errors.** `--workers=0` is not optional: in prefork mode the test
runner only emits a buried warning and the suite is unreliable. `--log-level=test` is what
makes the suite auditable: it prints one `Starting …` line per test, the only way to check
that the tests on disk are the tests that ran.

Also verified on a clean install and on a `--without-demo=all` base: `data/` loads before
`demo/`, and the two reminder templates resolve correctly with demo entirely disabled.

Translations (`i18n/fr.po`) started, not reviewed as part of this module's own test pass.

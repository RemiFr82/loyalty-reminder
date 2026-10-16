# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
{
    "name": "Loyalty Reminder",
    "version": "17.0.1.0.7",
    "summary": "Email reminders on loyalty card balance threshold or expiry date",
    "description": (
        "Sends an automatic reminder email to the holder of a loyalty card "
        "(loyalty.card) when a threshold of remaining points balance is reached, or "
        "when the card validity expiry date approaches. Default configuration "
        "at program level (loyalty.program), copied onto every new card and "
        "overridable independently afterwards."
    ),
    "author": "RemiFr82",
    "contributors": "",
    "maintainers": ["RemiFr82"],
    "website": "https://remifr82.me",
    "license": "LGPL-3",
    "price": 69.00,
    "currency": "EUR",
    "development_status": "Alpha",
    "category": "Sales/Loyalty",
    "application": False,
    "installable": True,
    "auto_install": False,
    "depends": [
        "loyalty",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/mail_message_subtype_data.xml",
        "data/ir_cron_data.xml",
        "views/loyalty_program_views.xml",
        "views/loyalty_card_views.xml",
    ],
}

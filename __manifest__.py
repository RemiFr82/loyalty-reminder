{
    "name": "Loyalty Reminder",
    "version": "17.0.1.0.4",
    "summary": "Rappels email sur seuil de solde ou échéance de carte de fidélité",
    "description": (
        "Envoie un email de rappel automatique au titulaire d'une carte de fidélité "
        "(loyalty.card) lorsqu'un seuil de solde de points restant est atteint, ou "
        "lorsque l'échéance de validité de la carte approche. Configuration par défaut "
        "au niveau du programme (loyalty.program), copiée sur chaque nouvelle carte et "
        "overridable indépendamment ensuite."
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

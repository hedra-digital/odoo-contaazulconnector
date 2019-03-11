{
    'name': 'Conta Azul',
    'category': 'Api call',
    'summary': 'This module design to integrate odoo with contaAzul',
    'license': 'AGPL-3',
    'version': '1.0',
    'description': """Contaazul Odoo integration""",
    'depends': ['base','purchase','sale_management','stock','br_sale', 'br_account','br_sale_stock'],
    'data': [
        'views/web_assets_load.xml',
        'security/contaazul_access.xml',
        'security/ir.model.access.csv',
        'views/contazul_company.xml',
        'views/contazul_inventory.xml',
        'views/res_config.xml',
        'views/contazul_customer.xml',
        'views/contazul_invoice.xml',
        'views/push_invoice_cron.xml',


    ],
    'author': 'Ksolves',
    'images': [

    ],
}
# -*- coding: utf-8 -*-

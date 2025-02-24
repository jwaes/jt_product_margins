# -*- coding: utf-8 -*-
{
    'name': "jt_product_margins",

    'summary': "Help with product margins and pricelists",

    'description': "",

    'author': "jaco tech",
    'website': "https://jaco.tech",
    "license": "AGPL-3",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '18.0.1.0.2',

    # any module necessary for this one to work correctly
    'depends': ['base', 'product', 'jt_pricelist_quarterly' ,'jt_product_properties'],

    # always loaded
    'data': [
        'data/property_key_margin.xml',
        'data/server_actions.xml',
        # 'security/ir.model.access.csv',
        'views/next_quarter_button_view.xml',
        'views/product_pricelist_views.xml',
        'views/product_pricelist_item_views.xml',
        'views/product_product_views.xml',
        'views/product_template_views.xml',
        'wizard/next_quarter_pricelist_wizard_views.xml',
    ],
}

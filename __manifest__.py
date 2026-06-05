# -*- coding: utf-8 -*-
{
    'name': "WMDs",

    'summary': "Local Warehouse Management System",

    'description': """Planned replacement for the current WMS.""",

    'author': "Wonderbrands",
    'website': "https://www.wonderbrands.co",

    'images': ['static/description/icon.png'],
    'category': 'Technical',
    'version': '18.0',

    'depends': [
        'base',
        'web',
        "website",
        "portal",
        "stock",
        "stock_barcode",
        "purchase",
        "WB_data_sale_order"
    ],

     'external_dependencies': {
        'python': [
            'qrcode',
        ],
    },

    'data': [
        "groups/groups.xml",
        "action/wmds_client.xml",
        "menu/main.xml",
        "template/wmds_template.xml",
        "data/wmds_status.xml",
        "data/block_reason_data.xml",
        "views/wmds_stock.xml",
        "views/wmds_po.xml",
        "views/wmds_sale.xml",
        "views/wmds_stock_batch.xml",
        "views/user.xml",
        "views/dock_n_bin.xml",
        "views/stock_move_wmds.xml",
        "views/stock_move_line_wmds.xml",
        "views/stock_location_block_wizard_view.xml",
        'views/report_dispatch_sheet.xml',
        "data/wmds_queued_tasks_cron.xml",
        "views/wmds_queued_tasks_views.xml",
        "security/ir.model.access.csv",

    ],

     "assets": {
        "web.assets_backend": [
            "wmds/static/src/js/WMDs_Component_Project/dist/odoo_vue_app.js",
            "wmds/static/src/js/barcode_behaviour.js",
            "wmds/static/src/js/backorder_log.js",
            "wmds/static/src/js/WMDs_Component_Project/dist/wmds-component-project.css",
            "wmds/static/src/js/index.js",
            "wmds/static/src/xml/barcode_template_inh.xml",
        ],
        "web.assets_frontend": [
            "wmds/static/src/css/style.css",
            "wmds/static/src/js/index.js",
        ],
    },

}


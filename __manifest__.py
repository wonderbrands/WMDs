# -*- coding: utf-8 -*-
{
    'name': "WMDs",

    'summary': "Local Warehouse Management System",

    'description': """
Planned replacement for the current WMS
    """,

    'author': "Wonderbrands",
    'website': "https://www.wonderbrands.co",


    'category': 'Technical',
    'version': '18.0',

    'depends': ['base',
    'web',
    "website",
    "portal",
    "stock"],

    'data': [
        "groups/groups.xml",
        "action/wmds_client.xml",
        "menu/main.xml",
        "template/wmds_template.xml",
        "data/wmds_status.xml",
        "views/wmds_stock.xml",
        "security/ir.model.access.csv",
    ],

     "assets": {
        "web.assets_backend": [
            "wmds/static/src/css/style.css",
            "wmds/static/src/js/index.js",
        ],
        "web.assets_frontend": [
            "wmds/static/src/css/style.css",
            "wmds/static/src/js/index.js",
        ],
    },

}


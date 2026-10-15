{
    'name': "Salesman Sale Restrictions",
    'version': '19.0.1.1.0',
    'category': 'Sales/Sales',
    'summary': "Non-managers: hide cost, margin and taxes on quotations, cap discounts (5% by default)",
    'author': "Anis Alim",
    'maintainer': "Anis Alim",
    'depends': ['sale_margin'],
    'data': [
        'views/sale_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
}

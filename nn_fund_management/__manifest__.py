{
    'name': 'NN Fund Management',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Finance',
    'summary': 'Manage incoming funds, allocations, requisitions and transfers',
    'author': 'Md Azmain Abrar',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'web'],
    'data': [
    'security/ir.model.access.csv',
    'data/sequences.xml',
    'views/fund_account_view.xml',
    'views/incoming_fund_view.xml',
    'views/project_expense_view.xml',
    'views/fund_allocation_view.xml',
    ],
    'installable': True,
    'application': True,
}
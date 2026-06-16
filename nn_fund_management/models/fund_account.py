from odoo import models, fields

class FundAccount(models.Model):
    _name = 'nn.fund.account'
    _description = 'Fund Account'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Account Name', required=True, tracking=True)
    account_type = fields.Selection([
        ('bank', 'Bank'),
        ('cash', 'Cash'),
        ('other', 'Other'),
    ], string='Account Type', required=True, default='bank')
    
    total_received = fields.Float(string='Total Received', default=0.0)
    unassigned_balance = fields.Float(string='Unassigned Balance', default=0.0)
    on_hold = fields.Float(string='On Hold', default=0.0)
    total_assigned = fields.Float(string='Total Assigned', default=0.0)
    
    notes = fields.Text(string='Notes')
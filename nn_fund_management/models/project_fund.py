from odoo import models, fields

class FundProject(models.Model):
    _name = 'nn.fund.project'
    _description = 'Fund Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Project Name', required=True, tracking=True)
    code = fields.Char(string='Project Code')
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)

    total_allocated = fields.Float(string='Total Allocated', default=0.0)
    available_balance = fields.Float(string='Available Balance', default=0.0)
    requisition_hold = fields.Float(string='Requisition Hold', default=0.0)
    transfer_hold = fields.Float(string='Transfer Hold', default=0.0)
    total_spent = fields.Float(string='Total Spent', default=0.0)
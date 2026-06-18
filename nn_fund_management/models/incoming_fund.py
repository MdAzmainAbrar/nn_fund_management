from odoo import models, fields, api
from odoo.exceptions import ValidationError

class IncomingFund(models.Model):
    _name = 'nn.incoming.fund'
    _description = 'Incoming Fund'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', required=True, copy=False,
                       readonly=True, default='New')
    fund_account_id = fields.Many2one('nn.fund.account', string='Fund Account',
                                       required=True, tracking=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.today)
    amount = fields.Float(string='Amount', required=True, tracking=True)
    transaction_ref = fields.Char(string='Transaction Reference', required=True)
    sender = fields.Char(string='Sender / Source')
    description = fields.Text(string='Description')
    company_id = fields.Many2one('res.company', string='Company',
                                  default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
    ], string='Status', default='draft', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('nn.incoming.fund') or 'New'
        return super().create(vals_list)

    def action_confirm(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError("Amount must be greater than zero.")
            rec.fund_account_id.total_received += rec.amount
            rec.fund_account_id.unassigned_balance += rec.amount
            rec.state = 'confirmed'

    _sql_constraints = [
        ('unique_transaction_ref', 
         'UNIQUE(fund_account_id, transaction_ref)',
         'Transaction reference must be unique per fund account!')
    ]
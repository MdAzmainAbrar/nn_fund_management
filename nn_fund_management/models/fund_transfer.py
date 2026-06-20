from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class FundTransfer(models.Model):
    _name = 'nn.fund.transfer'
    _description = 'Fund Transfer'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Transfer Number', required=True, copy=False,
                        readonly=True, default='New')

    source_type = fields.Selection([
        ('project', 'Project'),
        ('expense', 'Expense Head'),
    ], string='Source Type', required=True, default='project')
    source_project_id = fields.Many2one('nn.fund.project', string='Source Project')
    source_expense_id = fields.Many2one('nn.expense.head', string='Source Expense Head')

    dest_type = fields.Selection([
        ('project', 'Project'),
        ('expense', 'Expense Head'),
    ], string='Destination Type', required=True, default='project')
    dest_project_id = fields.Many2one('nn.fund.project', string='Destination Project')
    dest_expense_id = fields.Many2one('nn.expense.head', string='Destination Expense Head')

    amount = fields.Float(string='Amount', required=True, tracking=True)
    reason = fields.Text(string='Reason')
    requested_by = fields.Many2one('res.users', string='Requested By',
                                    default=lambda self: self.env.user)
    request_date = fields.Date(string='Request Date', default=fields.Date.today)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('gm_approval', 'GM Approval'),
        ('md_approval', 'MD Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    transfer_approval_ids = fields.One2many('nn.transfer.approval.history',
                                              'transfer_id', string='Approval History')

    def _get_source(self):
        return self.source_project_id if self.source_type == 'project' else self.source_expense_id

    def _get_dest(self):
        return self.dest_project_id if self.dest_type == 'project' else self.dest_expense_id

    @api.constrains('source_type', 'source_project_id', 'source_expense_id',
                     'dest_type', 'dest_project_id', 'dest_expense_id')
    def _check_source_dest(self):
        for rec in self:
            source = rec._get_source()
            dest = rec._get_dest()
            if not source:
                raise ValidationError("Please select a source.")
            if not dest:
                raise ValidationError("Please select a destination.")
            if source.id == dest.id and rec.source_type == rec.dest_type:
                raise ValidationError("Source and destination cannot be the same.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('nn.fund.transfer') or 'New'
        return super().create(vals_list)

    def action_submit(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError("Amount must be greater than zero.")
            source = rec._get_source()
            if rec.amount > source.available_balance:
                raise ValidationError(
                    "Transfer amount (%.2f) exceeds source's available balance (%.2f)." %
                    (rec.amount, source.available_balance)
                )
            source.available_balance -= rec.amount
            source.transfer_hold += rec.amount
            rec.state = 'gm_approval'
            rec._log_approval('submitted', 'Request submitted')

    def action_gm_approve(self, comment=None):
        for rec in self:
            if rec.state != 'gm_approval':
                raise UserError("This request is not waiting for GM approval.")
            if not self.env.user.has_group('nn_fund_management.group_gm_approver'):
                raise UserError("Only GM Approvers can perform this action.")
            if rec.requested_by == self.env.user:
                raise UserError("You cannot approve your own request.")
            rec.state = 'md_approval'
            rec._log_approval('gm_approval', comment or 'Approved by GM')

    def action_md_approve(self, comment=None):
        for rec in self:
            if rec.state != 'md_approval':
                raise UserError("This request is not waiting for MD approval.")
            if not self.env.user.has_group('nn_fund_management.group_md_approver'):
                raise UserError("Only MD Approvers can perform this action.")
            if rec.requested_by == self.env.user:
                raise UserError("You cannot approve your own request.")

            source = rec._get_source()
            dest = rec._get_dest()
            source.transfer_hold -= rec.amount
            dest.available_balance += rec.amount
            dest.total_allocated += rec.amount

            rec.state = 'approved'
            rec._log_approval('md_approval', comment or 'Approved by MD')

    def action_reject(self, comment=None):
        for rec in self:
            if rec.state in ('gm_approval', 'md_approval'):
                source = rec._get_source()
                source.transfer_hold -= rec.amount
                source.available_balance += rec.amount
            rec.state = 'rejected'
            rec._log_approval('rejected', comment or 'Rejected')

    def action_cancel(self):
        for rec in self:
            if rec.state in ('gm_approval', 'md_approval'):
                source = rec._get_source()
                source.transfer_hold -= rec.amount
                source.available_balance += rec.amount
            rec.state = 'cancelled'
            rec._log_approval('cancelled', 'Request cancelled')

    def _log_approval(self, level, comment):
        self.env['nn.transfer.approval.history'].create({
            'transfer_id': self.id,
            'approver_id': self.env.user.id,
            'level': level,
            'comment': comment,
            'result': self.state,
        })


class TransferApprovalHistory(models.Model):
    _name = 'nn.transfer.approval.history'
    _description = 'Transfer Approval History'
    _order = 'create_date desc'

    transfer_id = fields.Many2one('nn.fund.transfer', string='Transfer', ondelete='cascade')
    approver_id = fields.Many2one('res.users', string='Approver',
                                   default=lambda self: self.env.user)
    level = fields.Char(string='Approval Level')
    comment = fields.Text(string='Comment')
    result = fields.Char(string='Result')
    date = fields.Datetime(string='Date', default=fields.Datetime.now)
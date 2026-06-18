from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class FundAllocation(models.Model):
    _name = 'nn.fund.allocation'
    _description = 'Fund Allocation Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Request Number', required=True, copy=False,
                        readonly=True, default='New')
    fund_account_id = fields.Many2one('nn.fund.account', string='Fund Account',
                                       required=True, tracking=True)

    allocation_type = fields.Selection([
        ('project', 'Project'),
        ('expense', 'Expense Head'),
    ], string='Allocate To', required=True, default='project', tracking=True)

    project_id = fields.Many2one('nn.fund.project', string='Project')
    expense_head_id = fields.Many2one('nn.expense.head', string='Expense Head')

    amount = fields.Float(string='Amount', required=True, tracking=True)
    purpose = fields.Text(string='Purpose')
    request_date = fields.Date(string='Request Date', default=fields.Date.today)
    requested_by = fields.Many2one('res.users', string='Requested By',
                                    default=lambda self: self.env.user)
    attachment = fields.Binary(string='Attachment')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('gm_approval', 'GM Approval'),
        ('md_approval', 'MD Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    approval_history_ids = fields.One2many('nn.approval.history', 'allocation_id',
                                             string='Approval History')

    # ---------- Constraints ----------
    @api.constrains('allocation_type', 'project_id', 'expense_head_id')
    def _check_single_target(self):
        for rec in self:
            if rec.allocation_type == 'project' and not rec.project_id:
                raise ValidationError("Please select a Project.")
            if rec.allocation_type == 'expense' and not rec.expense_head_id:
                raise ValidationError("Please select an Expense Head.")
            if rec.project_id and rec.expense_head_id:
                raise ValidationError("An allocation must use either a Project or an Expense Head, not both.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('nn.fund.allocation') or 'New'
        return super().create(vals_list)

    # ---------- Workflow Actions ----------
    def action_submit(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError("Amount must be greater than zero.")
            if rec.amount > rec.fund_account_id.unassigned_balance:
                raise ValidationError(
                    "Requested amount (%.2f) exceeds available unassigned balance (%.2f)." %
                    (rec.amount, rec.fund_account_id.unassigned_balance)
                )
            # Hold the amount
            rec.fund_account_id.unassigned_balance -= rec.amount
            rec.fund_account_id.on_hold += rec.amount
            rec.state = 'gm_approval'
            rec._log_approval('submitted', 'Request submitted')

    def action_gm_approve(self, comment=None):
        for rec in self:
            if rec.state != 'gm_approval':
                raise UserError("This request is not waiting for GM approval.")
            if rec.requested_by == self.env.user:
                raise UserError("You cannot approve your own request.")
            rec.state = 'md_approval'
            rec._log_approval('gm_approval', comment or 'Approved by GM')

    def action_md_approve(self, comment=None):
        for rec in self:
            if rec.state != 'md_approval':
                raise UserError("This request is not waiting for MD approval.")
            if rec.requested_by == self.env.user:
                raise UserError("You cannot approve your own request.")
            # Move from hold to assigned
            rec.fund_account_id.on_hold -= rec.amount
            rec.fund_account_id.total_assigned += rec.amount

            if rec.allocation_type == 'project':
                rec.project_id.total_allocated += rec.amount
                rec.project_id.available_balance += rec.amount
            else:
                rec.expense_head_id.total_allocated += rec.amount
                rec.expense_head_id.available_balance += rec.amount

            rec.state = 'approved'
            rec._log_approval('md_approval', comment or 'Approved by MD')

    def action_reject(self, comment=None):
        for rec in self:
            if rec.state in ('gm_approval', 'md_approval'):
                rec.fund_account_id.on_hold -= rec.amount
                rec.fund_account_id.unassigned_balance += rec.amount
            rec.state = 'rejected'
            rec._log_approval('rejected', comment or 'Rejected')

    def action_cancel(self):
        for rec in self:
            if rec.state in ('gm_approval', 'md_approval'):
                rec.fund_account_id.on_hold -= rec.amount
                rec.fund_account_id.unassigned_balance += rec.amount
            rec.state = 'cancelled'
            rec._log_approval('cancelled', 'Request cancelled')

    def action_reset_draft(self):
        for rec in self:
            rec.state = 'draft'

    def _log_approval(self, level, comment):
        self.env['nn.approval.history'].create({
            'allocation_id': self.id,
            'approver_id': self.env.user.id,
            'level': level,
            'comment': comment,
            'result': self.state,
        })


class ApprovalHistory(models.Model):
    _name = 'nn.approval.history'
    _description = 'Approval History'
    _order = 'create_date desc'

    allocation_id = fields.Many2one('nn.fund.allocation', string='Allocation Request',
                                     ondelete='cascade')
    approver_id = fields.Many2one('res.users', string='Approver',
                                   default=lambda self: self.env.user)
    level = fields.Char(string='Approval Level')
    comment = fields.Text(string='Comment')
    result = fields.Char(string='Result')
    date = fields.Datetime(string='Date', default=fields.Datetime.now)
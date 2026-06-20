from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class FundRequisition(models.Model):
    _name = 'nn.fund.requisition'
    _description = 'Fund Requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Requisition Number', required=True, copy=False,
                        readonly=True, default='New')

    allocation_type = fields.Selection([
        ('project', 'Project'),
        ('expense', 'Expense Head'),
    ], string='Source', required=True, default='project', tracking=True)

    project_id = fields.Many2one('nn.fund.project', string='Project')
    expense_head_id = fields.Many2one('nn.expense.head', string='Expense Head')

    amount = fields.Float(string='Requested Amount', required=True, tracking=True)
    purpose = fields.Text(string='Purpose')
    request_date = fields.Date(string='Request Date', default=fields.Date.today)
    required_date = fields.Date(string='Required Date')
    requested_by = fields.Many2one('res.users', string='Requested By',
                                    default=lambda self: self.env.user)
    attachment = fields.Binary(string='Attachment')

    billed_amount = fields.Float(string='Billed Amount', default=0.0)
    remaining_billable = fields.Float(string='Remaining Billable',
                                       compute='_compute_remaining_billable', store=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('gm_approval', 'GM Approval'),
        ('md_approval', 'MD Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', tracking=True)

    requisition_approval_ids = fields.One2many('nn.requisition.approval.history',
                                                 'requisition_id', string='Approval History')

    @api.depends('amount', 'billed_amount')
    def _compute_remaining_billable(self):
        for rec in self:
            rec.remaining_billable = rec.amount - rec.billed_amount

    @api.constrains('allocation_type', 'project_id', 'expense_head_id')
    def _check_single_target(self):
        for rec in self:
            if rec.allocation_type == 'project' and not rec.project_id:
                raise ValidationError("Please select a Project.")
            if rec.allocation_type == 'expense' and not rec.expense_head_id:
                raise ValidationError("Please select an Expense Head.")
            if rec.project_id and rec.expense_head_id:
                raise ValidationError("A requisition must use either a Project or an Expense Head, not both.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('nn.fund.requisition') or 'New'
        return super().create(vals_list)

    def _get_source(self):
        return self.project_id if self.allocation_type == 'project' else self.expense_head_id

    def action_submit(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError("Amount must be greater than zero.")
            source = rec._get_source()
            if rec.amount > source.available_balance:
                raise ValidationError(
                    "Requested amount (%.2f) exceeds available balance (%.2f)." %
                    (rec.amount, source.available_balance)
                )
            source.available_balance -= rec.amount
            source.requisition_hold += rec.amount
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
            # Amount stays reserved (held) for billing - no change to source balance here
            rec.state = 'approved'
            rec._log_approval('md_approval', comment or 'Approved by MD')

    def action_reject(self, comment=None):
        for rec in self:
            if rec.state in ('gm_approval', 'md_approval'):
                source = rec._get_source()
                source.requisition_hold -= rec.amount
                source.available_balance += rec.amount
            rec.state = 'rejected'
            rec._log_approval('rejected', comment or 'Rejected')

    def action_cancel(self):
        for rec in self:
            if rec.state in ('gm_approval', 'md_approval', 'approved'):
                source = rec._get_source()
                unused = rec.amount - rec.billed_amount
                source.requisition_hold -= unused
                source.available_balance += unused
            rec.state = 'cancelled'
            rec._log_approval('cancelled', 'Request cancelled')

    def action_close(self):
        for rec in self:
            if rec.state != 'approved':
                raise UserError("Only approved requisitions can be closed.")
            source = rec._get_source()
            unused = rec.amount - rec.billed_amount
            if unused > 0:
                source.requisition_hold -= unused
                source.available_balance += unused
            rec.state = 'closed'
            rec._log_approval('closed', 'Requisition closed')

    def _log_approval(self, level, comment):
        self.env['nn.requisition.approval.history'].create({
            'requisition_id': self.id,
            'approver_id': self.env.user.id,
            'level': level,
            'comment': comment,
            'result': self.state,
        })


class RequisitionApprovalHistory(models.Model):
    _name = 'nn.requisition.approval.history'
    _description = 'Requisition Approval History'
    _order = 'create_date desc'

    requisition_id = fields.Many2one('nn.fund.requisition', string='Requisition',
                                      ondelete='cascade')
    approver_id = fields.Many2one('res.users', string='Approver',
                                   default=lambda self: self.env.user)
    level = fields.Char(string='Approval Level')
    comment = fields.Text(string='Comment')
    result = fields.Char(string='Result')
    date = fields.Datetime(string='Date', default=fields.Datetime.now)
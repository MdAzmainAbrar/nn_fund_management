from odoo import models, fields, api
from odoo.exceptions import ValidationError


class FundBill(models.Model):
    _name = 'nn.fund.bill'
    _description = 'Fund Bill'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Bill Number', required=True, copy=False,
                        readonly=True, default='New')
    requisition_id = fields.Many2one('nn.fund.requisition', string='Requisition',
                                      required=True, tracking=True,
                                      domain="[('state', '=', 'approved')]")
    amount = fields.Float(string='Bill Amount', required=True, tracking=True)
    bill_date = fields.Date(string='Bill Date', default=fields.Date.today)
    description = fields.Text(string='Description')
    attachment = fields.Binary(string='Attachment')

    # Mirror fields for convenience/reporting
    project_id = fields.Many2one(related='requisition_id.project_id', string='Project', store=True)
    expense_head_id = fields.Many2one(related='requisition_id.expense_head_id', string='Expense Head', store=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('nn.fund.bill') or 'New'
        return super().create(vals_list)

    @api.constrains('requisition_id', 'amount')
    def _check_bill_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError("Bill amount must be greater than zero.")
            if rec.requisition_id.state != 'approved':
                raise ValidationError("Only approved requisitions can be used for bills.")
            # Exclude this bill's own current amount if editing
            other_billed = sum(
                b.amount for b in rec.requisition_id.bill_ids
                if b.id != rec.id and b.state == 'posted'
            )
            if other_billed + rec.amount > rec.requisition_id.amount:
                raise ValidationError(
                    "This bill (%.2f) exceeds the requisition's remaining billable amount (%.2f)." %
                    (rec.amount, rec.requisition_id.amount - other_billed)
                )

    def action_post(self):
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError("Only draft bills can be posted.")
            requisition = rec.requisition_id
            remaining = requisition.amount - requisition.billed_amount
            if rec.amount > remaining:
                raise ValidationError(
                    "Bill amount (%.2f) exceeds remaining billable amount (%.2f)." %
                    (rec.amount, remaining)
                )
            # Update requisition billed amount
            requisition.billed_amount += rec.amount

            # Move from requisition_hold to spent on the project/expense head
            source = requisition._get_source()
            source.requisition_hold -= rec.amount
            source.total_spent += rec.amount

            rec.state = 'posted'

    def action_cancel(self):
        for rec in self:
            if rec.state == 'posted':
                requisition = rec.requisition_id
                requisition.billed_amount -= rec.amount
                source = requisition._get_source()
                source.total_spent -= rec.amount
                source.requisition_hold += rec.amount
            rec.state = 'cancelled'

    def action_reset_draft(self):
        for rec in self:
            rec.state = 'draft'


class FundRequisitionBillExtension(models.Model):
    """Extend Fund Requisition to show related bills"""
    _inherit = 'nn.fund.requisition'

    bill_ids = fields.One2many('nn.fund.bill', 'requisition_id', string='Bills')
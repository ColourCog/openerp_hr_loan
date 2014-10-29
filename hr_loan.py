#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

import time

from datetime import datetime, date
from openerp import netsvc
from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

#TODO: 
# generate journal entries using employee name and loan name as reference
# debit an asset account (OHADA?) and credit the cash account

def _employee_get(obj, cr, uid, context=None):
    if context is None:
        context = {}
    ids = obj.pool.get('hr.employee').search(cr, uid, [('user_id', '=', uid)], context=context)
    if ids:
        return ids[0]
    return False

class hr_loan(osv.osv):
    _name = 'hr.loan' 
    _inherit = ['mail.thread', 'ir.needaction_mixin'] 
    _description = 'HR Loan Management' 
    _track = {
        'state': {
          'hr_loan.mt_loan_accepted': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'accepted',
          'hr_loan.mt_loan_refused': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'cancelled',
          'hr_loan.mt_loan_confirmed': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'confirm',
        },
    }
  
    def _get_paid_loans(self, cr, uid, ids, context=None):
        res = { this.id : True for this in self.browse(cr, uid, ids, context=context)
                if this.balance == 0 }
        return res.keys()

    def onchange_employee_id(self, cr, uid, ids, employee_id, context=None):
        emp_obj = self.pool.get('hr.employee')
        company_id = False
        if employee_id:
            employee = emp_obj.browse(cr, uid, employee_id, context=context)
            company_id = employee.company_id.id
        return {'value': {'company_id': company_id}}

    _columns = { 
        'name' : fields.char('Name', size=64, select=True, readonly=True), 
        'date' : fields.date('Date', required=True, select=True, readonly=True, states={'draft':[('readonly',False)], 'accepted':[('readonly',False)]}), 
        'employee_id' : fields.many2one('hr.employee', 'Employee', required=True, readonly=True, states={'draft':[('readonly',False)]}), 
        'user_id': fields.many2one('res.users', 'User', required=True),
        'notes' : fields.text('Description', required=True, readonly=True, states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]}),
        'amount' : fields.float('Amount', digits_compute=dp.get_precision('Sale Price'), required=True, readonly=True, states={'draft':[('readonly',False)]}), 
        'nb_payments': fields.integer("Number of payments", required=True, readonly=True, states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]}),
        'installment' : fields.float('Due amount per payment', digits_compute=dp.get_precision('Sale Price'), required=True, readonly=True), 
        'balance' : fields.float('Balance', digits_compute=dp.get_precision('Sale Price'), required=True, readonly=True), 
        'journal_id': fields.many2one('account.journal', 'Force Journal', help = "The journal used to record loans."),
        'account_debit': fields.many2one('account.account', 'Debit Account', readonly=True, states={'accepted':[('readonly',False)]}, help="The account in which the loan will be recorded"),
        'account_credit': fields.many2one('account.account', 'Credit Account', readonly=True, states={'accepted':[('readonly',False)]}, help="The account in which the loan will be paid to the employee"),
        'account_move_id': fields.many2one('account.move', 'Ledger Posting'),
        'date_confirm': fields.date('Confirmation Date', select=True, help="Date of the confirmation of the loan. It's filled when the button Confirm is pressed."),
        'date_valid': fields.date('Validation Date', select=True, help="Date of the acceptation of the sheet expense. It's filled when the button Accept is pressed."),
        'user_valid': fields.many2one('res.users', 'Validation By', readonly=True, states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]}),
        'company_id': fields.many2one('res.company', 'Company', required=True),
        'state': fields.selection([
                ('draft', 'New'),
                ('cancelled', 'Refused'),
                ('confirm', 'Waiting Approval'),
                ('accepted', 'Accepted'),
                ('done', 'Waiting Payment'),
                ('paid', 'Paid'),
                ],
                'Status', readonly=True, track_visibility='onchange',
                help=_('When the loan request is created the status is \'Draft\'.\n It is confirmed by the user and request is sent to admin, the status is \'Waiting Confirmation\'.\
                \nIf the admin accepts it, the status is \'Accepted\'.\n If the accounting entries are made for the loan request, the status is \'Waiting Payment\'.')),
    }

    _defaults = {
        'company_id': lambda s, cr, uid, c: s.pool.get('res.company')._company_default_get(cr, uid, 'hr.employee', context=c),
        'date': fields.date.context_today,
        'nb_payments': 1,
        'state': 'draft',
        'employee_id': _employee_get,
        'user_id': lambda cr, uid, id, c={}: id,
    }


    def create(self, cr, uid, vals, context=None):
        if 'employee_id' in vals and vals['employee_id']: 
            employee = self.pool.get('hr.employee').browse(cr, uid, [vals['employee_id']])[0] 
        if vals.get('name','/') == '/':
            vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'hr.loan') or '/'
        vals['balance'] = vals['amount']
        vals['installment'] = vals['amount'] / vals['nb_payments']
        return super(hr_loan, self).create(cr, uid, vals, context=context)

    def unlink(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids, context=context):
            if rec.state != 'draft':
                raise osv.except_osv(_('Warning!'),_('You can only delete draft loans!'))
        return super(hr_loan, self).unlink(cr, uid, ids, context)

    def loan_draft(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'draft', 'date_valid': None, 'user_valid': None}, context=context)

    def loan_confirm(self, cr, uid, ids, context=None):
        for loan in self.browse(cr, uid, ids):
            if loan.amount <= 0.0: 
              raise osv.except_osv( 
                _('Could not confirm Loan !'), 
                _('Amount must be greater than zero.')) 
            if loan.nb_payments < 0: 
              raise osv.except_osv( 
                _('Could not confirm Loan !'), 
                _('You must set a Number of Payments')) 
            if loan.employee_id and loan.employee_id.parent_id.user_id:
                self.message_subscribe_users(cr, uid, [loan.id], user_ids=[loan.employee_id.parent_id.user_id.id])
        return self.write(cr, uid, ids, {'state': 'confirm', 'date_confirm': time.strftime('%Y-%m-%d')}, context=context)

    def loan_accept(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'accepted', 'date_valid': time.strftime('%Y-%m-%d'), 'user_valid': uid}, context=context)

    def loan_canceled(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'cancelled'}, context=context)

    def condition_paid(self, cr, uid, ids, context=None):
        ok = True
        for l in self.browse(cr, uid, ids, context=context):
            if l.balance > 0:
                ok = False
        return ok

    def decrease_balance(self, cr, uid, ids, context=None):
        res = []
        for loan in self.browse(cr, uid, ids):
            if loan.balance > 0 :
                res.append(self.write(cr, uid, [loan.id], {'balance': loan.balance - loan.installment}, context=context))
        return res
        
    def account_move_get(self, cr, uid, loan_id, context=None):
        '''
        This method prepare the creation of the account move related to the given loan.

        :param loan_id: Id of loan for which we are creating account_move.
        :return: mapping between fieldname and value of account move to create
        :rtype: dict
        '''
        journal_obj = self.pool.get('account.journal')
        loan = self.browse(cr, uid, loan_id, context=context)
        company_id = loan.company_id.id
        date = loan.date_confirm
        ref = loan.name
        journal_id = False
        if loan.journal_id:
            journal_id = loan.journal_id.id
        else:
            journal_id = journal_obj.search(cr, uid, [('type', '=', 'general'), ('company_id', '=', company_id)])
            if not journal_id:
                raise osv.except_osv(_('Error!'), _("No loan journal found. Please make sure you have a journal with type 'general' configured."))
            journal_id = journal_id[0]
        return self.pool.get('account.move').account_move_prepare(cr, uid, journal_id, date=date, ref=ref, company_id=company_id, context=context)

    def action_receipt_create(self, cr, uid, ids, context=None):
        """Create accounting entries for this loan"""
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        for loan in self.browse(cr, uid, ids, context=context):
            if not loan.account_debit:
                raise osv.except_osv(_('Error!'), _('You must select an account to debit for this loan'))
            if not loan.account_credit:
                raise osv.except_osv(_('Error!'), _('You must select an account to credit for this loan'))
            
            #create the move that will contain the accounting entries
            move_id = move_obj.create(cr, uid, self.account_move_get(cr, uid, loan.id, context=context), context=context)
        
            lml = []
            # create the debit move line
            lml.append({
                    'type': 'src',
                    'name': loan.employee_id.name,
                    'debit': loan.amount, 
                    'account_id': loan.account_debit.id, 
                    'date_maturity': loan.date_confirm, 
                    'ref': loan.name
                    })
            
            # create the credit move line
            lml.append({
                    'type': 'dest',
                    'name': loan.employee_id.name,
                    'credit': loan.amount, 
                    'account_id': loan.account_credit.id, 
                    'date_maturity': loan.date_confirm, 
                    'ref': loan.name
                    })
            #convert eml into an osv-valid format
            lines = [(0,0,x) for x in lml]
            journal_id = move_obj.browse(cr, uid, move_id, context).journal_id
            # post the journal entry if 'Skip 'Draft' State for Manual Entries' is checked
            if journal_id.entry_posted:
                move_obj.button_validate(cr, uid, [move_id], context)
            move_obj.write(cr, uid, [move_id], {'line_id': lines}, context=context)
            self.write(cr, uid, ids, {'account_move_id': move_id, 'state': 'done'}, context=context)
        return True

    def action_view_receipt(self, cr, uid, ids, context=None):
        '''
        This function returns an action that display existing account.move of given expense ids.
        '''
        assert len(ids) == 1, 'This option should only be used for a single id at a time'
        loan = self.browse(cr, uid, ids[0], context=context)
        assert loan.account_move_id
        try:
            dummy, view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account', 'view_move_form')
        except ValueError, e:
            view_id = False
        result = {
            'name': _('Loan Account Move'),
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
            'res_id': loan.account_move_id.id,
        }
        return result

hr_loan()

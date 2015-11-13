# -*- coding: utf-8 -*-
import time
from datetime import datetime, date
from openerp import netsvc
from openerp import pooler
from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
import logging
_logger = logging.getLogger(__name__)


def _employee_get(obj, cr, uid, context=None):
    if context is None:
        context = {}
    ids = obj.pool.get('hr.employee').search(
            cr,
            uid,
            [('user_id', '=', uid)],
            context=context)
    if ids:
        return ids[0]
    return False


class hr_loan_payment(osv.osv):
    _name = 'hr.loan.payment'

    _columns = {
        'loan_id': fields.many2one('hr.loan', 'Loan', required=True),
        'slip_id': fields.many2one('hr.payslip', 'Payslip', required=True),
        'amount': fields.float(
            'Amount',
            digits_compute=dp.get_precision('Payroll')),
    }
    _sql_constraints = [(
        'loan_slip_unique',
        'unique (loan_id, slip_id)',
        'Payslips must be unique per Loan !'),
    ]

    def unlink(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids, context=context):
            if rec.slipd_id and rec.slip_id.state not in ['draft', 'cancelled']:
                raise osv.except_osv(
                    _('Warning!'),
                    _('You must cancel the Payslip to delete this payment.'))
        return super(hr_loan_payment, self).unlink(cr, uid, ids, context)

hr_loan_payment()



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

    def _default_loan_account(self, cr, uid, context=None):
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if user.company_id.default_loan_account_id:
            return user.company_id.default_loan_account_id.id
        return False

    def _default_advance_account(self, cr, uid, context=None):
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if user.company_id.default_advance_account_id:
            return user.company_id.default_advance_account_id.id
        return False

    def _default_transfer_account(self, cr, uid, context=None):
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if user.company_id.default_loan_transfer_account_id:
            return user.company_id.default_loan_transfer_account_id.id
        return False

    def _default_journal(self, cr, uid, context=None):
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if user.company_id.default_loan_journal_id:
            return user.company_id.default_loan_journal_id.id
        return False

    def _get_currency(self, cr, uid, context=None):
        res = False
        journal_id = self._default_journal(cr, uid, context=context)
        if journal_id:
            journal = self.pool.get('account.journal').browse(
                    cr,
                    uid,
                    journal_id,
                    context=context)
            res = journal.company_id.currency_id.id
            if journal.currency:
                res = journal.currency.id
        return res

    def _get_loan_from_payment(self, cr, uid, ids, context=None):
        pay_obj = self.pool.get('hr.loan.payment')
        return [p.loan_id.id
                for p in pay_obj.browse(cr, uid, ids, context=context)]
    
    def _get_loan_from_voucher(self, cr, uid, ids, context=None):
        voucher_obj = self.pool.get('account.voucher')
        return [p.loan_id.id
                for p in voucher_obj.browse(cr, uid, ids, context=context)]

    def _get_loan_payments(self, cr, uid, ids, context=None):
        res = []
        for loan in self.browse(cr, uid, ids, context=context):
            res. extend([p.id for p in loan.payment_ids])
        return res

    def onchange_employee_id(self, cr, uid, ids, employee_id,
                        context=None):
        emp_obj = self.pool.get('hr.employee')
        company_id = False
        if employee_id:
            employee = emp_obj.browse(
                cr,
                uid,
                employee_id,
                context=context)
            company_id = employee.company_id.id
            return {'value': {'company_id': company_id}}

    def onchange_advance(self, cr, uid, ids, is_advance, context=None):
        switch = {
            True:self._default_advance_account,
            False:self._default_loan_account,
        }
        val = switch.get(is_advance, False)(cr, uid, context=context)
        return {'value': {'account_debit': val}}

    def onchange_amount(self, cr, uid, ids, amount, nb_payments,
                        context=None):
        val = amount / nb_payments
        return {'value': {'installment': val}}

    def onchange_nb_payments(self, cr, uid, ids, amount, nb_payments,
                                context=None):
        return self.onchange_amount(
                cr,
                uid,
                ids,
                amount,
                nb_payments,
                context=context)

    def _get_balance(self, cr, uid, ids, name, args, context):
        if not ids:
            return {}
        res = {}
        for loan in self.browse(cr, uid, ids, context=context):
            payslip = sum([ p.amount for p in loan.payment_ids])
            vouchers = sum([ v.amount for v in loan.voucher_ids])
            res[loan.id] = loan.amount - (payslip + vouchers)
            if loan.amount:
                if loan.move_id:
                    self.write(cr, uid, ids, {'state': 'waiting'}, context=context)
                if res[loan.id] <= 0.0:
                    self.write(cr, uid, ids, {'state': 'paid'}, context=context)
        return res

        

    _columns = {
        'name': fields.char('Name', size=64, select=True, readonly=True),
        'date': fields.date(
            'Date',
            required=True,
            select=True,
            readonly=True,
            states={
                'draft': [('readonly', False)],
                'accepted': [('readonly', False)]}),
        'is_advance': fields.boolean(
            'Advance',
            readonly=True,
            states={
                'draft': [('readonly', False)]},
                help="If its checked, indicates that loan is actually an advance."),
        'employee_id': fields.many2one(
            'hr.employee',
            'Employee',
            required=True,
            readonly=True,
            states={'draft': [('readonly', False)]}),
        'user_id': fields.many2one('res.users', 'User', required=True),
        'notes': fields.text(
            'Justification',
            required=True,
            readonly=True,
            states={
                'draft': [('readonly', False)],
                'confirm': [('readonly', False)]}),
        'amount': fields.float(
            'Amount',
            digits_compute=dp.get_precision('Payroll'),
            required=True,
            readonly=True,
            states={'draft': [('readonly', False)]}),
        'currency_id': fields.many2one(
            'res.currency',
            'Currency',
            required=True),
        'nb_payments': fields.integer(
            'Number of payments',
            required=True,
            readonly=True,
            states={'draft': [('readonly', False)]}),
        'installment': fields.float(
            'Due amount per payment',
            digits_compute=dp.get_precision('Payroll'),
            required=True,
            readonly=True,
            states={'draft': [('readonly', False)]}),
        'payment_ids': fields.one2many(
            'hr.loan.payment',
            'loan_id',
            'Loan Payslip Payments'),
        'voucher_ids': fields.one2many(
            'account.voucher',
            'loan_id',
            'Loan Spontaneous Payments'),
        'move_ids': fields.one2many(
            'account.move',
            'loan_id',
            'Loan Spontaneous Payments moves'),
        'balance': fields.function(
            _get_balance,
            type='float',
            string='Balance',
            digits_compute=dp.get_precision('Payroll'),
            store={
                _name: (lambda self, cr, uid, ids, c: ids, ['payment_ids', 'voucher_ids', 'amount'], 10),
                'hr.loan.payment': (_get_loan_from_payment, None, 10),
                'account.voucher': (_get_loan_from_voucher, None, 10),
            }),
        'journal_id': fields.many2one(
            'account.journal',
            'Journal',
            help="The journal used to record loans."),
        'account_debit': fields.many2one(
            'account.account',
            'Debit Account',
            help="The account in which the loan will be recorded"),
        'account_credit': fields.many2one(
            'account.account',
            'Transit Account',
            help="The account from which the loan will be paid to the employee"),
        'move_id': fields.many2one(
            'account.move', 
            'Journal Entry',
            readonly=True),
        'voucher_id': fields.many2one(
            'account.voucher',
            'Give-out Voucher',
            readonly=True),
        'date_confirm': fields.date(
            'Request Date',
            select=True,
            help="Date of loan submission."),
        'date_valid': fields.date(
            'Validation Date',
            select=True,
            help="Date of loan validation by hierarchy."),
        'user_valid': fields.many2one(
            'res.users',
            'Validation By',
            readonly=True,
            states={
                'draft': [('readonly', False)],
                'confirm': [('readonly', False)]}),
        'company_id': fields.many2one('res.company', 'Company', required=True),
        'state': fields.selection([
            ('draft', 'New'),
            ('cancelled', 'Cancelled'),
            ('confirm', 'Awaiting Approval'),
            ('accepted', 'Accepted'),
            ('waiting', 'Awaiting Payment'),
            ('paid', 'Paid'),
            ('suspended', 'Suspended'),
            ],
            'Status', readonly=True, track_visibility='onchange'),
    }

    _defaults = {
        'company_id': lambda s, cr, uid, c: s.pool.get('res.company')._company_default_get(cr, uid, 'hr.employee', context=c),
        'journal_id': _default_journal,
        'account_debit': _default_loan_account,
        'account_credit': _default_transfer_account,
        'date': fields.date.context_today,
        'currency_id': _get_currency,
        'nb_payments': 1,
        'is_advance': False,
        'state': 'draft',
        'employee_id': _employee_get,
        'user_id': lambda cr, uid, id, c={}: id,
    }

    def create(self, cr, uid, vals, context=None):
        if 'employee_id' in vals and vals['employee_id']:
            employee = self.pool.get('hr.employee').browse(cr, uid, [vals['employee_id']])[0]
            if not employee.address_home_id:
                raise osv.except_osv(
                    _('Could not create Loan !'),
                    _("Employee '%s' has no associated partner." % employee.name))
        if vals.get('name', '/') == '/':
            vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'hr.loan') or '/'
        vals['installment'] = vals['amount'] / vals['nb_payments']
        return super(hr_loan, self).create(cr, uid, vals, context=context)

    def copy(self, cr, uid, loan_id, default=None, context=None):
        default = default or {}
        default.update({
            'name': self.pool.get('ir.sequence').get(cr, uid, 'hr.loan') or '/',
            'balance': False,
            'payment_ids': [],
            'move_id': False,
        })
        return super(hr_loan, self).copy(cr, uid, loan_id, default, context=context)

    def unlink(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids, context=context):
            if rec.amount and rec.state not in ['draft', 'cancelled']:
                raise osv.except_osv(
                    _('Warning!'),
                    _('You must cancel the Loan before you can delete it.'))
        return super(hr_loan, self).unlink(cr, uid, ids, context)

    # TOOLS
    def loan_draft(self, cr, uid, ids, context=None):
        wf_service = netsvc.LocalService("workflow")
        for loan in self.browse(cr, uid, ids):
            wf_service.trg_delete(uid, 'hr.loan', loan.id, cr)
            wf_service.trg_create(uid, 'hr.loan', loan.id, cr)
        return self.write(cr, uid, ids, {'state': 'draft', 'date_valid': None, 'user_valid': None}, context=context)

    def loan_confirm(self, cr, uid, ids, context=None):
        for loan in self.browse(cr, uid, ids):
            if loan.is_advance:
                if loan.nb_payments > 1:
                    raise osv.except_osv(
                        _('Could not confirm Loan !'),
                        _('Not more than one installment for an advance.'))
            if loan.amount <= 0.0:
                raise osv.except_osv(
                    _('Could not confirm Loan !'),
                    _('Amount must be greater than zero.'))
            if loan.nb_payments < 0:
                raise osv.except_osv(
                    _('Could not confirm Loan !'),
                    _('You must set a Number of Payments'))
            if loan.employee_id and loan.employee_id.parent_id.user_id:
                self.message_subscribe_users(
                    cr,
                    uid,
                    [loan.id],
                    user_ids=[loan.employee_id.parent_id.user_id.id])
            date = time.strftime('%Y-%m-%d')
            if loan.date_confirm:
                date = loan.date_confirm
            self.write(cr, uid, ids, {'date_confirm': date}, context=context)
        return self.write(cr, uid, ids, {'state': 'confirm', }, context=context)

    def loan_validate(self, cr, uid, ids, context=None):
        for loan in self.browse(cr, uid, ids):
            date = time.strftime('%Y-%m-%d')
            if loan.date_valid:
                date = loan.date_valid
            self.write(cr, uid, ids, {'date_valid': date}, context=context)
        return self.write(
            cr,
            uid,
            ids,
            {'state': 'accepted', 'user_valid': uid},
            context=context)

    def clean_loan(self, cr, uid, ids, context=None):
        pay_obj = self.pool.get('hr.loan.payment')
        move_obj = self.pool.get('account.move')
        voucher_obj = self.pool.get('account.voucher')
        for loan in self.browse(cr, uid, ids, context=context):
            # Giveout
            if loan.voucher_id:
                voucher_obj.unlink(
                    cr,
                    uid,
                    [loan.voucher_id.id],
                    context=context)
            if loan.move_id:
                move_obj.unlink(
                    cr,
                    uid,
                    [loan.move_id.id],
                    context=context)
            # Payments
            if loan.payment_ids:
                l = [p.id for p in loan.payment_ids]
                pay_obj.unlink(cr, uid, l, context=context)
                self.write(
                    cr,
                    uid,
                    [loan.id],
                    {'payment_ids': []},
                    context=context)
            if loan.voucher_ids:
                l = [p.id for p in loan.voucher_ids]
                voucher_obj.unlink(cr, uid, l, context=context)
                self.write(
                    cr,
                    uid,
                    [loan.id],
                    {'voucher_ids': []},
                    context=context)
            if loan.move_ids:
                l = [p.id for p in loan.move_ids]
                move_obj.unlink(cr, uid, l, context=context)
                self.write(
                    cr,
                    uid,
                    [loan.id],
                    {'move_ids': []},
                    context=context)

    def loan_cancel(self, cr, uid, ids, context=None):
        for loan in self.browse(cr, uid, ids, context=context):
            if loan.payment_ids:
                raise osv.except_osv(
                    _('Cancel Error'),
                    _("Loan has some payslip payments.\nPlease cancel the payslips before proceeding."))
            if loan.voucher_ids:
                raise osv.except_osv(
                    _('Cancel Error'),
                    _("Loan has some spontaneous payments.\nPlease cancel/delete them before proceeding."))
        self.clean_loan(cr, uid, ids, context=context)
        return self.write(
            cr,
            uid,
            ids,
            {'state': 'cancelled'},
            context=context)

    def loan_suspend(self, cr, uid, ids, context=None):
        return self.write(
            cr,
            uid,
            ids,
            {'state': 'suspended'},
            context=context)

    def loan_resume(self, cr, uid, ids, context=None):
        return self.write(
            cr,
            uid,
            ids,
            {'state': 'waiting'},
            context=context)

    def loan_initiate(self, cr, uid, ids, context=None):
        self.action_receipt_create(cr, uid, ids, context)
        self.action_make_voucher(cr, uid, ids, context)
        return self.write(
            cr,
            uid,
            ids,
            {'state': 'waiting'},
            context=context)

    def loan_paid(self, cr, uid, ids, context=None):
        return self.write(
            cr,
            uid,
            ids,
            {'state': 'paid'},
            context=context)

    def condition_paid(self, cr, uid, ids, context=None):
        paid = True
        for loan in self.browse(cr, uid, ids, context=context):
            if loan.amount > 0:
                paid = False
            if loan.balance > 0:
                paid = False
        return paid


    def _create_move(self, cr, uid, loan_id, reference, credit_id, 
                    debit_id, date, amount, context=None):
        """return a move, given the variables."""
        ctx = dict(context or {}, account_period_prefer_normal=True)
        move_obj = self.pool.get('account.move')
        period_obj = self.pool.get('account.period')
        loan = self.browse(cr, uid, loan_id, context=ctx)
        company_id = loan.company_id.id
        period_id = period_obj.find(cr, uid, date, context=ctx)[0]

        move_id =  move_obj.create(
            cr, 
            uid, 
            move_obj.account_move_prepare(
                cr, 
                uid, 
                loan.journal_id.id, 
                date=date, 
                ref=reference, 
                company_id=company_id, 
                context=ctx),
            context=ctx)
            

        lml = []
        # create the debit move line
        lml.append({
                'partner_id': loan.employee_id.address_home_id.id,
                'name': loan.name,
                'debit': amount,
                'account_id': debit_id,
                'date_maturity': date,
                'period_id': period_id,
                })

        # create the credit move line
        lml.append({
                'partner_id': loan.employee_id.address_home_id.id,
                'name': loan.name,
                'credit': amount,
                'account_id': credit_id,
                'date_maturity': date,
                'period_id': period_id,
                })
        # convert eml into an osv-valid format
        lines = [(0, 0, x) for x in lml]
        move_obj.write(cr, uid, [move_id], {'line_id': lines}, context=ctx)
        # post the journal entry if 'Skip 'Draft' State for Manual Entries' is checked
        if loan.journal_id.entry_posted:
            move_obj.button_validate(cr, uid, [move_id], ctx)
        return move_id

    def _create_voucher(self, cr, uid, loan_id, move_id, journal_id, 
                        name, vtype, reference, date, amount, 
                        context=None):
        ctx = dict(context or {}, account_period_prefer_normal=True)
        CRDIR = {'in': 'cr', 'out':'dr'}
        TRDIR = {'in': 'receipt', 'out':'payment'}
        period_obj = self.pool.get('account.period')
        voucher_obj = self.pool.get('account.voucher')
        journal_obj = self.pool.get('account.journal')
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        move = move_obj.browse(cr, uid, move_id, context=ctx)
        loan = self.browse(cr, uid, loan_id, context=ctx)
        journal = journal_obj.browse(cr, uid, journal_id, context=ctx)
        company_id = loan.company_id.id
        period_id = period_obj.find(cr, uid, date, context=ctx)[0]
        account_id = journal.default_debit_account_id.id
        if vtype == 'in':
            account_id = journal.default_credit_account_id.id
        # prepare the voucher
        voucher = {
            'journal_id': journal_id,
            'company_id': company_id,
            'type': TRDIR.get(vtype),
            'name': name,
            'account_id': account_id,
            'reference': reference,
            'amount': amount > 0.0 and amount or 0.0,
            'date': date,
            'date_due': date,
            'period_id': period_id,
            }

        # Define the voucher line
        lml = []
        #order the lines by most old first
        mlids = [l.id for l in move.line_id]
        mlids.reverse()
        # Create voucher_lines
        account_move_lines = move_line_obj.browse(cr, uid, mlids, context=context)
        amount_unreconciled = amount
        for line_id in account_move_lines:
            if vtype == 'in' and line_id.credit:
                continue
            if vtype == 'out' and line_id.debit:
                continue
            account_id = line_id.account_id.id
            voucher['partner_id'] = line_id.partner_id.id
            amt = line_id.credit and line_id.credit or line_id.debit
            
            lml.append({
                'name': line_id.name,
                'move_line_id': line_id.id,
                'reconcile': (amt <= amount),
                'amount': amt < amount and amt or max(0, amount),
                'account_id': line_id.account_id.id,
                'type': CRDIR.get(vtype)
                })
            amount -= amt
        lines = [(0, 0, x) for x in lml]
        
                
        voucher['line_ids'] = lines
        voucher_id = voucher_obj.create(cr, uid, voucher, context=ctx)
        # validate now
        # this may be dangerous, but it is convenient
        voucher_obj.button_proforma_voucher(cr, uid, [voucher_id], context)
        return voucher_id

    def action_receipt_create(self, cr, uid, ids, context=None):
        """Create accounting entries for this loan"""
        ctx = dict(context or {}, account_period_prefer_normal=True)

        for loan in self.browse(cr, uid, ids, context=context):
            if loan.move_id:
                continue

            # create the move that will contain the accounting entries
            move_id = self._create_move(
                cr, 
                uid, 
                loan.id,
                loan.name,
                loan.account_credit.id,
                loan.account_debit.id,
                loan.date_valid,
                loan.amount,
                context=ctx)
                
            self.write(cr, uid, [loan.id], {'move_id': move_id}, context=ctx)

    def action_make_voucher(self, cr, uid, ids, context=None):
        ctx = dict(context or {}, account_period_prefer_normal=True)

        voucher_obj = self.pool.get('account.voucher')
        journal_obj = self.pool.get('account.journal')

        for loan in self.browse(cr, uid, ids, context=ctx):
            if loan.voucher_id:
                continue
            name = _('Loan %s to %s') % (loan.name, loan.employee_id.name)
            partner_id = loan.employee_id.address_home_id.id,
            journal = journal_obj.browse(cr, uid, ctx.get('paymethod_id'), context=context)
            amt = loan.amount
            
            voucher_id = self._create_voucher(
                cr, 
                uid, 
                loan.id, 
                loan.move_id.id, 
                journal.id, 
                name,
                'out', 
                ctx.get('reference', _('LOAN %s') % (loan.name)),
                loan.date_valid,
                loan.amount, 
                context=ctx)
                
            self.write(cr, uid, [loan.id], {'voucher_id': voucher_id}, context=ctx)


    def action_spontaneous_voucher(self, cr, uid, loan_id, context=None):
        """Create voucher for spontaneous payment"""
        ctx = dict(context or {}, account_period_prefer_normal=True)
        voucher_obj = self.pool.get('account.voucher')
        journal_obj = self.pool.get('account.journal')
        journal = journal_obj.browse(cr, uid, ctx.get('paymethod_id'), context=context)
        loan = self.browse(cr, uid, loan_id, context=ctx)[0]
        name = _('Payment on Loan %s from %s') % (loan.name, loan.employee_id.name)
        amount = ctx.get('amount')
        date = ctx.get('date')

        if amount > loan.balance:
            raise osv.except_osv(
                _('Amount error'),
                _("Spontaneous payment cannot exceed Loan balance"))

        move_id = self._create_move(
            cr, 
            uid, 
            loan.id, 
            ctx.get('reference', _('LOAN %s') % (loan.name)),
            loan.account_debit.id,
            loan.account_credit.id,
            date,
            amount,
            context=ctx)

        voucher_id = self._create_voucher(
            cr, 
            uid, 
            loan.id, 
            move_id, 
            journal.id, 
            name,
            'in', 
            ctx.get('reference', _('LOAN %s') % (loan.name)),
            date,
            amount, 
            context=ctx)
        vals = {
            'move_ids': [(4, move_id)],
            'voucher_ids': [(4, voucher_id)],
        }
        self.write(cr, uid, [loan.id], vals, context=ctx)
        
    def loan_give(self, cr, uid, ids, context=None):
        # only one loan at a time
        if not len(ids) == 1:
                raise osv.except_osv(
                    _('Concurrency Error'),
                    _("This tool can only be run for one Loan at a time!"))
        loan = self.browse(cr, uid, ids[0], context=context)
        if loan.move_id and loan.voucher_id:
            return self.loan_initiate(cr, uid, ids, context)
        if not loan.employee_id.address_home_id:
            raise osv.except_osv(
                _('Linked Partner Missing!'),
                _("Loan accounting requires '%s' to have a valid Home Adress!" % loan.employee_id.name))
        if not loan.account_debit:
            raise osv.except_osv(
                _('No Debit Account!'),
                _('You must select an account to debit for this loan'))
        if not loan.account_credit:
            raise osv.except_osv(
                _('No Transit Account!'),
                _('You must select an account to transit this loan by'))
        if not loan.journal_id:
            raise osv.except_osv(
                _('No Journal!'),
                _('You must select a journal to record this loan in'))

        dummy, view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'hr_loan', 'hr_loan_give_out_view')
        return {
            'name': _("Give out Loan"),
            'view_mode': 'form',
            'view_id': view_id,
            'view_type': 'form',
            'res_model': 'hr.loan.giveout',
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': context
        }

    def loan_spontaneous(self, cr, uid, ids, context=None):
        dummy, view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'hr_loan', 'hr_loan_spontaneous_view')

        return {
            'name': _("spontaneous Payment"),
            'view_mode': 'form',
            'view_id': view_id,
            'view_type': 'form',
            'res_model': 'hr.loan.spontaneous',
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': context
        }

    def print_slip(self, cr, uid, ids, context=None):
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'hr.loan.slip',
            'datas': {
                    'model': 'hr.loan',
                    'id': ids and ids[0] or False,
                    'ids': ids and ids or [],
                    'report_type': 'pdf'
                },
            'nodestroy': True
        }

hr_loan()


class hr_loan_giveout(osv.osv_memory):
    """
    This wizard create a payment voucher for the loan (give out the money)
    """

    _name = "hr.loan.giveout"
    _description = "Give out the Loan"

    _columns = {
        'paymethod_id': fields.many2one('account.journal', 'Payment method', required=True),
        'reference': fields.char(
            'Payment reference', 
            size=64, 
            required=True,
            help="Check number, or short memo"),
    }

    def give_out(self, cr, uid, ids, context=None):
        wf_service = netsvc.LocalService('workflow')
        if context is None:
            context = {}
        pool_obj = pooler.get_pool(cr.dbname)
        loan_obj = pool_obj.get('hr.loan')

        context.update({
            'paymethod_id': self.browse(cr, uid, ids)[0].paymethod_id.id,
            'reference': self.browse(cr, uid, ids)[0].reference,
            })

        loan_obj.loan_initiate(cr, uid, [context.get('active_id')], context=context)

        return {'type': 'ir.actions.act_window_close'}

hr_loan_giveout()

class hr_loan_spontaneous(osv.osv_memory):
    """
    This wizard create a payment voucher for the loan (give out the money)
    """

    _name = "hr.loan.spontaneous"
    _description = "spontaneous Loan Payment"

    _columns = {
        'paymethod_id': fields.many2one(
            'account.journal', 
            'Payment method', 
            required=True),
        'amount': fields.float(
            'Amount',
            digits_compute=dp.get_precision('Payroll'),
            required=True),
        'reference': fields.char(
            'Payment reference', 
            size=64, 
            help="Check number, or short memo"),
        'date': fields.date(
            'Payment Date',
            select=True,
            required=True),
    }

    def receive(self, cr, uid, ids, context=None):
        wf_service = netsvc.LocalService('workflow')
        if context is None:
            context = {}
        pool_obj = pooler.get_pool(cr.dbname)
        loan_obj = pool_obj.get('hr.loan')

        context.update({
            'date': self.browse(cr, uid, ids)[0].date,
            'amount': self.browse(cr, uid, ids)[0].amount,
            'paymethod_id': self.browse(cr, uid, ids)[0].paymethod_id.id,
            'reference': self.browse(cr, uid, ids)[0].reference,
            })

        loan_obj.action_spontaneous_voucher(cr, uid, [context.get('active_id')], context=context)

        return {'type': 'ir.actions.act_window_close'}

hr_loan_spontaneous()

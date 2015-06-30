import time

from datetime import datetime, date
from openerp import netsvc
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

    def _get_journal(self, cr, uid, context=None):
        if context is None:
            context = {}
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        company_id = context.get('company_id', user.company_id.id)
        journal_obj = self.pool.get('account.journal')
        domain = [('code', '=', 'MISC'), ('company_id', '=', company_id)]
        res = journal_obj.search(cr, uid, domain, limit=1)
        return res and res[0] or False

    def _get_currency(self, cr, uid, context=None):
        res = False
        journal_id = self._get_journal(cr, uid, context=context)
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

    def _get_loan_payments(self, cr, uid, ids, context=None):
        res = []
        for loan in self.browse(cr, uid, ids, context=context):
            res. extend([p.id for p in loan.payment_ids])
        return res

    def onchange_employee_id(self, cr, uid, ids, employee_id, context=None):
        emp_obj = self.pool.get('hr.employee')
        company_id = False
        if employee_id:
            employee = emp_obj.browse(cr, uid, employee_id, context=context)
            company_id = employee.company_id.id
        return {'value': {'company_id': company_id}}

    def onchange_amount(self, cr, uid, ids, amount, nb_payments, context=None):
        val = amount / nb_payments
        return {'value': {'installment': val}}

    def onchange_nb_payments(self, cr, uid, ids, amount, nb_payments, context=None):
        return self.onchange_amount(cr, uid, ids, amount, nb_payments, context=context)

    def _get_balance(self, cr, uid, ids, name, args, context):
        if not ids:
            return {}
        res = {}
        for loan in self.browse(cr, uid, ids, context=context):
            res[loan.id] = loan.amount - sum([payment.amount for payment in loan.payment_ids])
            if loan.move_id:
                self.write(cr, uid, ids, {'state': 'waiting'}, context=context)
            if res[loan.id] == 0.0:
                self.write(cr, uid, ids, {'state': 'paid'}, context=context)
        return res

    _columns = {
        'name' : fields.char('Name', size=64, select=True, readonly=True),
        'date' : fields.date('Date', required=True, select=True, readonly=True, states={'draft':[('readonly',False)], 'accepted':[('readonly',False)]}),
        'employee_id' : fields.many2one('hr.employee', 'Employee', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'user_id': fields.many2one('res.users', 'User', required=True),
        'notes' : fields.text('Justification', required=True, readonly=True, states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]}),
        'amount' : fields.float('Amount', digits_compute=dp.get_precision('Payroll'), required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'currency_id': fields.many2one('res.currency', 'Currency', required=True),
        'nb_payments': fields.integer("Number of payments", required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'installment' : fields.float('Due amount per payment', digits_compute=dp.get_precision('Payroll'), required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'payment_ids' : fields.one2many('hr.loan.payment', 'loan_id', 'Loan Payments'),
        'balance': fields.function(_get_balance, type='float', string='Balance', digits_compute=dp.get_precision('Payroll'),  store={
            _name: (lambda self, cr,uid,ids,c: ids, ['payment_ids',"amount"], 10),
            'hr.loan.payment': (_get_loan_from_payment, None,10)
            }),

        'journal_id': fields.many2one('account.journal', 'Journal', readonly=True, states={'accepted':[('readonly',False)]}, help = "The journal used to record loans."),
        'account_debit': fields.many2one('account.account', 'Debit Account', readonly=True, states={'accepted':[('readonly',False)]}, help="The account in which the loan will be recorded"),
        'account_credit': fields.many2one('account.account', 'Credit Account', readonly=True, states={'accepted':[('readonly',False)]}, help="The account in which the loan will be paid to the employee"),
        'move_id': fields.many2one('account.move', 'Ledger Posting'),
        'date_confirm': fields.date('Request Date', select=True, help="Date of the confirmation of the loan. It's filled when the button Submit is pressed."),
        'date_valid': fields.date('Validation Date', select=True, help="Date of the acceptation of the loan. It's filled when the button Accept is pressed."),
        'user_valid': fields.many2one('res.users', 'Validation By', readonly=True, states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]}),
        'company_id': fields.many2one('res.company', 'Company', required=True),
        'state': fields.selection([
                ('draft', 'New'),
                ('cancelled', 'Cancelled'),
                ('confirm', 'Waiting Approval'),
                ('accepted', 'Accepted'),
                ('waiting', 'Waiting Payment'),
                ('paid', 'Paid'),
                ('suspended', 'Suspended'),
                ],
                'Status', readonly=True, track_visibility='onchange',
                help=_('When the loan request is created the status is \'Draft\'.\n It is confirmed by the user and request is sent to admin, the status is \'Waiting Approval\'.\
                \nIf the admin accepts it, the status is \'Accepted\'.\n If the accounting entries are made for the loan request, the status is \'Waiting Payment\'.')),
    }

    _defaults = {
        'company_id': lambda s, cr, uid, c: s.pool.get('res.company')._company_default_get(cr, uid, 'hr.employee', context=c),
        'date': fields.date.context_today,
        'currency_id': _get_currency,
        'nb_payments': 3,
        'state': 'draft',
        'employee_id': _employee_get,
        'user_id': lambda cr, uid, id, c={}: id,
    }


    def create(self, cr, uid, vals, context=None):
        if 'employee_id' in vals and vals['employee_id']:
            employee = self.pool.get('hr.employee').browse(cr, uid, [vals['employee_id']])[0]
            if not employee.address_home_id :
              raise osv.except_osv(
                _('Could not create Loan !'),
                _("Employee '%s' has no associated partner." % employee.name))
        if vals.get('name','/') == '/':
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
            if rec.state not in ['draft','cancelled']:
                raise osv.except_osv(_('Warning!'),_('You must cancel the Loan before you can delete it.'))
        return super(hr_loan, self).unlink(cr, uid, ids, context)

    def loan_draft(self, cr, uid, ids, context=None):
        wf_service = netsvc.LocalService("workflow")
        for loan in self.browse(cr, uid, ids):
            wf_service.trg_delete(uid, 'hr.loan', loan.id, cr)
            wf_service.trg_create(uid, 'hr.loan', loan.id, cr)
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
        return self.write(cr, uid, ids, {'state': 'accepted', 'user_valid': uid}, context=context)

    def clean_loan(self, cr, uid, ids, context=None):
        pay_obj = self.pool.get('hr.loan.payment')
        move_obj = self.pool.get('account.move')
        for loan in self.browse(cr, uid, ids, context=context):
            if loan.move_id:
                move_obj.unlink(cr, uid, [loan.move_id.id], context=context)
            if loan.payment_ids:
                l = [p.id for p in loan.payment_ids]
                pay_obj.unlink(cr, uid, l, context=context)
                self.write(cr, uid, [loan.id], {'payment_ids': []}, context=context)

    def loan_cancel(self, cr, uid, ids, context=None):
        self.clean_loan(cr, uid, ids, context=context)
        return self.write(cr, uid, ids, {'state': 'cancelled'}, context=context)

    def loan_suspend(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'suspended'}, context=context)

    def loan_resume(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'waiting'}, context=context)

    def loan_initiate(self, cr, uid, ids, context=None):
        self.action_receipt_create(cr, uid, ids, context)
        return self.write(cr, uid, ids, {'state': 'waiting'}, context=context)

    def loan_paid(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'paid'}, context=context)

    def condition_paid(self, cr, uid, ids, context=None):
        ok = True
        for loan in self.browse(cr, uid, ids, context=context):
            if loan.balance > 0:
                ok = False
        return ok


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
        date = loan.date
        ref = loan.name
        journal_id = False
        if loan.journal_id:
            journal_id = loan.journal_id.id
        else:
            journal_id = journal_obj.search(cr, uid, [('code', '=', 'MISC'), ('company_id', '=', company_id)])
            if not journal_id:
                raise osv.except_osv(_('Error!'), _("No loan journal found. Please make sure you have a journal with type 'general' configured."))
            journal_id = journal_id[0]
        return self.pool.get('account.move').account_move_prepare(cr, uid, journal_id, date=date, ref=ref, company_id=company_id, context=context)

    def action_receipt_create(self, cr, uid, ids, context=None):
        """Create accounting entries for this loan"""
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        period_obj = self.pool.get('account.period')
        for loan in self.browse(cr, uid, ids, context=context):
            if loan.move_id:
                continue
            if not loan.employee_id.address_home_id:
                raise osv.except_osv(
                    _('Linked Partner Missing!'),
                    _("Loan accounting requires '%s' to have a valid Home Adress!" % loan.employee_id.name))
            if not loan.account_debit:
                raise osv.except_osv(_('Error!'), _('You must select an account to debit for this loan'))
            if not loan.account_credit:
                raise osv.except_osv(_('Error!'), _('You must select an account to credit for this loan'))

            #create the move that will contain the accounting entries
            move_id = move_obj.create(cr, uid, self.account_move_get(cr, uid, loan.id, context=context), context=context)
            period_id = period_obj.find(cr, uid, loan.date_valid, context=context)[0]

            lml = []
            # create the debit move line
            lml.append({
                    'partner_id': loan.employee_id.address_home_id.id,
                    'name': loan.name,
                    'debit': loan.amount,
                    'account_id': loan.account_debit.id,
                    'date_maturity': loan.date_valid,
                    'period_id': period_id,
                    })

            # create the credit move line
            lml.append({
                    'partner_id': loan.employee_id.address_home_id.id,
                    'name': loan.name,
                    'credit': loan.amount,
                    'account_id': loan.account_credit.id,
                    'date_maturity': loan.date_valid,
                    'period_id': period_id,
                    })
            #convert eml into an osv-valid format
            lines = [(0,0,x) for x in lml]
            journal_id = move_obj.browse(cr, uid, move_id, context).journal_id
            # post the journal entry if 'Skip 'Draft' State for Manual Entries' is checked
            if journal_id.entry_posted:
                move_obj.button_validate(cr, uid, [move_id], context)
            move_obj.write(cr, uid, [move_id], {'line_id': lines}, context=context)
            self.write(cr, uid, ids, {'move_id': move_id}, context=context)

    def action_view_receipt(self, cr, uid, ids, context=None):
        '''
        This function returns an action that display existing account.move of given loan ids.
        '''
        assert len(ids) == 1, 'This option should only be used for a single id at a time'
        loan = self.browse(cr, uid, ids[0], context=context)
        assert loan.move_id
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
            'res_id': loan.move_id.id,
        }
        return result

    def print_slip(self, cr, uid, ids, context=None):
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'hr.loan.slip',
            'datas': {
                    'model':'hr.loan',
                    'id': ids and ids[0] or False,
                    'ids': ids and ids or [],
                    'report_type': 'pdf'
                },
            'nodestroy': True
        }

hr_loan()

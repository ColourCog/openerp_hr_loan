#!/usr/bin/env python
# vim: set fileencoding=utf-8 :


from openerp.osv import osv, fields
import time
from datetime import datetime, date
from openerp.tools.translate import _
from tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
import decimal_precision as dp
import netsvc
import logging

_logger = logging.getLogger(__name__)


class hr_loan(osv.osv):
    _name = 'hr.loan' 
    _inherit = ['mail.thread', 'ir.needaction_mixin'] 
    _description = 'HR Loan Management' 
    _track = {
        'state': {
          'hr_expense.mt_expense_approved': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'accepted',
          'hr_expense.mt_expense_refused': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'cancelled',
          'hr_expense.mt_expense_confirmed': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'confirm',
        },
    }
  
  def _balance(self, cr, uid, ids, field_name, args, context=None): 
    res = {} 
    for record in self.browse(cr, uid, ids, context=context): 
      cr.execute('select sum(coalesce(total_amount, 0.0))::float from hr_expense_line where loan_id = %s' % (record.id)) 
      data = filter(None, map(lambda x:x[0], cr.fetchall())) or [0.0] 
      res[record.id] = { 
        'balance' : record.amount + data[0], 
        'paid' : not (record.amount + data[0]) > 0
      } 
    return res 
  
  def _get_loan_reimbursement_from_expense_lines(self, cr, uid, ids, context=None): 
    expense_line = {} 
    for line in self.pool.get('hr.expense.line').browse(cr, uid, ids, context=context): 
      expense_line[line.loan_id.id] = True 
      expense_line_ids = [] 
      if expense_line: 
        expense_line_ids = self.pool.get('hr.loan').search(cr, uid, [('id','in',expense_line.keys())], context=context) 
    return expense_line_ids 
  
  _columns = { 
    'name' : fields.char('Name', size=64, select=True, readonly=True), 
    'description' : fields.char('Description', size=128, select=True, required=True, readonly=True, 
                  states={'draft':[('readonly',False)], 'approved':[('readonly',False)]}), 
    'date' : fields.date('Date', required=True, select=True, readonly=True, 
                  states={'draft':[('readonly',False)], 'approved':[('readonly',False)]}), 
    'employee_id' : fields.many2one('hr.employee', 'Employee', 
                  required=True, 
                  #~ domain=[('hr.employee.category', '=', 'employee')] , 
                  readonly=True, 
                  states={'draft':[('readonly',False)], 
    'approved':[('readonly',False)]}), 
    'expense_line_ids' : fields.one2many('hr.expense.line', 'loan_id', 
                  'Expense Line', readonly=True), 
    'state' : fields.selection([ 
                  ('draft', 'Draft'), 
                  ('approved', 'Approved'), 
                  ('confirmed', 'Confirmed'), 
                  ('closed', 'Closed'), 
                  ('cancel', 'Cancelled') ], 
                  'State', 
                  readonly=True, 
                  help="State of the Driver Loan. ", 
                  select=True), 
    'reimbursement_method' : fields.selection([ 
                  ('weekly', 'Weekly'), 
                  ('fortnightly', 'Fortnightly'), 
                  ('monthly', 'Monthly'), ], 
                  'Reimbursement Method', 
                  readonly=True, 
                  states={'draft':[('readonly',False)], 
                  'approved':[('readonly',False)]}, 
                  help="""Select Loan Recovery Method:
                    - Weekly: Reimbursement will be applied every week, considering only 4 weeks in each month
                    - Fortnightly: Reimbursement will be applied forthnightly, considering only 2 reimbursement in each month, applied the 14th and 28th day of the month.
                    - Monthy: Reimbursement will be applied only once a month, applied the 28th day of the month. . """, 
                  select=True, 
                  required=True),

    'reimbursement_type' : fields.selection([
                  ('fixed', 'Fixed'), 
                  ('percent', 'Loan Percentage'), ], 
                  'Reimbursement Type', 
                  readonly=True, 
                  states={'draft':[('readonly',False)], 'approved':[('readonly',False)]}, 
                  required=True, 
                  help="""Select Loan Recovery Type:
                    - Fixed: Reimbursement will a fixed amount
                    - Percent: Reimbursement will be a percentage of total Loan Amount """, 
                  select=True),

    'notes' : fields.text('Notes'), 
    'origin' : fields.char('Source Document', size=64, 
                  help="Reference of the document that generated this Expense Record", 
                  readonly=True, 
                  states={
                    'draft':[('readonly',False)], 
                    'approved':[('readonly',False)]}), 
    'amount' : fields.float(
                  'Amount', 
                  digits_compute=dp.get_precision('Sale Price'), 
                  required=True, 
                  readonly=True, 
                  states={
                    'draft':[('readonly',False)], 
                    'approved':[('readonly',False)]
                  }), 
    'percent_reimbursement' : fields.float(
                  'Percent (%)', 
                  digits_compute=dp.get_precision('Sale Price'), 
                  required=False, 
                  help="Please set percent as 10.00%", 
                  readonly=True, 
                  states={
                    'draft':[('readonly',False)], 
                    'approved':[('readonly',False)]
                  }), 
    'fixed_reimbursement' : fields.float(
                  'Fixed Reimbursement', 
                  digits_compute=dp.get_precision('Sale Price'), 
                  required=False, 
                  readonly=True, 
                  states={
                    'draft':[('readonly',False)], 
                    'approved':[('readonly',False)]
                  }), 
    'balance' : fields.function(
                  _balance, 
                  method=True, 
                  digits_compute=dp.get_precision('Sale Price'), 
                  string='Balance', 
                  type='float', 
                  multi=True, 
                  store={ 
                    'hr.loan': (
                      lambda self, cr, uid, ids, c={}: 
                        ids, ['notes', 'amount','state','expense_line_ids'], 10), 
                    'hr.expense.line': (
                      _get_loan_reimbursement_from_expense_lines, 
                      ['product_uom_qty', 'price_unit'], 
                      10), 
                    }), 
                    #store = {'hr.expense.line': (_get_loan_reimbursement_from_expense_lines, None, 50)}), 
    'paid' : fields.function(
                  _balance, 
                  method=True, 
                  string='Paid', 
                  type='boolean', 
                  multi=True, 
                  store={ 
                    'hr.loan': (
                      lambda self, cr, uid, ids, c={}: 
                        ids, ['notes','amount','state','expense_line_ids'], 10), 
                    'hr.expense.line': (
                      _get_loan_reimbursement_from_expense_lines, 
                      ['product_uom_qty', 'price_unit'], 10), }), 
                  #store = {'hr.expense.line': (_get_loan_reimbursement_from_expense_lines, None, 50)}), 
    'product_id' : fields.many2one(
                  'product.product', 
                  'Reimbursement Product', 
                  readonly=True, 
                  states={
                    'draft':[('readonly',False)], 
                    'approved':[('readonly',False)]
                    }, 
                  required=True, 
                  #~ domain=[('hr.employee.category', '=', ('salary_reimbursement'))], 
                  ondelete='restrict'), 
    #'shop_id' : fields.related('employee_id', 'shop_id', type='many2one', relation='sale.shop', string='Shop', store=True, readonly=True), 
    'company_id' : fields.related(
                  'shop_id', 
                  'company_id', 
                  type='many2one', 
                  relation='res.company', 
                  string='Company', 
                  store=True, 
                  readonly=True), 
    'create_uid' : fields.many2one('res.users', 'Created by', readonly=True), 
    'create_date' : fields.datetime('Creation Date', readonly=True, select=True), 
    'cancelled_by' : fields.many2one('res.users', 'Cancelled by', readonly=True), 
    'date_cancelled': fields.datetime('Date Cancelled', readonly=True), 
    'approved_by' : fields.many2one('res.users', 'Approved by', readonly=True), 
    'date_approved' : fields.datetime('Date Approved', readonly=True), 
    'confirmed_by' : fields.many2one('res.users', 'Confirmed by', readonly=True), 
    'date_confirmed': fields.datetime('Date Confirmed', readonly=True), 
    'closed_by' : fields.many2one('res.users', 'Closed by', readonly=True), 
    'date_closed' : fields.datetime('Date Closed', readonly=True),
  }

  _defaults = {
    'date' : lambda *a: time.strftime(DEFAULT_SERVER_DATE_FORMAT), 
    'state' : lambda *a: 'draft',
  }

  _sql_constraints = [
    (
      'name_uniq', 
      'unique(name)', 
      'Loan record must be unique !'
    ),
  ]

  def create(self, cr, uid, vals, context=None):
    values = vals 
    if 'employee_id' in vals and vals['employee_id']: 
      employee = self.pool.get('hr.employee').browse(cr, uid, [vals['employee_id']])[0] 
      if vals.get('name','/') == '/':
            vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'hr.loan') or '/'
    return super(hr_loan, self).create(cr, uid, vals, context=context)

  def action_approve(self, cr, uid, ids, context=None):
    for rec in self.browse(cr, uid, ids, context=context): 
      if rec.amount <= 0.0: 
        raise osv.except_osv( 
          _('Could not approve Loan !'), 
          _('Amount must be greater than zero.')) 
      self.write(cr, uid, ids, {
                  'state':'approved', 
                  'approved_by' : uid,
                  'date_approved':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                  }) 
      for (id,name) in self.name_get(cr, uid, ids): 
        message = _("Loan '%s' is set to Approved.") % name 
        self.log(cr, uid, id, message) 
    return True

  def action_confirm(self, cr, uid, ids, context=None):
    for rec in self.browse(cr, uid, ids, context=context): 
      self.write(cr, uid, ids, {
                  'state':'confirmed', 
                  'confirmed_by' : uid,
                  'date_confirmed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                  }) 
      for (id,name) in self.name_get(cr, uid, ids): 
        message = _("Loan '%s' is set to Confirmed.") % name 
        self.log(cr, uid, id, message) 
    return True

  def action_cancel(self, cr, uid, ids, context=None):
    for rec in self.browse(cr, uid, ids, context=context): 
      self.write(cr, uid, ids, {
                  'state':'cancel', 
                  'cancelled_by' : uid,
                  'date_cancelled':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)}) 
      for (id,name) in self.name_get(cr, uid, ids): 
        message = _("Loan '%s' is set to Cancel.") % name 
        self.log(cr, uid, id, message) 
    return True

  def action_close(self, cr, uid, ids, context=None):
    for rec in self.browse(cr, uid, ids, context=context): 
      self.write(cr, uid, ids, {
                  'state':'closed', 
                  'closed_by' : uid,
                  'date_closed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                  }) 
      for (id,name) in self.name_get(cr, uid, ids): 
        message = _("Loan '%s' is set to Closed even when it is not paid.") % name if rec.balance > 0.0 else _("Loan '%s' is set to Closed.") % name 
        self.log(cr, uid, id, message) 
    return True

  def get_loan_reimbursement(self, cr, uid, employee_id, expense_id, context=None):
    expense_line_obj = self.pool.get('hr.expense.line') 
    expense_obj = self.pool.get('hr.expense') 
    res = expense_line_obj.search(
                  cr, uid, [
                            ('expense_id', '=', expense_id),
                            ('control','=', 1),
                            ('loan_id','!=',False)]) 
    print "res: ", res 
    if len(res): 
      loan_ids = [] 
      expense_line_ids = [] 
      for x in expense_obj.browse(cr, uid, [expense_id])[0].expense_line: 
        if x.loan_id.id: 
          loan_ids.append(x.loan_id.id) 
          expense_line_ids.append(x.id) 
      if len(loan_ids): 
        expense_line_obj.unlink(cr, uid, expense_line_ids) 
        self.write(cr, uid,loan_ids, {'state':'confirmed', 'closed_by' : False, 'date_closed':False} ) 
        prod_obj = self.pool.get('product.product') 
        loan_ids = self.search(cr, uid, [('employee_id', '=', employee_id),('state','=','confirmed'),('balance', '>', 0.0)]) 
        for rec in self.browse(cr, uid, loan_ids, context=context): 
          cr.execute('select date from hr_expense_line where loan_id = %s order by date desc limit 1' % (rec.id)) 
          data = filter(None, map(lambda x:x[0], cr.fetchall())) 
          date = data[0] if data else rec.date 
          date_liq = expense_obj.read(cr, uid, [expense_id], ['date'])[0]['date'] 
          print "date_liq: ", date_liq 
          dur = datetime.strptime(date_liq, '%Y-%m-%d') - datetime.strptime(date, '%Y-%m-%d') 
          product = prod_obj.browse(cr, uid, [rec.product_id.id])[0] 
          xfactor = 7 if rec.reimbursement_method == 'weekly' else 14.0 if rec.reimbursement_method == 'fortnightly' else 28.0 
          rango = 1 if not int(dur.days / xfactor) else int(dur.days / xfactor) + 1 
          balance = rec.balance 
          while rango and balance: 
            rango -= 1 
            reimbursement = rec.fixed_reimbursement if rec.reimbursement_type == 'fixed' else rec.amount *rec.percent_reimbursement / 100.0 
            reimbursement = balance if reimbursement > balance else reimbursement 
            balance -= reimbursement 
            xline = { 
              'expense_id' : expense_id, 
              'line_type' : product_category, 
              'name' : product.name + ' - ' + rec.name, 
              'sequence' : 100, 
              'product_id' : product.id, 
              'product_uom' : product.uom_id.id, 
              'product_uom_qty' : 1, 
              'price_unit' : reimbursement * -1.0, 
              'control' : True, 
              'loan_id' : rec.id, 
            } 
            res = expense_line_obj.create(cr, uid, xline) 
            if reimbursement >= rec.balance: 
              self.write(
                cr, 
                uid, 
                [rec.id], 
                {
                  'state':'closed', 
                  'closed_by' :uid,
                  'date_closed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                }) 
              for (id,name) in self.name_get(cr, uid, [rec.id]): 
                message = _("Loan '%s' has been Closed.") % rec.name 
                self.log(cr, uid, id, message) 
              return

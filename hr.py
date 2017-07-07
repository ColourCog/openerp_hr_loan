#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
#  hr_employee.py
#


from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

class hr_employee(osv.osv):
    _inherit = "hr.employee"
    def _calculate_total_loan(self, cr, uid, ids, name, args, context):
        if not ids: return {}
        res = {}
        for employee in self.browse(cr, uid, ids, context=context):
            if not employee.loan_ids:
                res[employee.id] = {'due': 0.0}
                continue
            cr.execute( 'SELECT SUM(balance) '\
                        'FROM hr_loan '\
                        'WHERE employee_id = %s '\
                        'AND state != %s',
                         (employee.id, 'paid'))
            result = dict(cr.dictfetchone())
            res[employee.id] = {'basic': result['sum']}
        return res
    _columns = {
        "loan_ids": fields.one2many("hr.loan", "employee_id", "Loans"),
        'total_loan': fields.function(_calculate_total_loan, method=True, type='float', string='Total Pending Loans', digits_compute=dp.get_precision('Payroll'), help="Sum of all loans of employee."),
    }

    def copy(self, cr, uid, employee_id, default=None, context=None):
        default = default or {}
        default.update({
            'loan_ids': [],
        })
        return super(hr_employee, self).copy(cr, uid, employee_id, default, context=context)


hr_employee()


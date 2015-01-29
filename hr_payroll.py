#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
#  hr_payroll.py
#  


from openerp.osv import fields, osv
from openerp.tools.translate import _


class hr_payslip(osv.osv):
    _inherit = "hr.payslip"

    def process_sheet(self, cr, uid, ids, context=None):
        obj_hr_loan = self.pool.get('hr.loan')
        for slip in self.browse(cr, uid, ids, context=context):
            for loan in slip.employee_id.loan_ids:
                if loan.state == "done":
                    obj_hr_loan.decrease_balance(cr, uid, [loan.id], context)
        return super(hr_payslip, self).process_sheet(cr, uid, [slip.id], context=context)

    def cancel_sheet(self, cr, uid, ids, context=None):
        obj_hr_loan = self.pool.get('hr.loan')
        for slip in self.browse(cr, uid, ids, context=context):
            if slip.state == "done":
                for loan in slip.employee_id.loan_ids:
                    if loan.state in ["done","paid"]:
                        obj_hr_loan.increase_balance(cr, uid, [loan.id], context)
        return super(hr_payslip, self).cancel_sheet(cr, uid, ids, context=context)

hr_payslip()


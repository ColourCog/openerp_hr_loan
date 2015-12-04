#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
#  hr_payroll.py
#


from openerp.osv import fields, osv


class hr_payslip(osv.osv):
    _inherit = "hr.payslip"

    def process_sheet(self, cr, uid, ids, context=None):
        pay_obj = self.pool.get('hr.loan.payment')
        for slip in self.browse(cr, uid, ids, context=context):
            for loan in slip.employee_id.loan_ids:
                if loan.state == 'waiting' and loan.date_valid < slip.date_to:
                    payment = {
                        'loan_id': loan.id,
                        'slip_id': slip.id,
                        'amount': loan.balance > loan.installment and loan.installment or loan.balance,
                    }
                    pay_obj.create(cr, uid, payment, context=context)
        return super(hr_payslip, self).process_sheet(cr, uid, ids, context=context)

    def cancel_sheet(self, cr, uid, ids, context=None):
        pay_obj = self.pool.get('hr.loan.payment')
        res = []
        for slip in self.browse(cr, uid, ids, context=context):
            for loan in slip.employee_id.loan_ids:
                res.extend([p.id for p in loan.payment_ids if p.slip_id.id == slip.id])
        pay_obj.unlink(cr, uid, res, context=context)
        return super(hr_payslip, self).cancel_sheet(cr, uid, ids, context=context)

hr_payslip()

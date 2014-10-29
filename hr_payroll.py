#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
#  hr_payroll.py
#  


from openerp.osv import fields, osv
from openerp.tools.translate import _

#TODO: 
# create custom salary rule in data.xml using installments
# salary rule should be able to generate journal entries crediting
# the (OHADA) asset account used from the (OHADA) salary expense account
# using the employee name and loan name as reference

# trigger balance calculation on payslip validation 'only'
# loan visual feedback in payslip interfaceSS

class hr_payslip(osv.osv):
    _inherit = "hr.payslip"

    def process_sheet(self, cr, uid, ids, context=None):
        obj_hr_loan = self.pool.get('hr.loan')
        for ps in self.browse(cr, uid, ids, context=context):
            for loan in ps.employee_id.loan_ids:
                if loan.state == "done":
                    obj_hr_loan.decrease_balance(cr, uid, [loan.id], context)
        return self.write(cr, uid, ids, {'paid': True, 'state': 'done'}, context)

    def unlink(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids, context=context):
            if rec.state != 'draft':
                raise osv.except_osv(_('Warning!'),_('You can only delete draft expenses!'))
        return super(hr_payslip, self).unlink(cr, uid, ids, context)

hr_payslip()


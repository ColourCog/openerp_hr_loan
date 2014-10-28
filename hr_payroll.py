#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
#  hr_employee.py
#  


from openerp.osv import fields, osv
from openerp.tools.translate import _

#TODO: 
# create custom salary rule in data.xml using installments
# create reimbursment function using 
# trigger balance calculation on payslip validation 'only'
# loan visual feedback in payslip interfaceSS

class hr_payroll(osv.osv):
    _inherit = "hr.payroll"

hr_payroll()


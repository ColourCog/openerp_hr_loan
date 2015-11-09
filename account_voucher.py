# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

class account_voucher(osv.osv):
    _inherit='account.voucher'
    _name='account.voucher'

    _columns = {
        'loan_id': fields.many2one('hr.loan', 'Loan'),
    }

account_voucher()

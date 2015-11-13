# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

class account_move(osv.osv):
    _inherit='account.move'
    _name='account.move'

    _columns = {
        'loan_id': fields.many2one('hr.loan', 'Loan'),
    }

account_move()

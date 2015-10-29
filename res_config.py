# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Business Applications
#    Copyright (C) 2004-2012 OpenERP S.A. (<http://openerp.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.tools.translate import _
from openerp.osv import fields, osv

class res_company(osv.osv):
    _inherit = "res.company"

    _columns = {
        'default_loan_transfer_account_id': fields.many2one('account.account',
            'The transfer account when creating loans'),
        'default_loan_account_id': fields.many2one('account.account',
            'The loan account to use by default'),
        'default_advance_account_id': fields.many2one('account.account',
            'The advance account to use by default'),
        'default_loan_journal_id': fields.many2one('account.journal',
            'The journal to use by default'),
    }

res_company()

class hr_config_settings(osv.osv_memory):
    _inherit = 'hr.config.settings'

    _columns = {
        'company_id': fields.many2one('res.company', 'Company', required=True),

        'default_loan_transfer_account_id': fields.related(
            'company_id',
            'default_loan_transfer_account_id',
            type='many2one',
            relation='account.account',
            string="Loans/Advances Transfer Account"),
        'default_loan_account_id': fields.related(
            'company_id',
            'default_loan_account_id',
            type='many2one',
            relation='account.account',
            string="Loans Account"),
        'default_advance_account_id': fields.related(
            'company_id',
            'default_advance_account_id',
            type='many2one',
            relation='account.account',
            string="Advances Account"),
        'default_loan_journal_id': fields.related(
            'company_id',
            'default_loan_journal_id',
            type='many2one',
            relation='account.journal',
            string="Loans/Advances Journal"),
    }

    def _default_company(self, cr, uid, context=None):
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        return user.company_id.id

    _defaults = {
        'company_id': _default_company,
    }

    def create(self, cr, uid, values, context=None):
        id = super(hr_config_settings, self).create(cr, uid, values, context)
        # Hack: to avoid some nasty bug, related fields are not written upon record creation.
        # Hence we write on those fields here.
        vals = {}
        for fname, field in self._columns.iteritems():
            if isinstance(field, fields.related) and fname in values:
                vals[fname] = values[fname]
        self.write(cr, uid, [id], vals, context)
        return id

    def onchange_company_id(self, cr, uid, ids, company_id, context=None):
        # update related fields
        values = {
            'default_loan_transfer_account_id': False,
            'default_loan_account_id': False,
            'default_advance_account_id': False,
            'default_loan_journal_id': False,
        }
        if company_id:
            company = self.pool.get('res.company').browse(cr, uid, company_id, context=context)
            values.update({
                'default_loan_transfer_account_id': company.default_loan_transfer_account_id and company.default_loan_transfer_account_id.id,
                'default_loan_account_id': company.default_loan_account_id and company.default_loan_account_id.id,
                'default_advance_account_id': company.default_advance_account_id and company.default_advance_account_id.id,
                'default_loan_journal_id': company.default_loan_journal_id and company.default_loan_journal_id.id,
            })
        return {'value': values}

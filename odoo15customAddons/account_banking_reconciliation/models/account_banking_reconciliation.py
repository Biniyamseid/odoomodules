# -*- coding: utf-8 -*-
# Copyright (C) 2015 Ursa Information Systems (http://www.ursainfosystems.com>)
# Copyright (C) 2011 NovaPoint Group LLC (<http://www.novapointgroup.com>)
# Copyright (C) 2004-2010 OpenERP SA (<http://www.openerp.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from datetime import timedelta
import time

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp
from operator import itemgetter
from odoo.tools.float_utils import float_round
import logging
_logger = logging.getLogger(__name__)


class BankAccRecStatement(models.Model):

    @api.model
    def create(self, vals):
        _logger.info(
            "OOOOOOOOOOOOOOOOOOOOOOOOOPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP   89999999999999")
        # account_move_line_obj = self.env['account.move.line']
        _logger.info(vals)
        # Prevent manually adding new statement line.
        # This would allow only onchange method to pre-populate statement lines
        # # based on the filter rules.
        # if not vals.get('move_line_id', False):
        #     raise UserError(_(
        #         "You cannot add any new bank statement line manually "
        #         "as of this revision!"))
        # account_move_line_obj.browse([vals['move_line_id']]).write(
        #     {'draft_assigned_to_statement': True})

        return super(BankAccRecStatement, self).create(vals)

    def check_group(self):
        """Check if following security constraints are implemented for groups:
        Bank Statement Preparer– they can create, view and delete any of the
        Bank Statements provided the Bank Statement is not in the DONE state,
        or the Ready for Review state.
        Bank Statement Verifier – they can create, view, edit, and delete any
        of the Bank Statements information at any time.
        NOTE: DONE Bank Statements  are only allowed to be deleted by a
        Bank Statement Verifier."""
        model_data_obj = self.env['ir.model.data']
        res_groups_obj = self.env['res.groups']
        # group_verifier_id = model_data_obj._get_id(
        #     'account_banking_reconciliation',
        #     'group_bank_stmt_verifier')
        # _logger.info("here")
        group_verifier_id = model_data_obj.sudo().search([("name","=",	"Bank Statement Verifier")],limit=1).id
        # _logger.info("here 2")

        for statement in self:
            if group_verifier_id:
                res_id = model_data_obj.browse(group_verifier_id).res_id
                group_verifier = res_groups_obj.browse([res_id])
                group_user_ids = [user.id for user in group_verifier.users]
                if statement.state != 'draft' \
                        and self.env.uid not in group_user_ids:
                    raise UserError(_("Only a member of '%s' "
                                      "group may delete/edit "
                                      "bank statements when not in draft "
                                      "state!" % (group_verifier.name)))
        return True

    def copy(self, default=None):
        for rec in self:
            if default is None:
                default = {}
            if 'name' not in default:
                default['name'] = _("%s (copy)") % rec.name
        return super(BankAccRecStatement, self).copy(default=default)
        # _logger.info("POOOOOOOOOOOOOOOOOOOOOOOOOOO copy")
        # self.ensure_one()
        # if default is None:
        #     default = {}
        # default.update({'credit_move_line_ids': [],
        #                 'debit_move_line_ids': [],
        #                 'name': ''})
        # return super(BankAccRecStatement, self).copy(default=default)

    def write(self, vals):
        # Check if the user is allowed to perform the action
        _logger.info("write")
        self.check_group()
        _logger.info(vals)
        return super(BankAccRecStatement, self).write(vals)

    @api.model
    def unlink(self):
        """Reset the related account.move.line to be re-assigned later
        to statement."""
        self.check__group()  # Check if user is allowed to perform the action
        # for statement in self:
        #     statement_lines = \
        #         statement.credit_move_line_ids + statement.debit_move_line_ids
        #     statement_lines.unlink()  # call unlink method to reset
        return super(BankAccRecStatement, self).unlink()

    def check_difference_balance(self):
        # Check if difference balance is zero or not.
        for statement in self:

            if statement.cleared_balance_cur:
                if statement.difference_cur != 0.0:
                    raise UserError(_("Prior to reconciling a statement, "
                                      "all differences must be accounted for "
                                      "and the Difference balance must be "
                                      "zero. Please review "
                                      "and make necessary changes."))
            else:
                if statement.difference != 0.0:
                    raise UserError(_("Prior to reconciling a statement, "
                                      "all differences must be accounted for "
                                      "and the Difference balance must "
                                      "be zero. Please review "
                                      "and make necessary changes."))
        return True

    def action_cancel(self):
        """Cancel the the statement."""
        self.write({'state': 'cancel'})
        for statement in self:
            statement_lines = \
                statement.credit_move_line_ids + statement.debit_move_line_ids
            line_ids = []
            for statement_line in statement_lines:
                if statement_line.move_line_id:
                    # Find move lines related to statement lines
                    line_ids.append(statement_line.move_line_id.id)
            # Reset 'Cleared' and 'Bank Acc Rec Statement ID' to False
            self.env['account.move.line'].browse(line_ids).write(
                {'cleared_bank_account': False,
                 'bank_acc_rec_statement_id': False})

            # Reset 'Cleared' in statement lines
            statement_lines.write({'cleared_bank_account': False,
                                   'research_required': False})

        self._compute_get_balance()

        return True

    def action_review(self):
        """Change the status of statement from 'draft' to 'to_be_reviewed'."""
        _logger.info(
            "PPPPPPPPPPO        ************************************************      ACTION REVIEW")
        # If difference balance not zero prevent further processing
        self.check_difference_balance()

        self.write({'state': 'to_be_reviewed'})
        return True

    def action_process(self):
        """Set the account move lines as 'Cleared' and
        Assign 'Bank Acc Rec Statement ID'
        for the statement lines which are marked as 'Cleared'."""
        _logger.info(
            "OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOLLLLLLLLLLLLLLLLLLLLLLL")
        # If difference balance not zero prevent further processing
        self.check_difference_balance()
        for statement in self:
            statement_lines = \
                statement.credit_move_line_ids + statement.debit_move_line_ids
            for statement_line in statement_lines:
                # Mark the move lines as 'Cleared'mand assign
                # the 'Bank Acc Rec Statement ID'
                statement_id = \
                    statement_line.cleared_bank_account and \
                    statement.id or False
                cleared_bank_account = \
                    statement_line.cleared_bank_account
                statement_line.move_line_id.write({
                    'cleared_bank_account': cleared_bank_account,
                    'bank_acc_rec_statement_id': statement_id})

            statement.write({'state': 'done',
                             'verified_by_user_id': self.env.uid,
                             'verified_date': time.strftime('%Y-%m-%d')})
        return True

    def action_cancel_draft(self):
        """Reset the statement to draft and perform resetting operations."""
        for statement in self:
            statement_lines = \
                statement.credit_move_line_ids + statement.debit_move_line_ids
            line_ids = []
            for statement_line in statement_lines:
                if statement_line.move_line_id:
                    # Find move lines related to statement lines
                    line_ids.append(statement_line.move_line_id.id)
            # Reset 'Cleared' and 'Bank Acc Rec Statement ID' to False
            # self.env['account.move.line'].browse(line_ids).write(
            #     {'cleared_bank_account': False,
            #      'bank_acc_rec_statement_id': False})

            # Reset 'Cleared' in statement lines
            # statement_lines.write({'cleared_bank_account': False,
            #                        'research_required': False})
            # Reset statement
            statement.write({'state': 'draft',
                             'verified_by_user_id': False,
                             'verified_date': False})
            self._compute_get_balance()
        return True

    def action_select_all(self):
        """Mark all the statement lines as 'Cleared'."""
        _logger.info(
            "OPPPPPPPPPPJJJJJJJJJJKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK")
        _logger.info(self)
        for statement in self:
            statement_lines = \
                statement.credit_move_line_ids + statement.debit_move_line_ids
            statement_lines.write({'cleared_bank_account': True})
            _logger.info(statement_lines)
        return True

    def action_unselect_all(self):
        """Reset 'Cleared' in all the statement lines."""
        for statement in self:
            _logger.info(f"***********************************statements*****")
            _logger.info(statement)
            _logger.info(f"***********************************statements*****")
            statement_lines = \
                statement.credit_move_line_ids + statement.debit_move_line_ids
            statement_lines.write({'cleared_bank_account': False})
        return True

    def _compute_get_balance(self):
        """Computed as following:
        A) Deposits, Credits, and Interest Amount:
        Total SUM of Amts of lines with Cleared = True
        Deposits, Credits, and Interest # of Items:
        Total of number of lines with Cleared = True
        B) Checks, Withdrawals, Debits, and Service Charges Amount:
        Checks, Withdrawals, Debits, and Service Charges Amount # of Items:
        Cleared Balance (Total Sum of the Deposit Amount Cleared (A) –
        Total Sum of Checks Amount Cleared (B))
        Difference= (Ending Balance – Beginning Balance) - cleared balance =
        should be zero.
        """
        account_precision = self.env['decimal.precision'].precision_get(
            'Account')
        if not self.starting_date:
                    self.starting_date = self.ending_date - timedelta(days=30)
        _logger.info("*********************************************** 1")
        for statement in self:
            statement.sum_of_credits_lines = 0.0
            statement.sum_of_credits = 0.0
            statement.sum_of_credits_cur = 0.0
            statement.sum_of_credits_lines = 0.0
            statement.sum_of_ucredits = 0.0
            statement.sum_of_ucredits_cur = 0.0
            statement.sum_of_ucredits_lines = 0.0
            statement.sum_of_debits = 0.0
            statement.sum_of_debits_cur = 0.0
            statement.sum_of_debits_lines = 0.0
            statement.sum_of_udebits = 0.0
            statement.sum_of_udebits_cur = 0.0
            statement.sum_of_udebits_lines = 0.0
            statement.cleared_balance = 0.0
            statement.cleared_balance_cur = 0.0
            statement.difference = 0.0
            statement.difference_cur = 0.0
            statement.uncleared_balance = 0.0
            statement.uncleared_balance_cur = 0.0
            _logger.info("*********************************************** 2")
            _logger.info(statement.credit_move_line_ids)
            _logger.info(statement.debit_move_line_ids)
            if len(statement.credit_move_line_ids) != 0:
                for line in statement.credit_move_line_ids:
                    if not (line.date >= statement.starting_date and line.date <= statement.ending_date):
                        continue

                    _logger.info(
                        "*********************************************** 3")
                    statement.sum_of_credits += \
                        line.cleared_bank_account and \
                        float_round(line.amount, account_precision) or 0.0
                    statement.sum_of_credits_cur += \
                        line.cleared_bank_account and \
                        float_round(line.amountcur, account_precision) or 0.0
                    statement.sum_of_credits_lines += \
                        line.cleared_bank_account and 1.0 or 0.0
                    statement.sum_of_ucredits += \
                        (not line.cleared_bank_account) and \
                        float_round(line.amount, account_precision) or 0.0
                    statement.sum_of_ucredits_cur += \
                        (not line.cleared_bank_account) and \
                        float_round(line.amountcur, account_precision) or 0.0
                    statement.sum_of_ucredits_lines += \
                        (not line.cleared_bank_account) and 1.0 or 0.0
            else:
                statement.sum_of_credits += 0.0
                statement.sum_of_credits_cur += 0.0
                statement.sum_of_credits_lines += 0.0
                statement.sum_of_ucredits += 0.0
                statement.sum_of_ucredits_cur += 0.0
                statement.sum_of_ucredits_lines += 0.0
            if len(statement.debit_move_line_ids) != 0:
                for line in statement.debit_move_line_ids:
                    if not (line.date >= statement.starting_date and line.date <= statement.ending_date):
                        continue
                    _logger.info(
                        "*********************************************** 4")
                    statement.sum_of_debits += \
                        line.cleared_bank_account and \
                        float_round(line.amount, account_precision) or 0.0
                    statement.sum_of_debits_cur += \
                        line.cleared_bank_account and \
                        float_round(line.amountcur, account_precision) or 0.0
                    _logger.info(
                        "***********************************************")
                    statement.sum_of_debits_lines += \
                        line.cleared_bank_account and 1.0 or 0.0
                    _logger.info("*****************************************")
                    statement.sum_of_udebits += \
                        (not line.cleared_bank_account) and \
                        float_round(line.amount, account_precision) or 0.0
                    statement.sum_of_udebits_cur += \
                        (not line.cleared_bank_account) and \
                        float_round(line.amountcur, account_precision) or 0.0
                    statement.sum_of_udebits_lines += \
                        (not line.cleared_bank_account) and 1.0 or 0.0
            else:
                statement.sum_of_debits += 0.0
                statement.sum_of_debits_cur += 0.0
                _logger.info("***********************************************")
                statement.sum_of_debits_lines += 0.0
                _logger.info("*****************************************")
                statement.sum_of_udebits += 0.0
                statement.sum_of_udebits_cur += 0.0
                statement.sum_of_udebits_lines += 0.0

            statement.cleared_balance = float_round(
                statement.sum_of_debits - statement.sum_of_credits,
                account_precision)
            statement.cleared_balance_cur = float_round(
                statement.sum_of_debits_cur - statement.sum_of_credits_cur,
                account_precision)
            statement.difference = \
                float_round((statement.ending_balance -
                             statement.starting_balance) -
                            statement.cleared_balance, account_precision)
            statement.difference_cur = \
                float_round((statement.ending_balance -
                             statement.starting_balance) -
                            statement.cleared_balance_cur, account_precision)
            statement.uncleared_balance = float_round(
                statement.sum_of_udebits - statement.sum_of_ucredits,
                account_precision)
            statement.uncleared_balance_cur = float_round(
                statement.sum_of_udebits_cur - statement.sum_of_ucredits_cur,
                account_precision)

            # statement.sum_of_debits += 0.0
            # statement.sum_of_debits_cur += 0.0
            # _logger.info("***********************************************")
            # statement.sum_of_debits_lines += 0.0
            # _logger.info("*****************************************")
            # statement.sum_of_udebits += 0.0
            # statement.sum_of_udebits_cur += 0.0
            # statement.sum_of_udebits_lines += 0.0
            # statement.sum_of_credits += 0.0
            # statement.sum_of_credits_cur += 0.0
            # statement.sum_of_credits_lines += 0.0
            # statement.sum_of_ucredits += 0.0
            # statement.sum_of_ucredits_cur += 0.0
            # statement.sum_of_ucredits_lines += 0.0

    # refresh data

    def refresh_record(self):
        retval = True
        refdict = {}
        _logger.info("kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk")
        # get current state of moves in the statement
        for statement in self:

            if statement.state == 'draft':
                for cr_item in statement.credit_move_line_ids:
                    if cr_item.move_line_id and cr_item.cleared_bank_account:
                        refdict[cr_item.move_line_id.id] = \
                            cr_item.cleared_bank_account

                for dr_item in statement.debit_move_line_ids:
                    if dr_item.move_line_id and dr_item.cleared_bank_account:
                        refdict[dr_item.move_line_id.id] = \
                            dr_item.cleared_bank_account

        # for the statement
        for statement in self:

            # process only if the statement is in draft state
            if statement.state == 'draft':
                vals = statement.change_lines_for_refresh()
                # list of credit lines
                outlist = []
                for cr_item in vals['value']['credit_move_line_ids']:
                    _logger.info(cr_item)
                    _logger.info(cr_item)
                    cr_item['cleared_bank_account'] = refdict and refdict.get(
                        cr_item['move_line_id'], False) or False
                    cr_item['research_required'] = False

                    item = [0, False, cr_item]
                    outlist.append(item)

                # list of debit lines
                inlist = []
                for dr_item in vals['value']['debit_move_line_ids']:
                    _logger.info(dr_item)
                    _logger.info(dr_item)
                    dr_item['cleared_bank_account'] = refdict and refdict.get(
                        dr_item['move_line_id'], False) or False
                    dr_item['research_required'] = False

                    item = [0, False, dr_item]
                    inlist.append(item)

                # write it to the record so it is visible on the form
                retval = self.write(
                    {'last_ending_date': vals['value']['last_ending_date'],
                     'starting_balance': vals['value']['starting_balance'],
                     'credit_move_line_ids': outlist,
                     'debit_move_line_ids': inlist})

        self._compute_get_balance()

        return retval

    # get starting balance for the account

    def get_starting_balance(self, account_id, ending_date):

        result = (False, 0.0)
        reslist = []
        statement_obj = self.env['bank.acc.rec.statement']
        domain = [('account_id', '=', account_id), ('state', '=', 'done')]
        # statement_ids = statement_obj.search(domain).ids

        # get all statements for this account in the past
        # for statement in statement_obj.browse(statement_ids):
        for statement in statement_obj.search(domain):
            if statement.ending_date < ending_date:
                reslist.append(
                    (statement.ending_date, statement.ending_balance))

        # get the latest statement value
        if len(reslist):
            reslist = sorted(reslist, key=itemgetter(0))
            result = reslist[len(reslist) - 1]

        return result

    def change_lines_for_refresh(self): 
        _logger.info(
            "OPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP 1")
        account_move_line_obj = self.env['account.move.line']
        statement_line_obj = self.env['bank.acc.rec.statement.line']
        _logger.info(
            "OPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP 2")
        val = {
            'value': {'debit_move_line_ids': [], 'credit_move_line_ids': []}}  # , 'move_line_ids': [(5, 0, 0)]}}
        for rec in self:
            if rec.account_id:
                _logger.info(
                    "OPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP 3")
                # for statement in self:
                # _logger.info(
                #     "OPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP 4")
                statement_line_ids = statement_line_obj.search(
                    ['|', ('credit_statement_id', '=', rec.id), ('debit_statement_id', '=', rec.id)])
                # call unlink method to reset and
                # remove existing statement lines and
                # mark reset field values in related move lines
                _logger.info(statement_line_ids)
                _logger.info(rec)
                for s in statement_line_ids:
                    _logger.info(s.name)
                    _logger.info(s.move_line_id)
                statement_line_ids.unlink()

                # Apply filter on move lines to allow
                # 1. credit and debit side journal items in posted state of
                # the selected GL account
                # 2. Journal items which are not cleared in
                # previous bank statements
                # 3. Date less than or equal to ending date provided the
                # 'Suppress Ending Date Filter' is not checkec
                domain = [('account_id', '=', rec.account_id.id),
                          ('move_id.state', '=', 'posted'),
                          '|',
                          ('cleared_bank_account', '=', False),
                          ('bank_acc_rec_statement_id', '=', rec.id)
                          ]
                if not rec.starting_date:
                    rec.starting_date = rec.ending_date - timedelta(days=30)
                domain += [('date', '>=', rec.starting_date)]
                if not self.suppress_ending_date_filter:
                    domain += [('date', '<=', rec.ending_date)]
                # line_ids = account_move_line_obj.search(domain).ids
                count = 0
                # for line in account_move_line_obj.browse(line_ids):
                _logger.info(domain)
                for line in account_move_line_obj.search(domain):
                    count += 1
                    amount_currency = (line.amount_currency < 0) and (
                        -1 * line.amount_currency) or line.amount_currency
                    res = {
                        # line.move_name,  # line.ref,
                        'ref': "ref" + str(count),
                        'date': line.date,
                        'partner_id': line.partner_id.id,
                        'currency_id': line.currency_id.id,
                        'amount': line.credit or line.debit,
                        'amountcur': amount_currency,
                        'name': "ref" + str(count),  # line.move_name,
                        'move_line_id': line.id,
                        'type': line.credit and 'cr' or 'dr',
                    }
                    _logger.info(res)
                    _logger.info(count)
                    _logger.info(
                        "OPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP 5")
                    if res['type'] == 'cr':
                        val['value']['credit_move_line_ids'].append(
                            res)
                    else:
                        val['value']['debit_move_line_ids'].append(
                            res)
                    # val['value']['move_line_ids'].append((0, 0, res))

                # look for previous statement for the account to
                # pull ending balance as starting balance
                prev_stmt = self.get_starting_balance(rec.account_id.id,
                                                      rec.ending_date)
                # rec.last_ending_date = prev_stmt[0]
                # rec.starting_balance = prev_stmt[1]
                # rec.credit_move_line_ids = val['value']['credit_move_line_ids']
                # rec.last_ending_date = prev_stmt[0]
                # rec.debit_move_line_ids = val['value']['debit_move_line_ids']
                # rec.move_line_ids = val['value']['move_line_ids']
                # rec.debit_move_line_ids = val['value']['debit_move_line_ids']
                val['value']['last_ending_date'] = prev_stmt[0]
                val['value']['starting_balance'] = prev_stmt[1]
            _logger.info(
                "OPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP 6")
            _logger.info(val)
        return val

    @api.onchange('account_id', 'ending_date', 'suppress_ending_date_filter')
    def onchange_account_id(self):
        _logger.info(
            "OPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP 1")
        account_move_line_obj = self.env['account.move.line']
        statement_line_obj = self.env['bank.acc.rec.statement.line']
        _logger.info(
            "OPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP 2")
        val = {
            'value': {'debit_move_line_ids': [(5, 0, 0)], 'credit_move_line_ids': [(5, 0, 0)]}}  # , 'move_line_ids': [(5, 0, 0)]}}
        for rec in self:
            if rec.account_id:
                _logger.info(
                    "OPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP 3")
                # for statement in self:
                # _logger.info(
                #     "OPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP 4")
                statement_line_ids = statement_line_obj.search(
                    ['|', ('credit_statement_id', '=', rec.id), ('debit_statement_id', '=', rec.id)])
                # call unlink method to reset and
                # remove existing statement lines and
                # mark reset field values in related move lines
                _logger.info(statement_line_ids)
                _logger.info(rec)
                for s in statement_line_ids:
                    _logger.info(s.name)
                    _logger.info(s.move_line_id)
                statement_line_ids.unlink()

                # Apply filter on move lines to allow
                # 1. credit and debit side journal items in posted state of
                # the selected GL account
                # 2. Journal items which are not cleared in
                # previous bank statements
                # 3. Date less than or equal to ending date provided the
                # 'Suppress Ending Date Filter' is not checkec
                domain = [('account_id', '=', rec.account_id.id),
                          ('move_id.state', '=', 'posted'),
                          '|',
                          ('cleared_bank_account', '=', False),
                          ('bank_acc_rec_statement_id', '=', rec.id)
                          ]
                if not rec.starting_date:
                    rec.starting_date = rec.ending_date - timedelta(days=30)
                domain += [('date', '>=', rec.starting_date)]
                if not self.suppress_ending_date_filter:
                    domain += [('date', '<=', rec.ending_date)]
                # line_ids = account_move_line_obj.search(domain).ids
                count = 0
                # for line in account_move_line_obj.browse(line_ids):
                _logger.info(domain)
                for line in account_move_line_obj.search(domain):
                    count += 1
                    amount_currency = (line.amount_currency < 0) and (
                        -1 * line.amount_currency) or line.amount_currency
                    res = {
                        # line.move_name,  # line.ref,
                        'ref': "ref" + str(count),
                        'date': line.date,
                        'partner_id': line.partner_id.id,
                        'currency_id': line.currency_id.id,
                        'amount': line.credit or line.debit,
                        'amountcur': amount_currency,
                        'name': "ref" + str(count),  # line.move_name,
                        'move_line_id': line.id,
                        'type': line.credit and 'cr' or 'dr',
                    }
                    _logger.info(res)
                    _logger.info(count)
                    _logger.info(
                        "OPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP 5")
                    if res['type'] == 'cr':
                        val['value']['credit_move_line_ids'].append(
                            (0, 0, res))
                    else:
                        val['value']['debit_move_line_ids'].append(
                            (0, 0, res))
                    # val['value']['move_line_ids'].append((0, 0, res))

                # look for previous statement for the account to
                # pull ending balance as starting balance
                prev_stmt = self.get_starting_balance(rec.account_id.id,
                                                      rec.ending_date)
                # rec.last_ending_date = prev_stmt[0]
                # rec.starting_balance = prev_stmt[1]
                # rec.credit_move_line_ids = val['value']['credit_move_line_ids']
                # rec.last_ending_date = prev_stmt[0]
                # rec.debit_move_line_ids = val['value']['debit_move_line_ids']
                # rec.move_line_ids = val['value']['move_line_ids']
                # rec.debit_move_line_ids = val['value']['debit_move_line_ids']
                val['value']['last_ending_date'] = prev_stmt[0]
                val['value']['starting_balance'] = prev_stmt[1]
            _logger.info(
                "OPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP 6")
            _logger.info(val)
        return val

    # @api.onchange('move_line_ids')
    # def onchange_move_lines(self):
    #     _logger.info("Move changed")
    #     cr_array = []
    #     db_array = []
    #     for rec in self:
    #         for r in rec.move_line_ids:
    #             _logger.info(r)
    #             _logger.info(r[0])
    #             if r[0].type == 'cr':
    #                 cr_array.append((4, r[0].id))
    #             else:
    #                 db_array.append((4, r[0].id))

    #     # val['value']['credit_move_line_ids']
    #     rec.credit_move_line_ids = cr_array
        # rec.debit_move_line_ids = db_array

    # @api.onchange('credit_move_line_ids')
    # def onchange_debit_lines(self):
    #     _logger.info("Move changed")
    #     cr_array = []
    #     db_array = []
    #     for rec in self:
    #         for r in rec.move_line_ids:
    #             _logger.info(r)
    #             _logger.info(r[0])
    #             if r[0].type == 'cr':
    #                 cr_array.append((4, r[0].id))
    #             else:
    #                 db_array.append((4, r[0].id))

    #     # val['value']['credit_move_line_ids']
    #     # rec.credit_move_line_ids = cr_array
    #     rec.debit_move_line_ids = db_array

    def get_default_company_id(self):
        # _logger.info("coming here")
        # _logger.info(self.env['res.users'].browse([self.env.uid]).company_id.id)
        return self.env['res.users'].browse([self.env.uid]).company_id.id

    _name = "bank.acc.rec.statement"
    name = fields.Char('Name', required=True, size=64,
                       states={'done': [('readonly', True)]},
                       help="This is a unique name identifying "
                            "the statement (e.g. Bank X January 2012).")
    account_id = fields.Many2one('account.account', 'Account', required=True,
                                 states={'done': [('readonly', True)]},
                                 domain="[('company_id', '=', company_id)]",
                                 help="The Bank/Gl Account that is being "
                                      "reconciled.")
    ending_date = fields.Date('Ending Date', required=True,
                              states={'done': [('readonly', True)]},
                              default=time.strftime('%Y-%m-%d'),
                              help="The ending date of your bank statement.")
    starting_date = fields.Date('Starting Date',
                                states={'done': [('readonly', True)]},
                                default=lambda self: self._get_default_starting_date())


    last_ending_date = fields.Date('Last Stmt Date',
                                   help="The previous statement date "
                                        "of your bank statement.")
    starting_balance = fields.Float('Starting Balance', required=True,
                                    digits=dp.get_precision('Account'),
                                    help="The Starting Balance on your "
                                         "bank statement.",
                                    states={'done': [('readonly', True)]})
    ending_balance = fields.Float('Ending Balance', required=True,
                                  digits=dp.get_precision('Account'),
                                  help="The Ending Balance on your "
                                       "bank statement.",
                                  states={'done': [('readonly', True)]})
    company_id = fields.Many2one('res.company', 'Company', required=True,
                                 readonly=True, default=get_default_company_id,
                                 help="The Company for which the "
                                      "deposit ticket is made to")
    notes = fields.Text('Notes')
    verified_date = fields.Date('Verified Date',
                                states={'done': [('readonly', True)]},
                                help="Date in which Deposit "
                                     "Ticket was verified.")
    verified_by_user_id = fields.Many2one('res.users', 'Verified By',
                                          states={
                                              'done': [('readonly', True)]},
                                          help="Entered automatically by "
                                               "the “last user” who saved it. "
                                               "System generated.")
    credit_move_line_ids = fields.One2many('bank.acc.rec.statement.line',
                                           'credit_statement_id', 'Credits',
                                           #    domain=[('type', '=', 'cr')],
                                           states={
                                               'done': [('readonly', True)]})
    debit_move_line_ids = fields.One2many('bank.acc.rec.statement.line',
                                          'debit_statement_id', 'Debits',
                                          #   domain=[('type', '=', 'dr')],
                                          states={
                                              'done': [('readonly', True)]})
    # move_line_ids = fields.One2many(
    #     'bank.acc.rec.statement.line', 'statement_id', 'Move Lines')
    cleared_balance = fields.Float(compute='_compute_get_balance',
                                   string='Cleared Balance',
                                   digits=dp.get_precision('Account'),
                                   help="Total Sum of the Deposit Amount "
                                        "Cleared – Total Sum of Checks, "
                                        "Withdrawals, Debits, and Service "
                                        "Charges Amount Cleared")
    difference = fields.Float(compute='_compute_get_balance',
                              string='Difference',
                              digits=dp.get_precision('Account'),
                              help="(Ending Balance – Beginning Balance) - "
                                   "Cleared Balance.")
    cleared_balance_cur = fields.Float(compute='_compute_get_balance',
                                       string='Cleared Balance (Cur)',
                                       digits=dp.get_precision('Account'),
                                       help="Total Sum of the Deposit "
                                            "Amount Cleared – Total Sum of "
                                            "Checks, Withdrawals, Debits, and"
                                            " Service Charges Amount Cleared")
    difference_cur = fields.Float(compute='_compute_get_balance',
                                  string='Difference (Cur)',
                                  digits=dp.get_precision('Account'),
                                  help="(Ending Balance – Beginning Balance)"
                                       " - Cleared Balance.")
    uncleared_balance = fields.Float(compute='_compute_get_balance',
                                     string='Uncleared Balance',
                                     digits=dp.get_precision('Account'),
                                     help="Total Sum of the Deposit "
                                          "Amount Uncleared – Total Sum of "
                                          "Checks, Withdrawals, Debits, and"
                                          " Service Charges Amount Uncleared")
    uncleared_balance_cur = fields.Float(compute='_compute_get_balance',
                                         string='Unleared Balance (Cur)',
                                         digits=dp.get_precision('Account'),
                                         help="Total Sum of the Deposit Amount"
                                              " Uncleared – Total Sum of "
                                              "Checks, Withdrawals, Debits, "
                                              "and Service Charges "
                                              "Amount Uncleared")
    sum_of_credits = fields.Float(compute='_compute_get_balance',
                                  string='Checks, Withdrawals, Debits, and'
                                         ' Service Charges Amount',
                                  digits=dp.get_precision('Account'),
                                  #   type='float',
                                  help="Total SUM of Amts of lines with"
                                       " Cleared = True")
    sum_of_debits = fields.Float(compute='_compute_get_balance',
                                 string='Deposits, Credits, and '
                                        'Interest Amount',
                                 digits=dp.get_precision('Account'),
                                 help="Total SUM of Amts of lines with "
                                      "Cleared = True")
    sum_of_credits_cur = fields.Float(compute='_compute_get_balance',
                                      string='Checks, Withdrawals, Debits, and'
                                             ' Service Charges Amount (Cur)',
                                      digits=dp.get_precision('Account'),
                                      help="Total SUM of Amts of lines "
                                           "with Cleared = True")
    sum_of_debits_cur = fields.Float(compute='_compute_get_balance',
                                     string='Deposits, Credits, and '
                                            'Interest Amount (Cur)',
                                     digits=dp.get_precision('Account'),
                                     help="Total SUM of Amts of lines "
                                          "with Cleared = True")
    sum_of_credits_lines = fields.Float(compute='_compute_get_balance',
                                        string='Checks, Withdrawals, Debits, '
                                               'and Service Charges # of '
                                               'Items',
                                        help="Total of number of lines with "
                                             "Cleared = True")
    sum_of_debits_lines = fields.Float(compute='_compute_get_balance',
                                       string='Deposits, Credits, and Interest'
                                              ' # of Items',
                                       help="Total of number of lines with"
                                            " Cleared = True")
    sum_of_ucredits = fields.Float(compute='_compute_get_balance',
                                   string='Uncleared - Checks, Withdrawals, '
                                          'Debits, and Service Charges Amount',
                                   digits=dp.get_precision('Account'),
                                   help="Total SUM of Amts of lines with "
                                        "Cleared = False")
    sum_of_udebits = fields.Float(compute='_compute_get_balance',
                                  string='Uncleared - Deposits, Credits, '
                                         'and Interest Amount',
                                  digits=dp.get_precision('Account'),
                                  help="Total SUM of Amts of lines with "
                                       "Cleared = False")
    sum_of_ucredits_cur = fields.Float(compute='_compute_get_balance',
                                       string='Uncleared - Checks, '
                                              'Withdrawals, Debits, and '
                                              'Service Charges Amount (Cur)',
                                       digits=dp.get_precision('Account'),
                                       help="Total SUM of Amts of lines "
                                            "with Cleared = False")
    sum_of_udebits_cur = fields.Float(compute='_compute_get_balance',
                                      string='Uncleared - Deposits, Credits, '
                                             'and Interest Amount (Cur)',
                                      digits=dp.get_precision('Account'),
                                      help="Total SUM of Amts of lines with"
                                           " Cleared = False")
    sum_of_ucredits_lines = fields.Float(compute='_compute_get_balance',
                                         string='Uncleared - Checks, '
                                                'Withdrawals, Debits, and '
                                                'Service Charges # of Items',
                                         help="Total of number of lines with"
                                              " Cleared = False")
    sum_of_udebits_lines = fields.Float(compute='_compute_get_balance',
                                        string='Uncleared - Deposits, Credits,'
                                               ' and Interest # of Items',
                                        help="Total of number of lines "
                                             "with Cleared = False")
    suppress_ending_date_filter = fields.Boolean('Remove Ending Date Filter',
                                                 help="If this is checked then"
                                                      " the Statement End Date"
                                                      " filter on the "
                                                      "transactions below will"
                                                      " not occur. All "
                                                      "transactions would "
                                                      "come over.")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_be_reviewed', 'Ready for Review'),
        ('done', 'Done'),
        ('cancel', 'Cancel')
    ], 'State', index=True, readonly=True, default='draft')

    _order = "ending_date desc"
    _sql_constraints = [
        ('name_company_uniq', 'unique (name, company_id, account_id)',
         'The name of the statement must be unique per '
         'company and G/L account!')
    ]
    
    @api.model
    def _get_default_starting_date(self):
        if self.ending_date:
            return fields.Date.to_string(fields.Date.from_string(self.ending_date) - timedelta(days=30))
        else:
            return None
        return fields.Date.to_string(fields.Date.from_string(self.ending_date) - timedelta(days=30))

    # methods2
    def get_line_details(self):
        _logger.info(
            "get_line_details")
        account_move_line_obj = self.env['account.move.line']
        statement_line_obj = self.env['bank.acc.rec.statement.line']
        _logger.info(
            "get_line_details ")
        val = {
            'value': {'debit_move_line_ids': [(5, 0, 0)], 'credit_move_line_ids': [(5, 0, 0)]}}  # , 'move_line_ids': [(5, 0, 0)]}}
        for rec in self:
            if rec.account_id:
                _logger.info("get_line_details")
                statement_line_ids = statement_line_obj.search(
                    ['|', ('credit_statement_id', '=', rec.id), ('debit_statement_id', '=', rec.id)])
                _logger.info(statement_line_ids)
                _logger.info(rec)
                for s in statement_line_ids:
                    _logger.info(s.name)
                    _logger.info(s.move_line_id)

        return val


    def explore_all_properties_of_rec(self):
        account_move_line = self.env['account.move.line']
        statement_line_obj = self.env['bank.acc.rec.statement.line']
        for rec in self:
            _logger.info(f"*****************explore properties")
            _logger.info(rec)
    def get_deposit_in_transit(self):
        account_move_line = self.env['account.move.line']
        statement_line_obj = self.env['bank.acc.rec.statement.line']
        other_debits_in_transit = 0
        receivable = 0
        interest_earned = 0
        error_on_check_debit = 0
        error_on_check_credit = 0
        nfs_check = 0
        service_charge_expense = 0
        deposit_in_transit = 0
        for rec in self:
            _logger.info(f"////////////////////////////////////////////////////////////////////////////////")
            _logger.info(f"*****************explore properties")
            _logger.info(rec)

        _logger.info("get_line_details")
        account_move_line_obj = self.env['account.move.line']
        statement_line_obj = self.env['bank.acc.rec.statement.line']
        _logger.info(
            "get_line_details ")
        val = {
            'value': {'debit_move_line_ids': [(5, 0, 0)], 'credit_move_line_ids': [(5, 0, 0)]}}  # , 'move_line_ids': [(5, 0, 0)]}}
        for rec in self:
            if rec.account_id:
                _logger.info("get_line_details")
                statement_line_ids = statement_line_obj.search(
                    ['|', ('credit_statement_id', '=', rec.id), ('debit_statement_id', '=', rec.id)])
                _logger.info(statement_line_ids)
                _logger.info(rec)
                for s in statement_line_ids:
                    _logger.info(s.name)
                    _logger.info(s.move_line_id)
                    # want to get all properties of the instance
                    move_line = s.move_line_id
                    _logger.info(f"||||||||||||||||||all details of move_line ||||||||||||||||||||||||||||")
                    _logger.info(move_line.read()[0])
                    #get target strings
                    _logger.info(f"get target strings")


                    # Calculate the date that is 30 days before rec.ending_date
                    _logger.info(f"last ending date{self.last_ending_date}")
                    if not self.last_ending_date or rec.last_ending_date == self.ending_date:
                        start_date = rec.ending_date - timedelta(days=30)
                    else:
                        start_date = rec.last_ending_date

                    # Search for records where the ref field contains the target_string, the date is between start_date and rec.ending_date, and the account_id is self.account_id.id
                    if not rec.starting_date:
                        rec.starting_date = rec.ending_date - timedelta(days=30)
                    
                    target_string_interest='interest earned'
                    # Search for records where the ref or display_name field contains the target_string
                    # matching_records = move_line.search([('ref', 'ilike', target_string),('date', '<=', rec.ending_date),('account_id', '=', self.account_id.id)])
                    matching_records = move_line.search([
                        ('ref', 'ilike', target_string_interest),
                        ('date', '>=', rec.starting_date),
                        ('date', '<=', rec.ending_date),
                        ('account_id', '=', self.account_id.id)
                    ])
                    for record in matching_records:
                        _logger.info(record.name)
                        _logger.info(record.debit)

                    # Sum up the debit field of these records
                    total_debit = sum(record.debit for record in matching_records)
                    interest_earned = total_debit
                    _logger.info(f"interest earned {total_debit}")

                    #calculate receivable
                    target_string_receivable='receivable collected by bank'
                    # Search for records where the ref or display_name field contains the target_string
                    # matching_records = move_line.search([('ref', 'ilike', target_string),('date', '<=', rec.ending_date),('account_id', '=', self.account_id.id)])
                    matching_records = move_line.search([
                        ('ref', 'ilike', target_string_receivable),
                        ('date', '>=', rec.starting_date),
                        ('date', '<=', rec.ending_date),
                        ('account_id', '=', self.account_id.id)
                    ])
                    for record in matching_records:
                        _logger.info(record.name)
                        _logger.info(record.debit)

                    # Sum up the debit field of these records
                    total_receivable = sum(record.debit for record in matching_records)
                    receivable = total_receivable


                    # calculate error on check debit
                    target_string_error='error on check'
                    # Search for records where the ref or display_name field contains the target_string
                    # matching_records = move_line.search([('ref', 'ilike', target_string),('date', '<=', rec.ending_date),('account_id', '=', self.account_id.id)])
                    matching_records = move_line.search([
                        ('ref', 'ilike', target_string_error),
                        ('date', '>=', rec.starting_date),
                        ('date', '<=', rec.ending_date),
                        ('account_id', '=', self.account_id.id)
                    ])
                    for record in matching_records:
                        _logger.info(record.name)
                        _logger.info(record.debit)

                    # Sum up the debit field of these records
                    total = sum(record.debit for record in matching_records)
                    error_on_check_debit = total

                    # calculate error on check credit
                    target_string_error='error on check'
                    # Search for records where the ref or display_name field contains the target_string
                    # matching_records = move_line.search([('ref', 'ilike', target_string),('date', '<=', rec.ending_date),('account_id', '=', self.account_id.id)])
                    matching_records = move_line.search([
                        ('ref', 'ilike', target_string_error),
                        ('date', '>=', start_date),
                        ('date', '<=', rec.ending_date),
                        ('account_id', '=', self.account_id.id)
                    ])
                    for record in matching_records:
                        _logger.info(record.name)
                        _logger.info(record.debit)

                    # Sum up the debit field of these records
                    total = sum(record.credit for record in matching_records)
                    error_on_check_credit = total
                    

                    # calculate NFS check
                    target_string_nfs='NFS check'
                    # Search for records where the ref or display_name field contains the target_string
                    # matching_records = move_line.search([('ref', 'ilike', target_string),('date', '<=', rec.ending_date),('account_id', '=', self.account_id.id)])
                    matching_records = move_line.search([
                        ('ref', 'ilike', target_string_nfs),
                        ('date', '>=', rec.starting_date),
                        ('date', '<=', rec.ending_date),
                        ('account_id', '=', self.account_id.id)
                    ])
                    for record in matching_records:
                        _logger.info(record.name)
                        _logger.info(record.debit)

                    # Sum up the debit field of these records
                    total = sum(record.credit for record in matching_records)
                    nfs_check = total

                    #calculate service charges credit

                    target_string_service=['service charge expense','service charge']
                    # Search for records where the ref or display_name field contains the target_string
                    # matching_records = move_line.search([('ref', 'ilike', target_string),('date', '<=', rec.ending_date),('account_id', '=', self.account_id.id)])
                    matching_records = move_line.search([
                        ('ref', 'in', target_string_service),
                        ('date', '>=', rec.starting_date),
                        ('date', '<=', rec.ending_date),
                        ('account_id', '=', self.account_id.id)
                    ])
                    for record in matching_records:
                        _logger.info(record.name)
                        _logger.info(record.credit)

                    # Sum up the debit field of these records
                    total = sum(record.credit for record in matching_records)
                    service_charge_expense = total


                    #calculate other_debits_in_transit
                    # calculate error on check credit
                    target_string=['receivable collected by bank','interest earned']
                    # Search for records where the ref or display_name field contains the target_string
                    # matching_records = move_line.search([('ref', 'ilike', target_string),('date', '<=', rec.ending_date),('account_id', '=', self.account_id.id)])

                    matching_records = move_line.search([
                        ('ref', 'in', target_string),
                        ('date', '=', rec.ending_date),
                        ('account_id', '=', self.account_id.id)
                    ])
                    for record in matching_records:
                        _logger.info(record.name)
                        _logger.info(record.debit)

                    # Sum up the debit field of these records
                    total = sum(record.debit for record in matching_records)
                    other_debits_in_transit = total

                

        # fields_info = self.env['account.move.line'].fields_get()
        fields_info = self.env['bank.acc.rec.statement.line'].fields_get()
        _logger.info(f"fields info")
        _logger.info(fields_info)
        for i in fields_info:
            _logger.info(i)
            print(i)
            # field_name, field_attrs = i
            # print("Field Name:", field_name)
            # _logger.info("                       ")
            # print("Field Attributes:", field_attrs)
            # print("-----")
        # self.ensure_one()
        domain = [
            ('date', '=', self.ending_date),
            ('account_id', '=', self.account_id.id),
        ]
        move_lines = self.env['account.move.line'].search(domain)
        depositInTransit = sum(line.debit for line in move_lines)
        depositInTransit = depositInTransit if depositInTransit is not None else 0.0
        return {
        'receivable': receivable,
        'interest_earned': interest_earned,
        'error_on_check_debit': error_on_check_debit,
        'error_on_check_credit': error_on_check_credit,
        'nfs_check': nfs_check,
        'service_charge_expense': service_charge_expense,
        'deposit_in_transit': depositInTransit,
        'other_debits_in_transit':other_debits_in_transit,
            }
    def get_credit_in_transit(self):
        account_move_line = self.env['account.move.line']
        statement_line_obj = self.env['bank.acc.rec.statement.line']
        for rec in self:
            _logger.info(f"*****************explore properties")
            _logger.info(rec)
        # self.ensure_one()
        domain = [
            ('date', '=', self.ending_date),
            ('account_id', '=', self.account_id.id),
        ]
        move_lines = self.env['account.move.line'].search(domain)
        depositInTransit = sum(line.credit for line in move_lines)
        return depositInTransit if depositInTransit is not None else 0.0

    def _get_memo_debits(self, memo_description):
    # self.ensure_one()
        domain = [
            ('statement_id', '=', self.id),
            ('account_id.internal_type', '=', 'liquidity'),
            ('move_id.narration', '=', memo_description),  # Corrected domain filter
        ]
        return sum(self.env['account.move.line'].search(domain).mapped('debit'))
    def _get_memo_credits(self, memo_description):
    # self.ensure_one()
        domain = [
            ('statement_id', '=', self.id),
            ('account_id.internal_type', '=', 'liquidity'),
            ('move_id.narration', '=', memo_description),  # Corrected domain filter
        ]
        return sum(self.env['account.move.line'].search(domain).mapped('credit'))
    
    # def _get_memo_debits(self, memo_description):
    #     # self.ensure_one()
    #     domain = [
    #         ('statement_id', '=', self.id),
    #         ('account_id.internal_type', '=', 'liquidity'),
    #         ('journal_entry_ids.narration', '=', memo_description),  # Adjusted to search in the correct related field
    #     ]
    #     return sum(self.env['account.move.line'].search(domain).mapped('debit'))
    # def _get_memo_debits(self, memo_description):
    #     domain = [
    #         ('move_id.statement_id', '=', self.id),
    #         ('account_id.internal_type', '=', 'liquidity'),
    #         ('move_id.memo', '=', memo_description),
    #     ]
    #     return sum(self.env['account.move.line'].search(domain).mapped('debit'))

    def get_balance_as_per_depositors_record(self):
        return sum(self.env['account.move.line'].search([
            ('move_id.statement_id', '=', self.id),
            ('account_id.internal_type', '=', 'liquidity'),
        ]).mapped('debit'))

    def get_receivable_collected_by_bank(self):

        # explore_all_properties_of_rec()
        return self._get_memo_debits("receivable collected by bank")

    def get_interest_earned(self):
        fields_info = self.env['account.move.line'].fields_get()
        for field_name, field_attrs in fields_info.items():
            print("Field Name:", field_name)
            print("Field Attributes:", field_attrs)
            print("-----")
        # explore_all_properties_of_rec()
        return self._get_memo_debits("interest earned")

    def get_service_charges(self):
        # explore_all_properties_of_rec()
        return self._get_memo_credits("service charge expenses")

    def get_error_on_check(self):
        # explore_all_properties_of_rec()
        return self._get_memo_credits("error")
        # return self._get_memo_debits("ref4")
        

    def get_adjusted_cash_balance(self):
        balance = self.get_balance_as_per_depositors_record()
        receivable = self.get_receivable_collected_by_bank()
        interest = self.get_interest_earned()
        service_charges = self.get_service_charges()
        error_on_check = self.get_error_on_check()
        # Assuming NFS check is always 0 as per your description
        nfs_check = 0
        return balance + receivable + interest - nfs_check - service_charges - error_on_check

    
    # def get_deposit_in_transit(self):
    #     # self.ensure_one()
    #     domain = [
    #         ('date', '=', self.ending_date),
    #         ('account_id', '=', self.account_id.id),
    #         ('move_id.state', '=', 'posted'), 
    #     ]
    #     move_lines = self.env['account.move.line'].search(domain)
    #     return sum(line.debit - line.credit for line in move_lines) 
    




class BankAccRecStatementLine(models.Model):
    _name = "bank.acc.rec.statement.line"
    _description = "Statement Line"
    name = fields.Char('Name', size=64,
                       help="Derived from the related Journal Item.",
                       required=True)
    ref = fields.Char('Reference', size=64,
                      help="Derived from related Journal Item.")
    partner_id = fields.Many2one('res.partner', string='Partner',
                                 help="Derived from related Journal Item.")
    amount = fields.Float('Amount', digits=dp.get_precision('Account'),
                          help="Derived from the 'debit' amount from "
                               "related Journal Item.")
    amountcur = fields.Float('Amount in Currency',
                             digits=dp.get_precision('Account'),
                             help="Derived from the 'amount currency' "
                                  "amount from related Journal Item.")
    date = fields.Date('Date', required=True,
                       help="Derived from related Journal Item.")
    credit_statement_id = fields.Many2one('bank.acc.rec.statement', 'Statement',
                                          ondelete='cascade')
    debit_statement_id = fields.Many2one('bank.acc.rec.statement', 'Statement',
                                         ondelete='cascade')
    move_line_id = fields.Many2one('account.move.line', 'Journal Item',
                                   help="Related Journal Item.")
    cleared_bank_account = fields.Boolean('Cleared? ',
                                          help='Check if the transaction has '
                                               'cleared from the bank')
    research_required = fields.Boolean('Research Required? ',
                                       help='Check if the transaction should '
                                            'be researched by '
                                            'Accounting personal')
    currency_id = fields.Many2one('res.currency', 'Currency',
                                  help="The optional other currency if "
                                       "it is a multi-currency entry.")
    type = fields.Selection([('dr', 'Debit'), ('cr', 'Credit')], 'Cr/Dr')

    @api.model
    def create(self, vals):
        _logger.info(
            "OOOOOOOOOOOOOOOOOOOOOOOOOPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP  098765432")
        account_move_line_obj = self.env['account.move.line']
        _logger.info(vals)
        # Prevent manually adding new statement line.
        # This would allow only onchange method to pre-populate statement lines
        # based on the filter rules.
        if not vals.get('move_line_id', False):
            raise UserError(_(
                "You cannot add any new bank statement line manually "
                "as of this revision!"))
        account_move_line_obj.browse([vals['move_line_id']]).write(
            {'draft_assigned_to_statement': True})

        line_value = super(BankAccRecStatementLine, self).create(vals)
        _logger.info(line_value)
        # statement_id = self.env['bank.acc.rec.statement'].search(
        #     [('id', '=', vals['statement_id'])])
        if vals['type'] == "cr":
            _logger.info("credit")
            # statement_id.credit_move_line_ids = [(4, line_value.id)]
        else:
            _logger.info("debit")
            # statement_id.debit_move_line_ids = [(4, line_value.id)]
            # section_and_note_one2many

        return line_value

    @api.model
    def unlink(self):
        _logger.info("OOOOOOOOOO@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
        account_move_line_obj = self.env['account.move.line']
        move_line_ids = [x.move_line_id.id for x in self if x.move_line_id]
        # map(lambda x: x.move_line_id.id if x.move_line_id,
        # self.browse(cr, uid, ids, context=context))
        # Reset field values in move lines to be added later
        _logger.info(move_line_ids)
        account_move_line_obj.browse(move_line_ids).write(
            {'draft_assigned_to_statement': False})
        #  'cleared_bank_account': False, })
        #  'bank_acc_rec_statement_id': False})
        return super(BankAccRecStatementLine, self).unlink()

from odoo import models, api, fields
from odoo.exceptions import ValidationError
import logging


class ContazulResCompanyInherit(models.Model):
    _inherit = 'res.company'

    contaazul_client_id = fields.Char('Client Id')
    contaazul_client_secret_key = fields.Char('Client Secret Key')
    contaazul_client_callback_url = fields.Char('Callback Url')
    contazul_access_token = fields.Char('Access Token')
    contazul_refresh_token = fields.Char('Refresh Token')
    contazul_expires_in = fields.Char('Expire Time')
    contazul_authorised_state = fields.Selection([('authorise', 'AUTHORISED'), ('unauthorised', 'UNAUTHORISED')],
                                                 default='unauthorised', string="State", readonly=True)
    client_id_show = fields.Char(related='contaazul_client_id', string='Client Id')

    def conaazul_authorise_action(self):
        self.check_current_company_user()
        if self.contaazul_client_id and self.contaazul_client_secret_key and self.contaazul_client_callback_url:
            return {
                'type': 'ir.actions.act_url',
                'url': '/authorise/contaazul',
                'target': 'self',
            }
        else:
            raise ValidationError('Enter Client ID, Client Secret Key and Callback Url')

    def contaazul_unauthorise_action(self):
        self.check_current_company_user()
        self.write({'contazul_access_token': '',
                    'contazul_refresh_token': '',
                    'contazul_expires_in': '',
                    'contazul_authorised_state': 'unauthorised'
        }
                   )

    def contaazul_refresh_token(self):
        self.check_current_company_user()
        code, message = self.env['contazul.api.call'].refresh_contazul(self.env.user.company_id.id)
        if not code == 200:
            return {
                'type': 'ir.actions.client',
                'tag': 'conta_dialog',
                'values': {'message': message, 'title': 'Error'}
            }

    def check_current_company_user(self):
        if self.env.user.company_id.id == self.id:
            return True
        else:
            raise ValidationError('You are not allowed to modify this company. Change your current company')

    def contaazul_synchronize_all(self):
        self.check_current_company_user()
        all_products = self.env['product.product'].search([]).filtered(lambda x: x.synch_with_contaazul == False)
        all_customers = self.env['res.partner'].search([('customer', '=', True)]).filtered(
            lambda x: x.synch_with_contaazul == False)
        if not all_products and not all_customers:
            raise ValidationError('Everything is upto date')
        for product in all_products:
            response_code, response_status = product.synch_with_conta_azul(self.id)
            if not response_code:
                response_data = response_status if response_status else ''
                return {
                    'type': 'ir.actions.client',
                    'tag': 'conta_dialog',
                    'values': {'message': response_data, 'title': 'Error'}
                }
        for customer in all_customers:
            response_code, response_status = customer.synch_with_conta_azul(self.id)
            if not response_code:
                response_data = response_status if response_status else ''
                return {
                    'type': 'ir.actions.client',
                    'tag': 'conta_dialog',
                    'values': {'message': response_data, 'title': 'Error'}
                }
        return {
            'type': 'ir.actions.client',
            'tag': 'conta_dialog',
            'values': {'message': 'DONE', 'title': 'Notification'}
        }

    def sunchronise_all_invoices(self):
        pending_payment_invoices = self.env['account.invoice'].sudo().search([('state', '=', 'open'),
                                                                              ('contaazul_id', '!=', False),
                                                                              ('type', '=', 'out_invoice'),
                                                                              ('company_id.contazul_authorised_state',
                                                                               'in', ['authorise']),
                                                                              ])
        for invoice in pending_payment_invoices:
            logging.info(invoice.number + " pending payment checking")
            self.env['contazul.api.call'].get_invoice_status(invoice)

        companies = self.env['res.company'].search([('contazul_authorised_state', 'in', ['authorise'])]).ids
        for company in companies:
            self.env['contazul.api.call'].sudo().synchronise_all_invoices(company)

    def push_contaazul_invoice(self):
        invoices = self.env['account.invoice'].sudo().search([('state', '=', 'paid'),
                                                              ('synch_with_contaazul', '=', False),
                                                              ('type', '=', 'out_invoice'),
                                                              ('company_id.contazul_authorised_state', 'in',
                                                               ['authorise'])])
        for invoice in invoices:
            logging.info(invoice.number + " Found")
            push = invoice.sudo().synch_with_conta_azul_action()
            if push and type(push) == bool:
                logging.info(invoice.number + " Pushed")

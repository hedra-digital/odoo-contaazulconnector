from odoo import fields, models, api
from odoo.exceptions import ValidationError


class InheritContaAzulInvoice(models.Model):
    _inherit = 'account.invoice'

    contaazul_id = fields.Char(default='', copy=False, readonly=True)
    synch_with_contaazul = fields.Boolean(string='Sync Done', copy=False, readonly=True,
                                          default=False)
    installments_ids = fields.Char(default='')

    def synch_with_conta_azul(self):
        if not self.synch_with_contaazul:
            for rec in self.invoice_line_ids:
                if not rec.product_id.with_context(force_company=self.company_id.id).synch_with_contaazul:
                    response_code, response_status = rec.product_id.with_context\
                        (force_company=self.company_id.id).synch_with_conta_azul(self.company_id.id)
                    if not response_code:
                        return response_code, response_status
            if not self.partner_id.with_context(force_company=self.company_id.id).synch_with_contaazul:
                response_code, response_status = self.partner_id.with_context\
                    (force_company=self.company_id.id).synch_with_conta_azul(self.company_id.id)
                if not response_code:
                    return response_code, response_status
        contazul_hit = self.env['contazul.api.call']
        contazul_hit = contazul_hit.with_context(api_hit="/v1/sales", api_type='invoice')
        response_code, response_status = contazul_hit.synchronize_contazul(
            self.search_read([('id', '=', self.id)], limit=1)[0], self.company_id.id)
        return response_code, response_status

    def synch_with_conta_azul_action(self):
        if self.type == "out_invoice":
            response_code, response_status = self.synch_with_conta_azul()
            if response_code:
                if self.contaazul_id:
                    self.write({'synch_with_contaazul': True})
                else:
                    self.write({'contaazul_id': response_status.get('id')})
                return True
            else:
                self.write({'synch_with_contaazul': False})
                if type(response_status) == dict:
                    message = response_status.get('error_description') if response_status.get('error_description') else response_status.get('message')
                else:
                    message = response_status
                return {
                    'type': 'ir.actions.client',
                    'tag': 'conta_dialog',
                    'values': {'message': message, 'title': 'Error: Invoice'}
                }
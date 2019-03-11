from odoo import fields, models, api
from odoo.exceptions import ValidationError
import logging


class ProductTemplateInherit(models.Model):
    _inherit = 'product.product'

    contaazul_id = fields.Char(default='', copy=False, company_dependent=True)
    synch_with_contaazul = fields.Boolean(string='Sync Done', copy=False,
                                          default=False, company_dependent=True)

    @api.model
    def create(self, vals):
        self = self.with_context(only_create=True)
        rec = super(ProductTemplateInherit, self).create(vals)
        rec.synch_with_conta_azul(rec.company_id.id)
        return rec

    def synch_with_conta_azul(self, company_id):
        contazul_hit = self.env['contazul.api.call']
        if self.type == 'service':
            contazul_hit = contazul_hit.with_context(api_hit="/v1/services", api_type='service')
        else:
            contazul_hit = contazul_hit.with_context(api_hit="/v1/products", api_type='products')
        response_code, response_status = contazul_hit.synchronize_contazul(
            self.search_read([('id', '=', self.id)], limit=1)[0], company_id)
        self = self.with_context(only_create=True)
        if response_code:
            self.with_context(force_company=company_id).write({'contaazul_id': response_status.get('id'),
                                                               'synch_with_contaazul': True})
            logging.info("SYNCH DONE")
            logging.info(response_status.get('message'))
            logging.info(self.name)
            return True, response_code
        else:
            self.with_context(force_company=company_id).write({'synch_with_contaazul': False})
            return_response = response_status.get('error_description') if response_status.get('error_description') else \
                response_status.get('message')
            logging.info("SYNCH FAILED")
            logging.info(return_response)
            return False, return_response

    def synch_with_conta_azul_action(self):
        response_code, response_status = self.synch_with_conta_azul(self.env.user.company_id.id)
        if not response_code:
            response_data = self.name + ' ' + response_status if response_status else ''
            return {
                'type': 'ir.actions.client',
                'tag': 'conta_dialog',
                'values': {'message': response_data, 'title': 'Error'}
            }

    @api.multi
    def write(self, values):
        if self._context.get('only_create') and self._context.get('only_create') == True:
            return super(ProductTemplateInherit, self).write(values)
        rec = super(ProductTemplateInherit, self).write(values)
        if rec:
            if self.type == 'service':
                validate = self.env['contazul.api.call'].check_service_update(values.keys())
            else:
                validate = self.env['contazul.api.call'].check_product_update(values.keys())
            if validate:
                self.synch_with_conta_azul(self._context.get('force_company') or self.env.user.company_id.id)
        return rec

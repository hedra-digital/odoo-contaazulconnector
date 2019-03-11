from odoo import fields, models, api
from odoo.exceptions import ValidationError


class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'

    contaazul_id = fields.Char(default='', company_dependent=True, copy=False)
    synch_with_contaazul = fields.Boolean(string='Sync Done', company_dependent=True, default=False, copy=False)

    @api.model
    def create(self, vals):
        self = self.with_context(only_create=True)
        rec = super(ResPartnerInherit, self).create(vals)
        if rec.customer and not rec.parent_id:
            rec.synch_with_conta_azul(rec.company_id.id)
        return rec

    def synch_with_conta_azul(self, company_id):
        contazul_hit = self.env['contazul.api.call']
        contazul_hit = contazul_hit.with_context(api_hit="/v1/customers", api_type='customer')
        response_code, response_status = contazul_hit.synchronize_contazul(
            self.search_read([('id', '=', self.id)], limit=1)[0], company_id)
        self = self.with_context(only_create=True)
        if response_code:
            self.with_context(force_company=company_id).write({'contaazul_id': response_status.get('id'),
                                                               'synch_with_contaazul': True})
            return True, response_code
        else:
            self.with_context(force_company=company_id).write({'synch_with_contaazul': False})
            return False, response_status.get('error_description') if response_status.get('error_description') else \
                response_status.get('message')

    def synch_with_conta_azul_action(self):
        response_code, response_status = self.synch_with_conta_azul(self.env.user.company_id.id)
        if not response_code:
            return {
                'type': 'ir.actions.client',
                'tag': 'conta_dialog',
                'values': {'message': response_status, 'title': 'Error'}
            }

    @api.multi
    def write(self, values):
        if self._context.get('only_create') and self._context.get('only_create')==True:
            return super(ResPartnerInherit, self).write(values)
        rec = super(ResPartnerInherit, self).write(values)
        if rec and self.customer and not self.parent_id and\
                self.env['contazul.api.call'].check_customer_update(values.keys()):
            self.synch_with_conta_azul(self.env.user.company_id.id)
        return rec
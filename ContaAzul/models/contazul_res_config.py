from odoo import fields, models, api


class ResConfigInherit(models.TransientModel):
    _inherit = 'res.config.settings'

    ks_api_link = fields.Char()

    def get_values(self):
        ks_res = super(ResConfigInherit, self).get_values()
        ks_res.update(
            ks_api_link=self.env['ir.config_parameter'].get_param('ks_api_link'),
        )
        return ks_res

    def set_values(self):
        super(ResConfigInherit, self).set_values()
        self.env['ir.config_parameter'].set_param('ks_api_link', self.ks_api_link)
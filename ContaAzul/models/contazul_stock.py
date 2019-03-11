from odoo import fields, models, api
from odoo.exceptions import ValidationError


class InheritStockImmediateTransfer(models.TransientModel):
    _inherit = 'stock.immediate.transfer'

    @api.multi
    def process(self):
        a = super(InheritStockImmediateTransfer, self).process()
        for pick_id in self.pick_ids:
            for product_id in pick_id.product_id:
                product_id.synch_with_conta_azul(pick_id.company_id.id)
        return a


class InheritStockChangeObject(models.TransientModel):
    _inherit = 'stock.change.product.qty'

    def change_product_qty(self):
        rec = super(InheritStockChangeObject, self).change_product_qty()
        for product_id in self.product_id:
            product_id.synch_with_conta_azul(self.env.user.company_id.id)
        return rec


class InheritStockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.multi
    def button_validate(self):
        rec = super(InheritStockPicking, self).button_validate()
        for line in self.move_ids_without_package:
            line.product_id.synch_with_conta_azul(self.company_id.id)
        return rec
import logging
import re

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression


from odoo.tools import float_compare, float_round

_logger = logging.getLogger(__name__)



class ProductProduct(models.Model):
    _inherit = "product.product"


    profit_margin = fields.Float(compute='_compute_profit_margin', string='Profit Margin (est.)')
    public_pricelist_price = fields.Float(compute='_compute_public_pricelist_price', string='Pricelist Price', store=True, digits='Product Price')

    @api.depends_context('pricelist', 'partner', 'quantity', 'uom', 'date', 'no_variant_attributes_price_extra')
    def _compute_public_pricelist_price(self):
        default_pricelist = self.env['product.pricelist.item']._default_pricelist_id()
        _logger.info("public pricelist is %s", default_pricelist.name)
        for prod in self:
            price = prod.with_context(pricelist=default_pricelist.id).price
            _logger.info("found price %s", price)
            prod.public_pricelist_price = price


    @api.depends('standard_price', 'public_pricelist_price')
    def _compute_profit_margin(self):
        for record in self:
            if (record.standard_price_max > 0.0) and (record.public_pricelist_price > 0.0) :
                gross_profit = record.public_pricelist_price - record.standard_price
                record.profit_margin = gross_profit / record.public_pricelist_price
            else :
                record.profit_margin = 0.0            
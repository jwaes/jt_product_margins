import logging
import re

from statistics import mean
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression


from odoo.tools import float_compare, float_round

_logger = logging.getLogger(__name__)



class ProductTemplate(models.Model):
    _inherit = "product.template"

    public_pricelist_price = fields.Float(compute='_compute_public_pricelist_template_price', string='Pricelist Price', store=True, digits='Product Price')
    standard_price_max = fields.Float(compute='_compute_standard_price_max', string='Cost (Max)', store=True, digits='Product Price')
    standard_price_avg = fields.Float(compute='_compute_standard_price_max', string='Cost (Avg)', store=True, digits='Product Price')
    
    @api.depends_context('company')
    @api.depends('product_variant_ids', 'product_variant_ids.standard_price')
    def _compute_standard_price_max(self):
        for record in self:
            costs = record.product_variant_ids.filtered(lambda t: t.standard_price > 0.0).mapped('standard_price')
            if costs:
                record.standard_price_max = max(costs)
                record.standard_price_avg = mean(costs)
            else :
                record.standard_price_max = 0.0
                record.standard_price_avg = 0.0


    def _compute_public_pricelist_template_price(self):
        default_pricelist = self.env['product.pricelist.item']._default_pricelist_id()
        _logger.info("public pricelist is %s", default_pricelist.name)
        for tmpl in self:
            price = tmpl.with_context(pricelist=default_pricelist.id).price
            _logger.info("found price %s", price)
            tmpl.public_pricelist_price = price
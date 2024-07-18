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

    profit_margin = fields.Float(compute='_compute_profit_margin_template', string='Profit Margin (est.)', store=True, group_operator='avg')
    public_pricelist_price = fields.Float(compute='_compute_public_pricelist_template_price', string='Pricelist Price', store=True, digits='Product Price')
    standard_price_max = fields.Float(compute='_compute_standard_price_max', string='Cost (max)', store=True, digits='Product Price')
    standard_price_avg = fields.Float(compute='_compute_standard_price_max', string='Cost (avg)', store=True, digits='Product Price')
    

    def _recalculate_margins(self):
        for record in self:
            record._compute_public_pricelist_template_price()
            record._compute_standard_price_max()
            record._compute_profit_margin_template()


    @api.depends('standard_price_max', 'public_pricelist_price')
    def _compute_profit_margin_template(self):
        for record in self:
            if (record.public_pricelist_price > 0.0) and (record.standard_price_max > 0.0) :
                sales_price = (record.public_pricelist_price / 2.0)
                gross_profit = sales_price - record.standard_price_max
                record.profit_margin = gross_profit /sales_price
            else :
                record.profit_margin = 0.0

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
        for tmpl in self:
            price = tmpl.with_context(pricelist=default_pricelist.id).price
            tmpl.public_pricelist_price = price
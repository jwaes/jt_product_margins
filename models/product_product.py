import logging
import re

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression


from odoo.tools import float_compare, float_round

_logger = logging.getLogger(__name__)

class ProductProduct(models.Model):
    _inherit = "product.product"


    profit_margin = fields.Float(compute='_compute_profit_margin', string='Profit Margin (est.)', store=True,  aggregator='avg')
    public_pricelist_price = fields.Float(compute='_compute_public_pricelist_price', string='Pricelist Price', store=True, digits='Product Price')

    @api.depends_context('pricelist', 'partner', 'quantity', 'uom', 'date', 'no_variant_attributes_price_extra')
    def _compute_public_pricelist_price(self):
        default_pricelist = self.env['product.pricelist.item']._default_pricelist_id()
        for prod in self:
            # price = prod.with_context(pricelist=default_pricelist.id).price
            price = default_pricelist._get_product_price(prod, 1.0)
            prod.public_pricelist_price = price


    @api.depends('standard_price', 'public_pricelist_price')
    def _compute_profit_margin(self):
        for record in self:
            if (record.standard_price > 0.0) and (record.public_pricelist_price > 0.0) :
                sales_price = (record.public_pricelist_price / 2.0)
                gross_profit = sales_price - record.standard_price
                record.profit_margin = gross_profit / sales_price
            else :
                record.profit_margin = 0.0     


    def _recalculate_margins(self):
        for record in self:
            record._compute_public_pricelist_price()
            record._compute_profit_margin()           

    # def create_pricelist_item_from_template(self, profit_margin=False, multiplier=2.0, quarter='this', force_create=False, pricelist=False, reduce_price=False):
    #     """Creates a pricelist item for this product variant based on its parent template.
        
    #     This method calls the parent's create_new_pricelist_item method and then filters the 
    #     returned pricelist items to return the one corresponding to this variant.
    #     """
    #     self.ensure_one()
    #     pricelist_items = self.product_tmpl_id.create_new_pricelist_item(
    #         profit_margin=profit_margin, 
    #         multiplier=multiplier, 
    #         quarter=quarter, 
    #         force_create=force_create, 
    #         pricelist=pricelist, 
    #         reduce_price=reduce_price
    #     )
    #     return pricelist_items.filtered(lambda item: item.product_id == self)                        


    def create_new_pricelist_item(self, profit_margin=False, multiplier=2.0, quarter='this', force_create=False, pricelist=False, reduce_price=False):
        """
        For a product.product record, forward the call to its parent template’s create_new_pricelist_item method.
        This will create pricelist items for all variants (including siblings) as defined in the product.template method.
        """
        self.ensure_one()
        return self.product_tmpl_id.create_new_pricelist_item(
            profit_margin=profit_margin,
            multiplier=multiplier,
            quarter=quarter,
            force_create=force_create,
            pricelist=pricelist,
            reduce_price=reduce_price
        )    
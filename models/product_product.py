import logging
import re

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression


from odoo.tools import float_compare, float_round

_logger = logging.getLogger(__name__)



class ProductProduct(models.Model):
    _inherit = "product.product"


    public_pricelist_price = fields.Float(compute='_compute_public_pricelist_price', string='Pricelist Price', store=True)

    @api.depends_context('pricelist', 'partner', 'quantity', 'uom', 'date', 'no_variant_attributes_price_extra')
    def _compute_public_pricelist_price(self):
        default_pricelist = self.env['product.pricelist.item']._default_pricelist_id()
        for prod in self:
            prod.public_pricelist_price = prod.with_context(pricelist=default_pricelist).price
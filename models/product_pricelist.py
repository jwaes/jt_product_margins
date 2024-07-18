import logging
from odoo import api, fields, models
from odoo.tools import date_utils
from datetime import datetime
from pytz import timezone, UTC
from odoo.exceptions import ValidationError
import math

_logger = logging.getLogger(__name__)

class PricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    profit_margin = fields.Float(compute='_compute_profit_margin', string='Profit Margin (est.)')
    
    @api.depends('product_tmpl_id', 'product_tmpl_id.standard_price_max', 'product_id', 'product_id.standard_price', 'fixed_price')
    def _compute_profit_margin(self):
        for record in self:
            cost = 0.0
            if record.product_tmpl_id:
                cost = record.product_tmpl_id.standard_price_max
            elif record.product_id:
                cost = record.product_id.standard_price
            sales_price = (record.fixed_price / 2.0)
            if (cost > 0.0) and (sales_price > 0.0):
                gross_profit = sales_price - record.standard_price_max
                record.profit_margin = gross_profit / sales_price  
            else:
                record.profit_margin = 0.0          

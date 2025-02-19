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
    validity = fields.Selection([
        ('current', 'Current'),
        ('past', 'Past'),
        ('future', 'Future')
    ], string='Validity', compute='_compute_validity', store=True)
    automatically_generated = fields.Boolean(string='Automatically Generated', default=False)
    fixed_price_automatically_calculated = fields.Float(string='Calculated Price', digits='Product Price')

    @api.depends('date_start', 'date_end')
    def _compute_validity(self):
        now = fields.Datetime.now()
        for rec in self:
            validity = 'current'
            if rec.date_end and (now > rec.date_end):
                validity = 'past'
            elif rec.date_start and (now < rec.date_start):
                validity = 'future'
            rec.validity = validity


    @api.depends('product_tmpl_id', 'product_tmpl_id.standard_price_max', 'product_id', 'product_id.standard_price', 'fixed_price')
    def _compute_profit_margin(self):
        for record in self:
            cost = 0.0
            if record.product_id and record.product_id.standard_price > 0.0:
                cost = record.product_id.standard_price            
            elif record.product_tmpl_id:
                cost = record.product_tmpl_id.standard_price_max
            sales_price = (record.fixed_price / 2.0)
            if (cost > 0.0) and (sales_price > 0.0):
                gross_profit = sales_price - cost
                record.profit_margin = gross_profit / sales_price  
            else:
                record.profit_margin = 0.0

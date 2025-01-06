import logging
import re
import math

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
            price = default_pricelist._get_product_price(tmpl, 1.0)
            tmpl.public_pricelist_price = price

    def _get_q_year(self, for_date=fields.Datetime.now()):
        value = for_date.year
        return int(value)
    
    def _get_q(self, for_date=fields.Datetime.now()):
        value = for_date.month / 3
        value = math.ceil(value)
        return int(value)

    def create_new_pricelist_item(self, profit_margin=False, multiplier=2.0, quarter='this', force_create=False, pricelist=False, reduce_price=False):
        if not pricelist:
            pricelist = self.env['product.pricelist.item']._default_pricelist_id()

        today = fields.Datetime.now()
        previous_date =  tools.date_utils.subtract(today, months=3)        

        # quarter == 'this'
        q = self._get_q()
        q_year = self._get_q_year()

        if not profit_margin:
            default_digest_emails = self.env['ir.config_parameter'].sudo().get_param('digest.default_digest_emails')
            profit_margin = float(self.env['ir.config_parameter'].sudo().get_param('jt.product.margin.pct', default=0.4))

        if quarter == 'next':
            for_date = tools.date_utils.add(today, months=3)
            previous_date =  today
            q = self._get_q(for_date=for_date)
            q_year = self._get_q_year(for_date=for_date)

        for template in self:
            _logger.info("Product Template %s", template.name)
            pricelist_items = template.env['product.pricelist.item'].search([
                '|', ('product_tmpl_id', '=', template.id), 
                ('product_id', 'in', template.product_variant_ids.ids)]).filtered(lambda price: 
                    (price.daterange_type == 'quarter') and 
                    (price.daterange_q == q) and 
                    (price.daterange_q_year == q_year))
            if len(pricelist_items) > 0:
                _logger.info("pricelist item exits for this quarter")
            else:
                if template.standard_price_max > 0:
                    sales_price = (template.standard_price_max / (1-profit_margin)) * multiplier
                    previous_price = pricelist._get_product_price(template, 1.0, date=previous_date)
                    _logger.info("calculated price is %s", sales_price)
                    if sales_price < previous_price:
                        _logger.info("calculated price is lower than current pricelist price")
                        if not reduce_price:
                            _logger.info("not lowering price")
                            sales_price = previous_price
                    pricelist_item = template.env['product.pricelist.item'].create({
                        'pricelist_id': pricelist.id,
                        'applied_on': '1_product',
                        'product_tmpl_id': template.id,
                        'compute_price': 'fixed',
                        'fixed_price': sales_price,                        
                        'base': 'list_price',  # based on public price
                        'min_quantity': 0.0, 
                        'daterange_type': 'quarter',
                        'daterange_q': q,
                        'daterange_q_year': q_year,
                    })
                    pricelist_item._calculate_daterange()


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

    profit_margin = fields.Float(compute='_compute_profit_margin_template', string='Profit Margin (est.)', store=True, aggregator='avg')
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


    @api.depends('tmpl_all_kvs')
    def _get_profit_margin(self):
        profit_margin = float(self.env['ir.config_parameter'].sudo().get_param('jt.product.margin.pct', default=0.4))
        for tmpl in self:
            for kv in tmpl.tmpl_all_kvs:
                if kv.code == "margin.bruto.pct":
                    profit_margin = float(kv.text)
        return profit_margin        

    def get_pricelist_item_vals(self, template, variant, profit_margin=False,  quarter='this', multiplier=2.0, pricelist=False, reduce_price=False):
        if not pricelist:
            pricelist = self.env['product.pricelist.item']._default_pricelist_id()

        if not profit_margin:
            profit_margin = self._get_profit_margin()

        q, q_year, previous_date = self.get_q_year(quarter)            
                    
        margin_max_cost = True
        for kv in template.tmpl_all_kvs:
            if kv.code == "margin.cost.max":
                margin_max_cost = (kv.value_id.code.lower() == 'yes')
                break
        _logger.info("Margin max cost setting evaluated to: %s", margin_max_cost)
        if margin_max_cost:
            _logger.info("Margin max cost is enabled. Using template cost for margin calculation.")
            if template.standard_price_max > 0:
                base_cost = template.standard_price_max
            else:
                return False  # No vals if no base cost
        else:
            _logger.info("Margin max cost is disabled. Using variant cost for margin calculation.")
            if variant and variant.standard_price > 0:
                base_cost = variant.standard_price
            else:
                return False  # No vals if no base cost
        sales_price = (base_cost / (1 - profit_margin)) * multiplier
        previous_price = pricelist._get_product_price(variant or template, 1.0, date=previous_date)
        _logger.info("calculated price is %s", sales_price)
        calculated_price = sales_price
        if sales_price < previous_price:
            _logger.info("calculated price is lower than current pricelist price")
            if not reduce_price:
                _logger.info("not lowering price")
                sales_price = previous_price
        
        vals = {
            'pricelist_id': pricelist.id,
            'applied_on': '0_product_variant' if variant else '1_product',
            'product_id': variant.id if variant else False,
            'product_tmpl_id': template.id,
            'compute_price': 'fixed',
            'fixed_price': sales_price,
            'fixed_price_automatically_calculated': calculated_price,
            'base': 'list_price',
            'min_quantity': 0.0,
            'daterange_type': 'quarter',
            'daterange_q': q,
            'daterange_q_year': q_year,
            'automatically_generated': True,
        }
        return vals

    def get_q_year(self, quarter='this'):
        today = fields.Datetime.now()
        previous_date =  tools.date_utils.subtract(today, months=3)        
        
        # quarter == 'this'
        q = self._get_q()
        q_year = self._get_q_year()
        
        if quarter == 'next':
            for_date = tools.date_utils.add(today, months=3)
            previous_date =  today
            q = self._get_q(for_date=for_date)
            q_year = self._get_q_year(for_date=for_date)
        return q, q_year, previous_date

    def create_new_pricelist_item_variant(self, variant, template, q, q_year, profit_margin, quarter, multiplier, pricelist, reduce_price, fixed_price):
        _logger.info("Product Template %s (%s), Variant %s (%s)", template.name, template.id, variant.name, variant.id)
        domain = [
            ('daterange_type', '=', 'quarter'),
            ('daterange_q', '=', q),
            ('daterange_q_year', '=', q_year),
        ]
        if variant:
            domain.append(('product_id', '=', variant.id))
        else:
            domain.append(('product_tmpl_id', '=', template.id))

        _logger.info("searching for pricelist items with domain: %s", domain)
        pricelist_items = template.env['product.pricelist.item'].search(domain)
        _logger.info("pricelist items found: %s", len(pricelist_items))
        if len(pricelist_items) > 0:
            _logger.info("pricelist item exits for this quarter")
        else:
            margin_max_cost = True
            for kv in template.tmpl_all_kvs:
                if kv.code == "margin.cost.max":
                    margin_max_cost = (kv.value_id.code.lower() == 'yes')
                    break
            if margin_max_cost:
                if template.standard_price_max > 0:
                    base_cost = template.standard_price_max
                    variant = False  # Use template cost, and make a template price entry
                else:
                    _logger.warning("not creating a standard_price_max is 0.0")            
                    return  # Skip this variant
            else:
                if variant.standard_price > 0:
                    base_cost = variant.standard_price
                else:
                    return  # Skip this variant
            vals = self.get_pricelist_item_vals(template, variant, profit_margin, quarter, multiplier, pricelist, reduce_price)
            if fixed_price:
                vals['fixed_price'] = fixed_price
            if vals:
                pricelist_item = template.env['product.pricelist.item'].create(vals)
                pricelist_item._calculate_daterange()        

    def create_new_pricelist_item(self, profit_margin=False, multiplier=2.0, quarter='this', pricelist=False, reduce_price=False, fixed_price=False, variant=False):
        if not pricelist:
            pricelist = self.env['product.pricelist.item']._default_pricelist_id()

        q, q_year, previous_date = self.get_q_year(quarter)

        margin_max_cost = True
        for kv in self.tmpl_all_kvs:
            if kv.code == "margin.cost.max":
                margin_max_cost = (kv.value_id.code.lower() == 'yes')
                break

        if variant:
            _logger.info("Variant %s (%s)", variant.name, variant.id)
            pricelist_item = self.create_new_pricelist_item_variant(variant, variant.product_tmpl_id, q, q_year, profit_margin, quarter, multiplier, pricelist, reduce_price, fixed_price)
        else:
            for template in self:
                _logger.info("Product Template %s (%s)", template.name, template.id)
                if margin_max_cost:
                    _logger.info("Margin max cost is enabled. Using template cost for margin calculation.")
                    pricelist_item = self.create_new_pricelist_item_variant(None, template, q, q_year, profit_margin, quarter, multiplier, pricelist, reduce_price, fixed_price)
                else :
                    _logger.info("Margin max cost is disabled. Using variant cost for margin calculation.")
                    for variant in template.product_variant_ids:
                        _logger.info("|-- Variant %s (%s)", variant.name, variant.id)
                        pricelist_item = self.create_new_pricelist_item_variant(variant, template, q, q_year, profit_margin, quarter, multiplier, pricelist, reduce_price, fixed_price)



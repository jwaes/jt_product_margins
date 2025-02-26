import logging
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_compare
import time

_logger = logging.getLogger(__name__)

class NextQuarterPricelistWizardLine(models.TransientModel):
    _name = 'next.quarter.pricelist.wizard.line'
    _description = "Next Quarter Pricelist Wizard Line"

    wizard_id = fields.Many2one('next.quarter.pricelist.wizard', string="Wizard")
    product_tmpl_id = fields.Many2one('product.template', string="Product")
    product_id = fields.Many2one('product.product', string="Variant")
    current_price = fields.Float(string="Current Pricelist Price")
    proposed_price = fields.Float(string="Proposed Price")
    calculated_price = fields.Float(string="Calculated Price")
    new_price = fields.Float(string="New Price")
    price_change = fields.Selection([
         ('up', 'Up'),
         ('down', 'Down'),
         ('same', 'Same'),
    ], string="Price Change", compute='_compute_price_change', store=True)
    margin_used = fields.Char(string="Margin Used")
    applied_on = fields.Selection([
        ('template', 'Template'),
        ('variant', 'Variant'),
    ], string="Applied On", default='variant')
    computed_margin = fields.Float(string="Computed Margin", compute="_compute_margin")

    @api.depends('product_tmpl_id', 'proposed_price', 'new_price', 'applied_on')
    def _compute_margin(self):
        for line in self:
            if line.applied_on == 'variant':
                cost_price = line.product_tmpl_id.product_variant_ids[:1].standard_price if line.product_tmpl_id.product_variant_ids else 0.0
            else:
                cost_price = line.product_tmpl_id.standard_price_max

            sales_price = (line.new_price if line.new_price else line.proposed_price) / 2.0
            if sales_price > 0.0 and cost_price > 0.0:
                gross_profit = sales_price - cost_price
                line.computed_margin = gross_profit / sales_price
            else:
                line.computed_margin = 0.0

    @api.depends('current_price', 'new_price')
    def _compute_price_change(self):
        for line in self:
            if float_compare(line.new_price, line.current_price, precision_digits=2) > 0:
                line.price_change = 'up'
            elif float_compare(line.new_price, line.current_price, precision_digits=2) < 0:
                line.price_change = 'down'
            else:
                line.price_change = 'same'

class NextQuarterPricelistWizard(models.TransientModel):
    _name = 'next.quarter.pricelist.wizard'
    _description = "Next Quarter Pricelist Wizard"

    pricelist_id = fields.Many2one('product.pricelist', string="Pricelist", required=True)
    line_ids = fields.One2many('next.quarter.pricelist.wizard.line', 'wizard_id', string="Products")

    def load_data(self):
       # Clear existing lines
        self.line_ids.unlink()
        today = fields.Date.today()
        current_quarter = (today.month - 1) // 3 + 1
        year = today.year

        # Calculate next quarter and year
        next_quarter = current_quarter + 1
        next_year = year
        if next_quarter > 4:
            next_quarter = 1
            next_year += 1

        start_time2 = time.perf_counter()
        # Step 1: Get current quarter items
        current_items = self.env['product.pricelist.item'].search([
            ('pricelist_id', '=', self.pricelist_id.id),
            ('automatically_generated', '=', True),
            ('daterange_type', '=', 'quarter'),
            ('daterange_q', '=', current_quarter),
            ('daterange_q_year', '=', year),
        ])

        # Step 2: Get related product and product template IDs from current items.
        # Only consider product_ids when available; if not, use product_tmpl_id.
        current_product_ids = current_items.filtered(lambda r: r.product_id).mapped('product_id').ids
        current_product_tmpl_ids = current_items.filtered(lambda r: not r.product_id and r.product_tmpl_id).mapped('product_tmpl_id').ids

        # Step 3: Find next quarter items that use any of these products/templates
        next_items = self.env['product.pricelist.item'].search([
            ('pricelist_id', '=', self.pricelist_id.id),
            ('daterange_type', '=', 'quarter'),
            ('daterange_q', '=', next_quarter),
            ('daterange_q_year', '=', next_year),
            '|',
            ('product_id', 'in', current_product_ids),
            ('product_tmpl_id', 'in', current_product_tmpl_ids),
        ])

        # Build sets of product IDs and product template IDs present in next quarter items
        next_product_ids = next_items.filtered(lambda r: r.product_id).mapped('product_id').ids
        next_product_tmpl_ids = next_items.filtered(lambda r: not r.product_id and r.product_tmpl_id).mapped('product_tmpl_id').ids

        # Step 4: Exclude current items that have a corresponding next quarter entry.
        def keep_item(item):
            if item.product_id:
                return item.product_id.id not in next_product_ids
            elif item.product_tmpl_id:
                return item.product_tmpl_id.id not in next_product_tmpl_ids
            return True

        pricelist_items = current_items.filtered(keep_item)

        elapsed_time = time.perf_counter() - start_time2
        _logger.info(f"Elapsed time: {elapsed_time:.4f} seconds")
        _logger.info("Found %s pricelist items", len(pricelist_items))


        for item in pricelist_items:
            tmpl = item.product_tmpl_id
            current_price = item.fixed_price
            # Use the template if product_id is False, otherwise use variant.
            product_to_use = item.product_id or tmpl
            # Calculate proposed price for next quarter using existing method
            vals = tmpl.get_pricelist_item_vals(
                template=tmpl,
                variant=product_to_use,
                profit_margin=False,
                quarter='next',
                multiplier=2.0,
                pricelist=self.pricelist_id,
                reduce_price=False  # We're not applying reduction yet
            )
            proposed_price = vals['fixed_price']
            calculated_price = vals['fixed_price_automatically_calculated']

            self.env['next.quarter.pricelist.wizard.line'].create({
                'wizard_id': self.id,
                'product_tmpl_id': tmpl.id,
                'product_id': item.product_id.id,
                'current_price': current_price,
                'proposed_price': proposed_price,
                'calculated_price': calculated_price,
                'new_price': proposed_price,  # Initialize new_price
                'price_change': 'same',
                'margin_used': str(tmpl._get_profit_margin()),
                'applied_on': "variant" if item.product_id else "template",
            })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'next.quarter.pricelist.wizard',
            'view_mode': 'form',
            'target': 'new',
            'res_id': self.id,
        }

    def action_create_next_quarter_items(self):
        if not self.line_ids:
            raise UserError(_("No data loaded."))
        for line in self.line_ids:
            if line.applied_on == 'template':
                target = line.product_tmpl_id
            else:
                target = line.product_id
            if target:
                target.create_new_pricelist_item(
                    profit_margin=False,
                    multiplier=2.0,
                    quarter='next',
                    pricelist=self.pricelist_id,
                    reduce_price=False,  # Always False, user chooses on wizard
                    fixed_price=line.new_price
                )
        return {'type': 'ir.actions.act_window_close'}

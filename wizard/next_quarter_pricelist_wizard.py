import logging
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)

class NextQuarterPricelistWizardLine(models.TransientModel):
    _name = 'next.quarter.pricelist.wizard.line'
    _description = "Next Quarter Pricelist Wizard Line"

    wizard_id = fields.Many2one('next.quarter.pricelist.wizard', string="Wizard")
    product_tmpl_id = fields.Many2one('product.template', string="Product")
    current_price = fields.Float(string="Current Pricelist Price")
    proposed_price = fields.Float(string="Proposed Price")
    calculated_price = fields.Float(string="Calculated Price")  # New field
    new_price = fields.Float(string="New Price") # Added field
    price_change = fields.Selection([
         ('up', 'Up'),
         ('down', 'Down'),
         ('same', 'Same'),
    ], string="Price Change")
    margin_used = fields.Char(string="Margin Used")
    applied_on = fields.Selection([
        ('template', 'Template'),
        ('variant', 'Variant'),
    ], string="Applied On", default='variant')

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
        # Calculate start and end dates for current quarter
        start_date = fields.Date.from_string(f'{year}-{(3 * current_quarter - 2):02d}-01')
        if current_quarter == 4:
            end_date = fields.Date.from_string(f'{year}-12-31')
        else:
            next_quarter_start = fields.Date.from_string(f'{year}-{(3 * current_quarter + 1):02d}-01')
            end_date = next_quarter_start + relativedelta(days=-1)
        _logger.info("Current Quarter Dates: %s to %s", start_date, end_date)
        # Find pricelist items automatically generated for current quarter
        pricelist_items = self.env['product.pricelist.item'].search([
            ('pricelist_id', '=', self.pricelist_id.id),            
            ('automatically_generated', '=', True),
            ('daterange_type', '=', 'quarter'),
            ('daterange_q', '=', current_quarter),
            ('daterange_q_year', '=', year),
        ])
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

            # Determine price change
            if float_compare(proposed_price, current_price, precision_digits=2) > 0:
                change = 'up'
            elif float_compare(proposed_price, current_price, precision_digits=2) < 0:
                change = 'down'
            else:
                change = 'same'

            self.env['next.quarter.pricelist.wizard.line'].create({
                'wizard_id': self.id,
                'product_tmpl_id': tmpl.id,
                'current_price': current_price,
                'proposed_price': proposed_price,
                'calculated_price': calculated_price,
                'new_price': proposed_price,  # Initialize new_price
                'price_change': change,
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
                target = line.product_tmpl_id.product_variant_ids[:1]
                if not target:
                    continue # Skip if no variant is found.

            if target:  # Check if target exists
                target.create_new_pricelist_item(
                    profit_margin=False,
                    multiplier=2.0,
                    quarter='next',
                    force_create=True,
                    pricelist=self.pricelist_id,
                    reduce_price=False,  # Always False
                    fixed_price=line.new_price,
                    for_variant=target if line.applied_on == 'variant' else False  # Pass the variant if applicable
                )
        return {'type': 'ir.actions.act_window_close'}

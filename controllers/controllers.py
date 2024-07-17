# -*- coding: utf-8 -*-
# from odoo import http


# class JtProductMargins(http.Controller):
#     @http.route('/jt_product_margins/jt_product_margins', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/jt_product_margins/jt_product_margins/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('jt_product_margins.listing', {
#             'root': '/jt_product_margins/jt_product_margins',
#             'objects': http.request.env['jt_product_margins.jt_product_margins'].search([]),
#         })

#     @http.route('/jt_product_margins/jt_product_margins/objects/<model("jt_product_margins.jt_product_margins"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('jt_product_margins.object', {
#             'object': obj
#         })


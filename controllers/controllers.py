# -*- coding: utf-8 -*-
# from odoo import http


# class /extra-addons/wmds/(http.Controller):
#     @http.route('//extra-addons/wmds///extra-addons/wmds/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('//extra-addons/wmds///extra-addons/wmds//objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('/extra-addons/wmds/.listing', {
#             'root': '//extra-addons/wmds///extra-addons/wmds/',
#             'objects': http.request.env['/extra-addons/wmds/./extra-addons/wmds/'].search([]),
#         })

#     @http.route('//extra-addons/wmds///extra-addons/wmds//objects/<model("/extra-addons/wmds/./extra-addons/wmds/"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('/extra-addons/wmds/.object', {
#             'object': obj
#         })


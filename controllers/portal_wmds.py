from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

class WMDS_Portal(CustomerPortal):

    @http.route(['/wmds'], type='http', auth="user", website=True)
    def my_custom_portal_page(self, **kw):
        return request.render("wmds.portal_wmds", {})
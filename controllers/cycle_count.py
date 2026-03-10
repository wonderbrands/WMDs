from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class CycleCount(http.Controller):

    @http.route('/wmds/v2/engine/get/locations_by_range', type='json', auth='user', methods=['POST'], csrf=True)
    def get_locations_by_range(self, **kw):
        _logger.info("============================")
        _logger.info(kw)

        
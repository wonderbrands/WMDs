# -*- coding: utf-8 -*-
"""Traslados a BIN y de BIN a DOCK: síncronos, sin pasar por wmds.queued_tasks."""
import json
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

import odoo.addons.wmds.controllers.dock_n_bin as dock_n_bin_ctrl


@tagged('post_install', '-at_install')
class TestBinDockOperations(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.operator = cls.env.user
        cls.bin = cls.env['bin.storage'].create({'name': 'BIN-TEST-Q'})
        cls.dock = cls.env['dock.storage'].create({'name': 'DOCK-TEST-Q'})
        partner = cls.env['res.partner'].create({'name': 'Cliente cola BIN'})
        cls.so = cls.env['sale.order'].create({'partner_id': partner.id})
        # Más de 10 guías: antes de este cambio iban a la cola
        cls.tags = cls.env['sale.order.ei'].create([{'so_id': cls.so.id} for _ in range(12)])
        cls.names = cls.tags.mapped('display_name_custom')
        cls.product = cls.env['product.product'].create({'name': 'Producto cola BIN', 'type': 'consu'})

    def _full_move(self, **vals):
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        return self.env['stock.move'].create(dict({
            'name': self.product.name,
            'product_id': self.product.id,
            'product_uom_qty': 3,
            'product_uom': self.product.uom_id.id,
            'location_id': warehouse.lot_stock_id.id,
            'location_dest_id': warehouse.lot_stock_id.id,
        }, **vals))

    def _move_tags_to_bin(self):
        return self.bin._wmds_move_to_bin(self.operator.login, orders=self.names)

    # ------------------------------------------------------------------
    # Traslado a BIN
    # ------------------------------------------------------------------

    def test_move_orders_to_bin(self):
        res = self._move_tags_to_bin()
        self.assertTrue(res['ok'])
        self.assertTrue(all(self.tags.mapped('on_bin')))
        self.assertEqual(self.tags.bin_id, self.bin)
        bin_log = self.env['bin.log'].search([('bin_id', '=', self.bin.id)])
        self.assertEqual(len(bin_log.line_ids), len(self.tags))
        self.assertEqual(
            self.env['wmds.log'].search_count([('sale', '=', self.so.id), ('log', 'ilike', self.bin.name)]),
            len(self.tags),
        )

    def test_blocked_bin_rejects_items(self):
        self.bin.state = 'blocked'
        with self.assertRaisesRegex(UserError, 'bloqueado'):
            self._move_tags_to_bin()

    def test_bin_with_full_rejects_orders(self):
        # Antes esta regla solo se revisaba con 10 guías o menos
        self._full_move(on_bin=True, bin_id=self.bin.id)
        with self.assertRaisesRegex(UserError, 'fulfillment'):
            self._move_tags_to_bin()

    def test_move_full_picking_to_bin(self):
        picking_type = self.env['stock.picking.type'].search([('code', '=', 'internal')], limit=1)
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': picking_type.default_location_dest_id.id,
            'origin': 'ORIGEN-TEST-Q',
        })
        move = self._full_move(picking_id=picking.id)
        move.write({'state': 'done', 'quantity': 3})

        res = self.bin._wmds_move_to_bin(self.operator.login, pick_id=picking.id)

        self.assertEqual((res['count'], res['origin'], res['bin']), (1, 'ORIGEN-TEST-Q', self.bin.name))
        self.assertTrue(move.on_bin)
        self.assertEqual(self.bin.origin_doc, 'ORIGEN-TEST-Q')

    # ------------------------------------------------------------------
    # Traslado de BIN a DOCK
    # ------------------------------------------------------------------

    def test_move_to_dock_releases_bin(self):
        self._move_tags_to_bin()
        self.bin.write({'state': 'blocked', 'origin_doc': 'X'})

        res = self.bin._wmds_move_to_dock(self.dock, self.operator.login)

        self.assertEqual(res, {'ok': True, 'moved_packages': len(self.tags)})
        self.assertTrue(all(self.tags.mapped('on_dock')))
        self.assertFalse(any(self.tags.mapped('on_bin')))
        self.assertEqual(self.tags.dock_id, self.dock)
        self.assertEqual(self.bin.state, 'available')
        self.assertFalse(self.bin.origin_doc)

    def test_partial_move_keeps_bin_blocked(self):
        self._move_tags_to_bin()
        self.bin.state = 'blocked'
        selected = [{'name': name} for name in self.names[:3]]

        res = self.bin._wmds_move_to_dock(self.dock, self.operator.login, selected)

        self.assertEqual(res['moved_packages'], 3)
        self.assertEqual(self.bin.state, 'blocked')
        self.assertEqual(len(self.tags.filtered('on_bin')), len(self.tags) - 3)

    def test_unblocked_bin_cannot_go_to_dock(self):
        self._move_tags_to_bin()
        with self.assertRaisesRegex(UserError, 'bloqueado'):
            self.bin._wmds_move_to_dock(self.dock, self.operator.login)

    def test_dock_with_full_rejects_orders(self):
        self._move_tags_to_bin()
        self.bin.state = 'blocked'
        self._full_move(on_dock=True, dock_id=self.dock.id)
        with self.assertRaisesRegex(UserError, 'fulfillment'):
            self.bin._wmds_move_to_dock(self.dock, self.operator.login)

    # ------------------------------------------------------------------
    # Endpoints y cola
    # ------------------------------------------------------------------

    def test_endpoints_do_not_queue(self):
        Tasks = self.env['wmds.queued_tasks']
        before = Tasks.search_count([])
        controller = dock_n_bin_ctrl.DockNBin()
        with patch.object(dock_n_bin_ctrl, 'request', MagicMock(env=self.env)):
            res_bin = controller.move_to_bin(bin=self.bin.name, operator=self.operator.login, orders=self.names)
            self.bin.state = 'blocked'
            res_dock = controller.move_bin_to_dock(bin=self.bin.name, dock=self.dock.name, operator=self.operator.login)

        self.assertEqual(res_bin, {'ok': True})
        self.assertEqual(res_dock, {'ok': True, 'moved_packages': len(self.tags)})
        self.assertEqual(Tasks.search_count([]), before)

    def test_legacy_queued_task_is_drained(self):
        task = self.env['wmds.queued_tasks'].create({
            'task_type': 'move_to_bin',
            'params': json.dumps({'bin': self.bin.name, 'operator': self.operator.login, 'orders': self.names}),
            'operator_login': self.operator.login,
        })
        # _process_task hace commit, prohibido dentro de una prueba
        with patch.object(self.env.cr, 'commit', lambda: None):
            task._process_task()

        self.assertEqual(task.status, 'completed')
        self.assertTrue(all(self.tags.mapped('on_bin')))

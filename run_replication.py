# -*- coding: utf-8 -*-
import odoo.http
import unittest.mock
from odoo import fields
from datetime import datetime
import random

print("====================================================")
print("     LIVE WMDS PROCESS REPLICATION RUN")
print("====================================================")
print(f"Local Execution Time (UTC): {datetime.utcnow()}")

class MockSession(object):
    def __init__(self, uid):
        self.uid = uid
        self.debug = ''
        
    def get(self, key, default=None):
        return getattr(self, key, default)

class MockRequest(object):
    def __init__(self, env, user_id):
        self.env = env
        self.uid = user_id
        self.user = env['res.users'].browse(user_id)
        self.session = MockSession(user_id)
        self.cr = env.cr
        self.context = env.context
        self.cookies = {}
        self.httprequest = unittest.mock.MagicMock()
        self.httprequest.environ = {}

# Setup request context for operator user 207 (Aarón Alexander Soto Murguia)
env = self.env
operator_user_id = 207
mock_req = MockRequest(env, operator_user_id)
odoo.http._request_stack.push(mock_req)

try:
    # 1. Alias field if needed
    if 'carrier_selection_relational' not in env['sale.order']._fields:
        env['sale.order']._fields['carrier_selection_relational'] = env['sale.order']._fields['data_carrier_selection_relational']
        type(env['sale.order']).carrier_selection_relational = property(
            lambda self: self.data_carrier_selection_relational,
            lambda self, val: self.write({'data_carrier_selection_relational': val})
        )

    # 2. Get resources
    vendor = self.env['res.partner'].search([('supplier_rank', '>', 0)], limit=1)
    customer = self.env['res.partner'].search([('customer_rank', '>', 0)], limit=1)
    product = self.env['product.product'].browse(7009) # Bosch Drill

    # ==========================================
    # FLOW 1: PURCHASE (WITHOUT VO.BO. -> QUARANTINE -> APPROVE)
    # ==========================================
    print("\n--- [STEP 1] CREATING BRAND NEW PO ---")
    po = self.env['purchase.order'].create({
        'partner_id': vendor.id,
        'order_line': [(0, 0, {
            'product_id': product.id,
            'product_qty': 3.0,
            'price_unit': 150.0,
            'name': f"Live Test - {product.name}",
        })]
    })
    print(f"PO Created: {po.name} (ID: {po.id})")
    
    po.button_confirm()
    print(f"PO Confirmed: State is {po.state}")

    # Process receipt
    receipt = po.picking_ids.filtered(lambda p: p.picking_type_id.code == 'incoming')
    print(f"Receipt Picking Created: {receipt.name}")
    for move in receipt.move_ids:
        move.quantity = move.product_uom_qty
    receipt.button_validate()
    print(f"Receipt {receipt.name} Validated.")

    # Find storage picking
    storage = self.env['stock.picking'].search([
        ('origin', '=', po.name),
        ('picking_type_id.name', 'in', ('Storage', 'Rackeo', 'Rackeos')),
        ('state', '!=', 'cancel')
    ], limit=1)
    print(f"Storage Picking Created: {storage.name}")

    # Set up empty location
    dest_loc = None
    all_locs = self.env['stock.location'].search([
        ('complete_name', 'like', 'WH/Stock/Almacenaje'),
        ('usage', '=', 'internal')
    ])
    for l in all_locs:
        q = self.env['stock.quant'].search([('location_id', '=', l.id), ('quantity', '>', 0)])
        if not q:
            cuar_name = l.complete_name.replace('Stock/Almacenaje', 'Cuarentena')
            cuar_l = self.env['stock.location'].search([('complete_name', '=', cuar_name)], limit=1)
            if cuar_l:
                dest_loc = l
                break
                
    if not dest_loc:
        rand_name = f"LIVE-LOC-{random.randint(1000, 9999)}"
        dest_loc = self.env['stock.location'].create({'name': rand_name, 'location_id': 152})
        self.env['stock.location'].create({'name': rand_name, 'location_id': 147})
    
    print(f"Using empty target location: {dest_loc.complete_name}")
    for move in storage.move_ids:
        move.location_dest_id = dest_loc.id
        move.quantity = move.product_uom_qty

    # Temporarily rename Storage to Rackeo to trigger quarantine rule
    orig_pt_name = storage.picking_type_id.name
    storage.picking_type_id.sudo().write({'name': 'Rackeo'})

    storage.button_validate()
    print(f"Storage Picking {storage.name} Validated.")
    storage.picking_type_id.sudo().write({'name': orig_pt_name})

    # Verify Quarantine block
    dest_loc.invalidate_recordset()
    print(f"Location {dest_loc.name} Parent: {dest_loc.location_id.complete_name} (Expected: WH/Cuarentena)")
    print(f"Location Block Type: {dest_loc.block_reason_type}")

    # Approve COMEX Vo.Bo.
    print("\n--- [STEP 2] APPROVING VO.BO. COMEX ---")
    po.action_comex_approve()
    dest_loc.invalidate_recordset()
    print(f"Location {dest_loc.name} Parent after Approval: {dest_loc.location_id.complete_name} (Expected: WH/Stock/Almacenaje)")

    print("\n--- [STEP 3] PURCHASE FLOW LOGS ---")
    logs = self.env['wmds.log'].search([('purchase', '=', po.id)], order='id asc')
    for log in logs:
        print(f"[{log.date}] Log ID: {log.id} | User: {log.user.name} | Log: {log.log}")

    # ==========================================
    # FLOW 2: SALE FLOW
    # ==========================================
    print("\n--- [STEP 4] CREATING BRAND NEW SO ---")
    so = self.env['sale.order'].create({
        'partner_id': customer.id,
        'ei_total': 1,
        'order_line': [(0, 0, {
            'product_id': product.id,
            'product_uom_qty': 1.0,
            'price_unit': 250.0,
            'name': f"Live Test - {product.name}",
        })]
    })
    print(f"SO Created: {so.name} (ID: {so.id})")

    # Add Carrier
    carrier = self.env['delivery.carrier'].search([], limit=1)
    so.carrier_selection_relational = carrier.id
    print(f"Assigned Carrier: {carrier.name}")

    # Add Attachment
    so_attach = self.env['sale.order.attachment'].create({
        'so_id': so.id,
        'attachment': b'bGl2ZV90ZXN0',
        'file_name': 'guia_live.pdf',
    })
    print("Attachment created and hooked.")

    so.action_confirm()
    print(f"SO Confirmed: State is {so.state}")

    # Get PICK picking
    pick_picking = so.picking_ids.filtered(lambda p: p.picking_type_id.name == 'Pick')
    print(f"PICK Picking Created: {pick_picking.name}")
    pick_picking.operator = mock_req.user.id

    # Create Batch
    batch = self.env['stock.picking.batch'].create({
        'operator': mock_req.user.id,
        'picking_ids': [(6, 0, [pick_picking.id])],
    })
    print(f"Batch Picking Created: {batch.name}")

    # Validate PICK
    pick_picking.action_assign()
    for move in pick_picking.move_ids:
        move.quantity = move.product_uom_qty
    pick_picking.button_validate()
    print(f"PICK {pick_picking.name} Validated.")

    # Validate PACK
    pack_picking = so.picking_ids.filtered(lambda p: p.picking_type_id.name == 'Pack')
    print(f"PACK Picking Created: {pack_picking.name}")
    pack_picking.operator = mock_req.user.id
    pack_picking.action_assign()
    for move in pack_picking.move_ids:
        move.quantity = move.product_uom_qty
    pack_picking.button_validate()
    print(f"PACK {pack_picking.name} Validated.")

    # Create Label
    ei_tag = self.env['sale.order.ei'].create({
        'so_id': so.id,
        'sequence_number': 1,
        'display_name_custom': f"{so.name}/1",
    })
    print(f"Internal Package Created: {ei_tag.display_name_custom}")

    # Bin
    from odoo.addons.wmds.controllers.dock_n_bin import DockNBin
    dock_n_bin_controller = DockNBin()
    bin_record = self.env['bin.storage'].search([], limit=1)
    
    print("Calling move_to_bin controller...")
    dock_n_bin_controller.move_to_bin(
        operator=mock_req.user.login,
        bin=bin_record.name,
        orders=[ei_tag.display_name_custom]
    )

    # Dock
    dock_record = self.env['dock.storage'].search([], limit=1)
    print("Calling move_bin_to_dock controller...")
    dock_n_bin_controller.move_bin_to_dock(
        operator=mock_req.user.login,
        bin=bin_record.name,
        dock=dock_record.name,
        selected_packages=[{'name': ei_tag.display_name_custom, 'is_full': False}]
    )

    # Dispatch
    from odoo.addons.wmds.controllers.dispatch import Dispatch
    dispatch_controller = Dispatch()
    print("Calling dispatch_packet controller...")
    dispatch_controller.dispatch_packet(
        picks_ids=[ei_tag.display_name_custom],
        operator_login=mock_req.user.login
    )

    # Verify OUT picking
    out_picking = so.picking_ids.filtered(lambda p: p.picking_type_id.name == 'Delivery Orders' or p.picking_type_id.code == 'outgoing')
    print(f"OUT Picking State after Dispatch: {out_picking.state} (Expected: done)")

    print("\n--- [STEP 5] SALE FLOW LOGS ---")
    so_logs = self.env['wmds.log'].search([('sale', '=', so.id)], order='id asc')
    for log in so_logs:
        print(f"[{log.date}] Log ID: {log.id} | User: {log.user.name} | Log: {log.log}")

except Exception as e:
    import traceback
    print("RUN TIME ERROR:", str(e))
    traceback.print_exc()

finally:
    odoo.http._request_stack.pop()
    print("\n=== RUN COMPLETED ===")

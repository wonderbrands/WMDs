# -*- coding: utf-8 -*-
import odoo.http
import unittest.mock
from odoo import fields
from datetime import datetime
import random

print("====================================================")
print("     FULL WMDS PROCESS REPLICATION WITH MULTIPLE PRODUCTS")
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

    # 2. Get resources (Multiple products)
    vendor = self.env['res.partner'].search([('supplier_rank', '>', 0)], limit=1)
    customer = self.env['res.partner'].search([('customer_rank', '>', 0)], limit=1)
    
    prod_1 = self.env['product.product'].browse(7009) # Bosch Drill Rotomartillo
    prod_2 = self.env['product.product'].browse(7010) # Bosch Drill Reversa
    prod_3 = self.env['product.product'].browse(7013) # Bosch Lijadora Orbital

    # Dynamic Empty Locations Resolve
    empty_locs = []
    all_locs = self.env['stock.location'].search([
        ('complete_name', 'like', 'WH/Stock/Almacenaje/'),
        ('usage', '=', 'internal')
    ])
    for l in all_locs:
        q = self.env['stock.quant'].search([('location_id', '=', l.id), ('quantity', '>', 0)])
        if not q:
            cuar_name = l.complete_name.replace('Stock/Almacenaje', 'Cuarentena')
            cuar_l = self.env['stock.location'].search([('complete_name', '=', cuar_name)], limit=1)
            if cuar_l:
                empty_locs.append(l)
                if len(empty_locs) == 3:
                    break

    if len(empty_locs) < 3:
        for i in range(len(empty_locs), 3):
            rand_name = f"LIVE-LOC-{random.randint(10000, 99999)}"
            l_alm = self.env['stock.location'].create({'name': rand_name, 'location_id': 152})
            self.env['stock.location'].create({'name': rand_name, 'location_id': 147})
            empty_locs.append(l_alm)

    loc_1, loc_2, loc_3 = empty_locs[0], empty_locs[1], empty_locs[2]

    # ==========================================
    # FLOW 1: PURCHASE (WITHOUT VO.BO. -> QUARANTINE -> APPROVE)
    # ==========================================
    print("\n--- [STEP 1] CREATING PO WITH MULTIPLE PRODUCTS ---")
    po = self.env['purchase.order'].create({
        'partner_id': vendor.id,
        'order_line': [
            (0, 0, {
                'product_id': prod_1.id,
                'product_qty': 2.0,
                'price_unit': 120.0,
                'name': f"Full Test - {prod_1.name}",
            }),
            (0, 0, {
                'product_id': prod_2.id,
                'product_qty': 1.0,
                'price_unit': 140.0,
                'name': f"Full Test - {prod_2.name}",
            }),
            (0, 0, {
                'product_id': prod_3.id,
                'product_qty': 3.0,
                'price_unit': 80.0,
                'name': f"Full Test - {prod_3.name}",
            }),
        ]
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

    # Move products to their respective real target locations
    print(f"Assigning products to real target locations:")
    print(f"  - {prod_1.name} -> {loc_1.complete_name}")
    print(f"  - {prod_2.name} -> {loc_2.complete_name}")
    print(f"  - {prod_3.name} -> {loc_3.complete_name}")

    for move in storage.move_ids:
        if move.product_id.id == prod_1.id:
            move.location_dest_id = loc_1.id
        elif move.product_id.id == prod_2.id:
            move.location_dest_id = loc_2.id
        elif move.product_id.id == prod_3.id:
            move.location_dest_id = loc_3.id
        move.quantity = move.product_uom_qty

    # Temporarily rename Storage to Rackeo to trigger quarantine rule
    orig_pt_name = storage.picking_type_id.name
    storage.picking_type_id.sudo().write({'name': 'Rackeo'})

    storage.button_validate()
    print(f"Storage Picking {storage.name} Validated.")
    storage.picking_type_id.sudo().write({'name': orig_pt_name})

    # Verify Quarantine block
    loc_1.invalidate_recordset()
    loc_2.invalidate_recordset()
    loc_3.invalidate_recordset()
    
    print("\n--- [VERIFYING QUARANTINE BLOCKS] ---")
    for l in [loc_1, loc_2, loc_3]:
        print(f"Location: {l.name} | Parent: {l.location_id.complete_name} (Expected: WH/Cuarentena) | Block Type: {l.block_reason_type}")

    # Approve COMEX Vo.Bo.
    print("\n--- [STEP 2] APPROVING VO.BO. COMEX ---")
    po.action_comex_approve()
    
    loc_1.invalidate_recordset()
    loc_2.invalidate_recordset()
    loc_3.invalidate_recordset()
    
    print("\n--- [VERIFYING UNBLOCKED LOCATIONS] ---")
    for l in [loc_1, loc_2, loc_3]:
        print(f"Location: {l.name} | Parent: {l.location_id.complete_name} (Expected: WH/Stock/Almacenaje) | Block Type: {l.block_reason_type}")

    print("\n--- [STEP 3] PURCHASE FLOW LOGS ---")
    logs = self.env['wmds.log'].search([('purchase', '=', po.id)], order='id asc')
    for log in logs:
        print(f"[{log.date}] Log ID: {log.id} | User: {log.user.name} | Log: {log.log}")

    # ==========================================
    # FLOW 2: SALE FLOW
    # ==========================================
    print("\n--- [STEP 4] CREATING SO WITH MULTIPLE PRODUCTS ---")
    so = self.env['sale.order'].create({
        'partner_id': customer.id,
        'ei_total': 1,
        'order_line': [
            (0, 0, {
                'product_id': prod_1.id,
                'product_uom_qty': 1.0,
                'price_unit': 200.0,
                'name': f"Full Test - {prod_1.name}",
            }),
            (0, 0, {
                'product_id': prod_2.id,
                'product_uom_qty': 1.0,
                'price_unit': 220.0,
                'name': f"Full Test - {prod_2.name}",
            }),
            (0, 0, {
                'product_id': prod_3.id,
                'product_uom_qty': 2.0,
                'price_unit': 120.0,
                'name': f"Full Test - {prod_3.name}",
            }),
        ]
    })
    print(f"SO Created: {so.name} (ID: {so.id})")

    # Add Carrier
    carrier = self.env['delivery.carrier'].search([], limit=1)
    so.carrier_selection_relational = carrier.id
    print(f"Assigned Carrier: {carrier.name}")

    # Add Attachment
    so_attach = self.env['sale.order.attachment'].create({
        'so_id': so.id,
        'attachment': b'bGl2ZV90ZXN0X2Z1bGw=',
        'file_name': 'guia_full_test.pdf',
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

    # Create Labels (Packages)
    ei_tags = []
    for i in range(1, 5):
        tag = self.env['sale.order.ei'].create({
            'so_id': so.id,
            'sequence_number': i,
            'display_name_custom': f"{so.name}/{i}",
        })
        ei_tags.append(tag)
        print(f"Internal Package Created: {tag.display_name_custom}")

    # Process each package through Bin and Dock controllers
    from odoo.addons.wmds.controllers.dock_n_bin import DockNBin
    dock_n_bin_controller = DockNBin()
    
    bin_record = self.env['bin.storage'].search([('name', '=', 'B')], limit=1)
    if not bin_record:
        bin_record = self.env['bin.storage'].search([], limit=1)

    dock_record = self.env['dock.storage'].search([('name', '=', '02')], limit=1)
    if not dock_record:
        dock_record = self.env['dock.storage'].search([], limit=1)

    for tag in ei_tags:
        print(f"Calling move_to_bin controller for Bin: {bin_record.name} - Package: {tag.display_name_custom}...")
        dock_n_bin_controller.move_to_bin(
            operator=mock_req.user.login,
            bin=bin_record.name,
            orders=[tag.display_name_custom]
        )

        print(f"Calling move_bin_to_dock controller for Bin: {bin_record.name} to Dock: {dock_record.name} - Package: {tag.display_name_custom}...")
        dock_n_bin_controller.move_bin_to_dock(
            operator=mock_req.user.login,
            bin=bin_record.name,
            dock=dock_record.name,
            selected_packages=[{'name': tag.display_name_custom, 'is_full': False}]
        )

    # Dispatch
    from odoo.addons.wmds.controllers.dispatch import Dispatch
    dispatch_controller = Dispatch()
    print("Calling dispatch_packet controller for all packages...")
    dispatch_controller.dispatch_packet(
        picks_ids=[tag.display_name_custom for tag in ei_tags],
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

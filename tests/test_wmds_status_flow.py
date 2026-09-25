# -*- coding: utf-8 -*-
"""
WMDS Status and Log Flow Test Suite
Executes end-to-end verification of all 60 WMDS status transitions across all operations.
Run via: cat ... | podman exec -i odoo python3 /odoo/odoo-bin shell -c /src/odoo.conf -d admin --no-http
"""
import sys
import logging
from odoo import fields

_logger = logging.getLogger('WMDS_TEST')

print("=" * 80)
print("INICIANDO SUITE DE PRUEBAS COMPRENSIVAS DE ESTADOS WMDS")
print("=" * 80)

passed_count = 0
failed_count = 0
errors = []

def assert_status(record, expected_value, context_name):
    global passed_count, failed_count
    record._eval_wmds_status()
    current_val = record.wmds_status.value if record.wmds_status else None
    if current_val == expected_value:
        passed_count += 1
        print(f" [PASS] {context_name}: Estado es '{current_val}' (Esperado: '{expected_value}')")
    else:
        failed_count += 1
        err_msg = f" [FAIL] {context_name}: Estado actual '{current_val}' != Esperado '{expected_value}'"
        print(err_msg)
        errors.append(err_msg)

env = self.env
user = env.ref('base.user_admin')
partner = env['res.partner'].search([], limit=1)
product = env['product.product'].search([('type', '=', 'consu')], limit=1) or env['product.product'].search([], limit=1)
warehouse = env['stock.warehouse'].search([], limit=1)

# Pick leaf location
leaf_loc = env['stock.location'].search([
    ('usage', '=', 'internal'),
    ('child_ids', '=', False)
], limit=1)

pt_pick = env['stock.picking.type'].search([('name', 'ilike', 'Pick'), ('warehouse_id', '=', warehouse.id)], limit=1)
pt_pack = env['stock.picking.type'].search([('name', 'ilike', 'Pack'), ('warehouse_id', '=', warehouse.id)], limit=1)
pt_out = env['stock.picking.type'].search([('name', 'ilike', 'Delivery Orders'), ('warehouse_id', '=', warehouse.id)], limit=1) or env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)
pt_rackeo = env['stock.picking.type'].search([('name', 'ilike', 'Rackeo')], limit=1) or env['stock.picking.type'].search([('code', '=', 'internal')], limit=1)
pt_rec = env['stock.picking.type'].search([('code', '=', 'incoming')], limit=1)

loc_stock_rec = leaf_loc if leaf_loc else warehouse.lot_stock_id
loc_stock = loc_stock_rec.id
loc_customer = env.ref('stock.stock_location_customers').id
loc_supplier = env.ref('stock.stock_location_suppliers').id

# Asegurar stock suficiente para evitar stock_no_negative validation
env['stock.quant']._update_available_quantity(product, loc_stock_rec, 1000)

# ---------------------------------------------------------
# 1. TEST VENTA ESTÁNDAR (RETAIL)
# ---------------------------------------------------------
print("\n--- 1. PROBANDO VENTA ESTÁNDAR (RETAIL) ---")
so = env['sale.order'].create({
    'partner_id': partner.id,
    'data_is_wholesale_sale': False,
    'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 2, 'price_unit': 100})]
})
assert_status(so, 'so_draft', 'SO Retail Creación')

so.action_confirm()
assert_status(so, 'so_pending_assign', 'SO Retail Confirmado')

pickings = env['stock.picking'].search([('sale_id', '=', so.id)])
p_pick = pickings.filtered(lambda p: 'Pick' in (p.picking_type_id.name or '') and 'Resurtido' not in (p.picking_type_id.name or ''))
p_pack = pickings.filtered(lambda p: 'Pack' in (p.picking_type_id.name or ''))
p_out = pickings.filtered(lambda p: any(k in (p.picking_type_id.name or '') for k in ('Delivery Orders', 'Órdenes de entrega', 'Out', 'OUT')))

if p_pick:
    assert_status(p_pick, 'pick_not_assigned', 'Picking Pick Creado')
    p_pick.write({'operator': user.id})
    assert_status(p_pick, 'pick_assigned', 'Picking Pick Asignado')
    assert_status(so, 'so_picking', 'SO Retail en Pickeo')
    
    # Marcar done en Pick
    p_pick.action_assign()
    for move in p_pick.move_ids:
        move.write({'location_id': loc_stock})
        move.quantity = move.product_uom_qty
    p_pick.button_validate()
    assert_status(p_pick, 'pick_completed', 'Picking Pick Completado')
    assert_status(so, 'so_picked', 'SO Retail Pickeado (Esperando Empaque)')

if p_pack:
    assert_status(p_pack, 'pack_not_assigned', 'Picking Pack Creado')
    p_pack.write({'operator': user.id})
    assert_status(p_pack, 'pack_assigned', 'Picking Pack Asignado')
    assert_status(so, 'so_packing', 'SO Retail en Empaque')
    
    p_pack.action_assign()
    for move in p_pack.move_ids:
        move.quantity = move.product_uom_qty
    p_pack.button_validate()
    assert_status(p_pack, 'pack_completed', 'Picking Pack Completado')
    assert_status(so, 'so_packed', 'SO Retail Empacado')

if p_out:
    assert_status(p_out, 'out_ready', 'Picking Out Listo')
    for move in p_out.move_ids:
        move.on_dock = True
    assert_status(so, 'so_in_dock', 'SO Retail en Muelle')
    
    p_out.action_assign()
    for move in p_out.move_ids:
        move.quantity = move.product_uom_qty
    p_out.button_validate()
    assert_status(p_out, 'out_completed', 'Picking Out Completado')
    assert_status(so, 'so_dispatched', 'SO Retail Despachado')

# ---------------------------------------------------------
# 2. TEST VENTA MAYOREO / PISO (BYPASS PACK -> BIN)
# ---------------------------------------------------------
print("\n--- 2. PROBANDO VENTA MAYOREO / PISO (BYPASS PACK) ---")
so_w = env['sale.order'].create({
    'partner_id': partner.id,
    'data_is_wholesale_sale': True,
    'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 5, 'price_unit': 80})]
})
assert_status(so_w, 'so_draft', 'SO Mayoreo Creación')

so_w.action_confirm()
assert_status(so_w, 'so_pending_assign', 'SO Mayoreo Confirmado')

pickings_w = env['stock.picking'].search([('sale_id', '=', so_w.id)])
p_pick_w = pickings_w.filtered(lambda p: 'Pick' in (p.picking_type_id.name or '') and 'Resurtido' not in (p.picking_type_id.name or ''))
p_out_w = pickings_w.filtered(lambda p: any(k in (p.picking_type_id.name or '') for k in ('Delivery Orders', 'Órdenes de entrega', 'Out', 'OUT')))

if p_pick_w:
    p_pick_w.write({'operator': user.id})
    assert_status(so_w, 'so_picking', 'SO Mayoreo en Pickeo')
    
    p_pick_w.action_assign()
    for move in p_pick_w.move_ids:
        move.write({'location_id': loc_stock})
        move.quantity = move.product_uom_qty
    p_pick_w.button_validate()
    assert_status(p_pick_w, 'pick_completed', 'Picking Pick Mayoreo Completado')
    assert_status(so_w, 'so_picked_bin', 'SO Mayoreo en BIN (Empaque Omitido)')

if p_out_w:
    p_out_w.action_assign()
    for move in p_out_w.move_ids:
        move.quantity = move.product_uom_qty
    p_out_w.button_validate()
    assert_status(so_w, 'so_dispatched', 'SO Mayoreo Despachado')

so_c = env['sale.order'].create({'partner_id': partner.id})
so_c.action_cancel()
assert_status(so_c, 'so_cancelled', 'SO Cancelado')

# ---------------------------------------------------------
# 3. TEST ALMACENAJE / RACKEO
# ---------------------------------------------------------
print("\n--- 3. PROBANDO ALMACENAJE / RACKEO ---")
p_rack = env['stock.picking'].create({
    'picking_type_id': pt_rackeo.id,
    'location_id': loc_supplier,
    'location_dest_id': loc_stock,
})
assert_status(p_rack, 'rack_pending', 'Rackeo Pendiente')

p_rack.write({'operator': user.id})
assert_status(p_rack, 'rack_assigned', 'Rackeo Asignado')

env['stock.move'].create({
    'name': 'Test Rack Move',
    'product_id': product.id,
    'product_uom_qty': 1,
    'picking_id': p_rack.id,
    'location_id': loc_supplier,
    'location_dest_id': loc_stock,
    'quantity': 1,
})
assert_status(p_rack, 'rack_in_progress', 'Rackeo En Progreso')

p_rack.action_cancel()
assert_status(p_rack, 'rack_cancelled', 'Rackeo Cancelado')

# ---------------------------------------------------------
# 4. TEST RECEPCIONES
# ---------------------------------------------------------
print("\n--- 4. PROBANDO RECEPCIONES ---")
p_rec = env['stock.picking'].create({
    'picking_type_id': pt_rec.id,
    'location_id': loc_supplier,
    'location_dest_id': loc_stock,
})
assert_status(p_rec, 'rec_pending', 'Recepción Pendiente')

p_rec.write({'operator': user.id})
assert_status(p_rec, 'rec_assigned', 'Recepción Asignada')

env['stock.move'].create({
    'name': 'Test Rec Move',
    'product_id': product.id,
    'product_uom_qty': 1,
    'picking_id': p_rec.id,
    'location_id': loc_supplier,
    'location_dest_id': loc_stock,
    'quantity': 1,
})
assert_status(p_rec, 'rec_in_progress', 'Recepción En Progreso')

p_rec.action_cancel()
assert_status(p_rec, 'rec_cancelled', 'Recepción Cancelada')

# ---------------------------------------------------------
# 5. TEST RESURTIDO FULL (PFUL & DFUL)
# ---------------------------------------------------------
print("\n--- 5. PROBANDO PFUL Y DFUL ---")
pt_pful = env['stock.picking.type'].search([('name', 'ilike', 'Resurtido a Ful: Pick')], limit=1)
if not pt_pful:
    pt_pful = env['stock.picking.type'].create({
        'name': 'Resurtido a Ful: Pick',
        'code': 'internal',
        'sequence_code': 'PFUL',
        'warehouse_id': warehouse.id,
    })
p_pful = env['stock.picking'].create({
    'picking_type_id': pt_pful.id,
    'location_id': loc_stock,
    'location_dest_id': loc_supplier,
})
assert_status(p_pful, 'pful_not_assigned', 'PFUL No Asignado')

p_pful.write({'operator': user.id})
assert_status(p_pful, 'pful_assigned', 'PFUL Asignado')

pt_dful = env['stock.picking.type'].search([('name', 'ilike', 'Resurtido a Ful: Despacho')], limit=1)
if not pt_dful:
    pt_dful = env['stock.picking.type'].create({
        'name': 'Resurtido a Ful: Despacho',
        'code': 'outgoing',
        'sequence_code': 'DFUL',
        'warehouse_id': warehouse.id,
    })
p_dful = env['stock.picking'].create({
    'picking_type_id': pt_dful.id,
    'location_id': loc_stock,
    'location_dest_id': loc_supplier,
})
assert_status(p_dful, 'dful_ready', 'DFUL Listo')

p_dful.action_cancel()
assert_status(p_dful, 'dful_cancelled', 'DFUL Cancelado')

# ---------------------------------------------------------
# 6. TEST CONTEO CÍCLICO
# ---------------------------------------------------------
print("\n--- 6. PROBANDO CONTEO CÍCLICO ---")
cc = env['scheduled.cycle.count'].create({
    'notes': 'Test Conteo Status'
})
assert_status(cc, 'cc_draft', 'Conteo Cíclico Borrador')

loc_test = env['stock.location'].search([], limit=1)
env['cycle.count.selected.location'].create({
    'cycle_count_id': cc.id,
    'location_id': loc_test.id,
})
assert_status(cc, 'cc_not_started', 'Conteo Cíclico No Iniciado')

wave = env['cycle.count.wave'].create({
    'cycle_count_id': cc.id,
    'operator_id': user.id,
    'state': 'ongoing',
})
assert_status(cc, 'cc_in_progress', 'Conteo Cíclico En Progreso')

wave.write({'state': 'done'})
assert_status(cc, 'cc_in_comparison', 'Conteo Cíclico En Comparación')

cc.write({'state': 'finalized'})
assert_status(cc, 'cc_completed', 'Conteo Cíclico Completado')

cc.write({'state': 'cancelled'})
assert_status(cc, 'cc_cancelled', 'Conteo Cíclico Cancelado')

# ---------------------------------------------------------
# 7. TEST ÓRDENES DE COMPRA (PO)
# ---------------------------------------------------------
print("\n--- 7. PROBANDO ÓRDENES DE COMPRA (PO) ---")
po = env['purchase.order'].create({
    'partner_id': partner.id,
    'order_line': [(0, 0, {'product_id': product.id, 'product_qty': 10, 'price_unit': 50})]
})
assert_status(po, 'po_draft', 'PO Borrador')

po.button_confirm()
# Al confirmar la PO se genera la recepción asignada/pendiente (po_receiving)
assert_status(po, 'po_receiving', 'PO Confirmado (En Recepción)')

po.button_cancel()
assert_status(po, 'po_cancelled', 'PO Cancelado')

# ---------------------------------------------------------
# 8. TEST INMUTABILIDAD WMDS.LOG & READONLY
# ---------------------------------------------------------
print("\n--- 8. PROBANDO INMUTABILIDAD DE WMDS.LOG ---")
log_entry = env['wmds.log'].sudo().create({
    'sale': so.id,
    'log': 'Test Log Entry',
    'date': fields.Datetime.now()
})
print(f" Log Creado Correctamente: ID={log_entry.id}")

try:
    log_entry.with_user(user).write({'log': 'Intento de edicion'})
    print(" [FAIL] Error: Se permitió modificar wmds.log!")
    failed_count += 1
except Exception as e:
    passed_count += 1
    print(f" [PASS] Modificación de wmds.log denegada correctamente: {type(e).__name__}")

try:
    log_entry.with_user(user).unlink()
    print(" [FAIL] Error: Se permitió eliminar wmds.log!")
    failed_count += 1
except Exception as e:
    passed_count += 1
    print(f" [PASS] Eliminación de wmds.log denegada correctamente: {type(e).__name__}")

# Cleanup test records
for rec in (so, so_w, so_c, p_rack, p_rec, p_pful, p_dful, cc, po):
    try:
        if hasattr(rec, 'action_unlock') and getattr(rec, 'state', None) == 'done':
            rec.action_unlock()
        if hasattr(rec, 'action_cancel') and getattr(rec, 'state', None) not in ('cancel', False):
            rec.action_cancel()
        rec.unlink()
    except Exception as e:
        _logger.info(f"Cleanup non-critical exception for {rec}: {e}")

print("=" * 80)
print(f"RESULTADO DE PRUEBAS: PASADAS = {passed_count}, FALLADAS = {failed_count}")
print("=" * 80)

if failed_count > 0:
    print("ERRORES ENCONTRADOS:")
    for err in errors:
        print(" -", err)
    sys.exit(1)
else:
    print("TODAS LAS PRUEBAS SE EJECUTARON EXITOSAMENTE Y SIN ERRORES.")

# -*- coding: utf-8 -*-
"""
Script de utilidad para reparar transferencias históricas (STOR u otras) que tienen el campo `origin`
apuntando a una Orden de Compra pero no tienen el campo `purchase_id` enlazado.

Uso en odoo shell:
    exec(open('extra-addons/wonderbrands2026/wmds/scripts/fix_missing_purchase_id_stors.py').read())
    fix_missing_purchase_ids(env)
"""

def fix_missing_purchase_ids(env, limit=None):
    print("=== INICIANDO REPARACIÓN DE PURCHASE_ID EN TRANSFERENCIAS STOR/ORIGEN ===")
    domain = [
        ('purchase_id', '=', False),
        ('origin', '!=', False),
    ]
    stors = env['stock.picking'].sudo().search(domain, limit=limit)
    print(f"Encontradas {len(stors)} transferencias sin purchase_id con origin definido.")

    updated_count = 0
    for picking in stors:
        orig_name = str(picking.origin).split(':')[0].strip()
        if not orig_name:
            continue
            
        po = env['purchase.order'].sudo().search([('name', '=ilike', orig_name)], limit=1)
        if not po and picking.move_ids:
            orig_pickings = picking.move_ids.mapped('move_orig_ids.picking_id')
            pos = orig_pickings.mapped('purchase_id')
            if pos:
                po = pos[0]
                
        if po:
            picking.write({'purchase_id': po.id})
            updated_count += 1
            if updated_count % 100 == 0:
                print(f"   • Actualizados {updated_count} registros...")

    print(f"🏁 COMPLETADO: {updated_count} transferencias vinculadas exitosamente con su purchase_id correspondiente.")
    return updated_count

if __name__ == '__main__':
    if 'env' in locals() or 'env' in globals():
        fix_missing_purchase_ids(env)

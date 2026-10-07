import re

with open('controllers/order_channel.py', 'r') as f:
    content = f.read()

new_logic = """
            # 1. Obtener canales dinámicos
            env.cr.execute("SELECT DISTINCT channel FROM sale_order WHERE channel IS NOT NULL AND channel != '' ORDER BY channel")
            raw_channels = [r[0] for r in env.cr.fetchall() if r[0]]
            available_channels = sorted(list(set(c.strip() for c in raw_channels if c and c.strip())))

            # 2. Dominio base en sale.order (status Yuju no diga 'sent')
            domain_so = [
                '|',
                ('order_progress', '!=', 'sent'),
                ('order_progress', '=', False)
            ]

            if channel_filter and channel_filter != 'all':
                domain_so.append(('channel', 'ilike', channel_filter))

            if query:
                # Buscar pickings que coincidan con la búsqueda
                matching_picks = picking_model.sudo().search([
                    '|', '|',
                    ('name', 'ilike', query),
                    ('carrier_tracking_ref', 'ilike', query),
                    ('origin', 'ilike', query)
                ], limit=100)
                so_ids_from_picks = matching_picks.mapped('sale_id').ids

                domain_so.extend([
                    '|', '|', '|',
                    ('name', 'ilike', query),
                    ('partner_id.name', 'ilike', query),
                    ('channel_order_id', 'ilike', query),
                    ('id', 'in', so_ids_from_picks)
                ])

            # Buscar SOs (buscamos más del límite porque luego filtraremos por SLA)
            sale_orders = env['sale.order'].sudo().search(domain_so, order='id desc', limit=limit * 10)

            valid_pickings = []
            for so in sale_orders:
                if len(valid_pickings) >= limit:
                    break
                
                # Obtener solo el ÚLTIMO picking asociado a esta SO
                last_pick = picking_model.sudo().search([('sale_id', '=', so.id)], order='id desc', limit=1)
                if not last_pick:
                    continue
                
                # 3. Aplicar Filtro SLA sobre el último picking
                if status_filter != 'all':
                    if last_pick.state in ('done', 'cancel'):
                        continue
                    if not last_pick.sla_date:
                        continue
                    
                    if status_filter == 'overdue' and not (last_pick.sla_date < now_utc):
                        continue
                    elif status_filter == 'critical_1h' and not (now_utc <= last_pick.sla_date <= in_1h_utc):
                        continue
                    elif status_filter == 'urgent_2h' and not (in_1h_utc < last_pick.sla_date <= in_2h_utc):
                        continue
                    elif status_filter == 'warning_6h' and not (in_2h_utc < last_pick.sla_date <= in_6h_utc):
                        continue
                    elif status_filter == 'notice_24h' and not (in_6h_utc < last_pick.sla_date <= in_24h_utc):
                        continue
                    elif status_filter == 'normal' and not (last_pick.sla_date > in_24h_utc):
                        continue
                
                valid_pickings.append(last_pick)

            pickings = valid_pickings

            # Optimización masiva BATCH para logs de WMDS
"""

# Regex to replace from `env.cr.execute("SELECT DISTINCT channel` to `# Optimización masiva BATCH`
pattern = re.compile(r'env\.cr\.execute\("SELECT DISTINCT channel.*?# Optimización masiva BATCH para logs de WMDS .*?\n', re.DOTALL)

new_content = pattern.sub(new_logic, content)

with open('controllers/order_channel.py', 'w') as f:
    f.write(new_content)

print("Updated successfully!")

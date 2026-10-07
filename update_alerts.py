import re

with open('controllers/order_channel.py', 'r') as f:
    content = f.read()

new_logic = """
            now_utc = fields.Datetime.now()
            in_1h_utc = now_utc + timedelta(hours=1)

            env.cr.execute('''
                SELECT p.sla_date
                FROM sale_order s
                JOIN LATERAL (
                    SELECT state, sla_date
                    FROM stock_picking
                    WHERE sale_id = s.id
                    ORDER BY id DESC
                    LIMIT 1
                ) p ON true
                WHERE (s.order_progress != 'sent' OR s.order_progress IS NULL)
                  AND p.state NOT IN ('done', 'cancel')
                  AND p.sla_date IS NOT NULL
            ''')
            
            rows = env.cr.fetchall()
            critical_count = 0
            overdue_count = 0
            
            for (sla_date,) in rows:
                if sla_date < now_utc:
                    overdue_count += 1
                elif now_utc <= sla_date <= in_1h_utc:
                    critical_count += 1

            return {
"""

pattern = re.compile(r'            now_utc = fields.Datetime.now\(\)\n.*?return \{', re.DOTALL)
new_content = pattern.sub(new_logic, content)

with open('controllers/order_channel.py', 'w') as f:
    f.write(new_content)

print("Updated alerts successfully!")

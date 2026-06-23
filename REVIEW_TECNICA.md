# REVIEW TÉCNICA — Módulo WMDs (v18.0)

## 1. RESUMEN EJECUTIVO Y ARQUITECTURA GENERAL

### Propósito del Sistema
Sistema de gestión de almacén local (Warehouse Management Dispatch System) que extiende Odoo 18 con funcionalidades avanzadas de logística: flujo BIN → DOCK → despacho, conteo cíclico de inventario, planes de pickeo masivo (batch picking), gestión de cuarentenas COMEX para compras, mesa de empaque, y despacho manual/fulfillment. Reemplazo planificado del WMS actual.

### Stack Tecnológico

| Capa | Tecnología | Versión/Detalle |
|------|-----------|-----------------|
| Backend framework | Odoo (Python) | 18.0 |
| Frontend SPA | Vue 3 + PrimeVue | v3.5+ (embebido como IIFE bundle) |
| State management | Pinia | Vue store para frontend |
| Frontend build | Vite | IIFE library output |
| Barcode rendering | python-barcode | Code128 SVG |
| QR generation | qrcode (Python) | PNG, Base64 |
| Async tasks | PostgreSQL advisory locks | Threading nativo |
| Testing | Odoo TransactionCase | unittest |
| OWL patches | @stock_barcode models | Monkey-patching vía `patch()` |
| Dependencia externa | WB_data_sale_order | Módulo interno Wonderbrands |
| Dependencia externa | wb_printer_IoT | Impresión de guías y etiquetas |

### Patrón Arquitectónico
Arquitectura **híbrida MVC + SPA embebida**:

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (Navegador)                │
│  ┌──────────────────────┐  ┌──────────────────────┐ │
│  │   Vue 3 SPA (Pinia)  │  │  OWL Barcode Module  │ │
│  │   /wmds (portal)     │  │  (stock_barcode nativo)│ │
│  └─────────┬────────────┘  └──────────┬───────────┘ │
└────────────┼───────────────────────────┼─────────────┘
             │ JSON-RPC (/wmds/v2/*)     │ fetch() + ORM
             ▼                           ▼
┌─────────────────────────────────────────────────────┐
│            Capa de Controladores (HTTP)               │
│  15 controladores con ~60 endpoints JSON-RPC          │
└────────────────────┬────────────────────────────────┘
                     │ request.env[]
                     ▼
┌─────────────────────────────────────────────────────┐
│               Capa de Modelos (ORM)                   │
│  15 modelos: herencia de stock.* + modelos propios    │
│  Logs, BIN/DOCK, Queued Tasks, Cycle Count, Dispatch  │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│              PostgreSQL (Advisory Locks)              │
│  + almacenamiento de imágenes (QR/Barcode en base64)  │
└─────────────────────────────────────────────────────┘
```

- **No hay capa de servicio intermedia**: los controladores contienen lógica de negocio directamente.
- **Duplicación back-end/front-end**: operaciones como `move_to_bin` existen tanto en el controlador (síncrono, <10 ítems) como en el modelo `wmds.queued_tasks` (asíncrono, >10 ítems).
- **Acoplamiento fuerte con módulos internos**: `WB_data_sale_order`, `wb_printer_IoT`.

### Flujo de Datos Principal

1. **Login**: Operador escanea QR/barcode → `user_access.py` valida → sessionStorage + Pinia store
2. **Asignación**: Manager asigna operador/BIN a picks/batches → `get_picks.py:post_pick_assign_operator`
3. **Pickeo**: Operador escanea productos → `barcode_controller.py:process_scan` actualiza `wmds_picked_qty`
4. **Validación**: `barcode_controller.py:validate_operation` → sincroniza `quantity`, llama `button_validate()` → backorders automáticos
5. **Movimiento a BIN**: `dock_n_bin.py:move_to_bin` (>10 → queued task) → estado `on_bin=True`
6. **Movimiento a DOCK**: `dock_n_bin.py:move_bin_to_dock` (>10 → queued task) → estado `on_dock=True`
7. **Despacho**: `dispatch.py:dispatch_packet` → EI tags marcados `dispatched=True` → validación OUT automática
8. **Logging transversal**: Cada operación crea `wmds.log` con propagación automática pick↔batch↔sale↔purchase

---

## 2. ANÁLISIS MÓDULO POR MÓDULO

### 2.1 Modelos (models/)

#### `stock_flow_edit.py` (413 líneas)
- **Responsabilidad**: Extensión masiva de `stock.picking`, `stock.picking.batch`, `stock.move`, `stock.move.line`, `stock.location` con lógica WMDS.
- **Dependencias**: `wmds.log`, `wmds.stock.status`, `bin.storage`, `wb_printer_IoT`.
- **Calidad**: Acceptable. La lógica de validación de Rackeo N1 está duplicada entre `button_validate()` y `barcode_controller.py:process_dest_location_scan`. El `_get_stock_barcode_data()` está definido dos veces en `StockWMDS` y `BatchWMDS` con lógica muy similar pero no idéntica. El `_FORBIDDEN_LOCATIONS` está hardcodeado como constante de clase en vez de ser configurable.

#### `wmds_queued_tasks.py` (745 líneas)
- **Responsabilidad**: Cola de tareas asíncronas para operaciones de alto volumen (>10 ítems). Tipos: `move_to_bin`, `move_to_dock`, `dispatch_package`.
- **Dependencias**: PostgreSQL advisory lock (847192847), `threading`, Odoo ORM en `SUPERUSER_ID`.
- **Calidad**: Mixta. Bien diseñado el patrón de advisory lock para evitar concurrencia entre workers. Sin embargo:
  - Uso excesivo de `self.env.cr.commit()` que rompe la atomicidad de Odoo
  - `_update_progress()` escribe sin verificar estado concurrente
  - `_execute_move_to_bin()` y `_execute_move_to_dock()` duplican ~80% de la lógica de los controladores `dock_n_bin.py`
  - La caché `so_out_closed` acelera el despacho pero podría quedar inconsistente si el OUT se reabre durante el procesamiento del lote

#### `purchase_flow_edit.py` (336 líneas)
- **Responsabilidad**: Flujo COMEX para compras: VoBo, liberación de cuarentenas, creación de transferencias internas.
- **Dependencias**: `stock.picking`, `stock.quant`, `stock.location`, `wmds.log`.
- **Calidad**: Buena. `_get_quarantine_from_rackeos()` tiene diseño sólido con agrupación por STOR picking. Problemas:
  - `import requests` no utilizado (línea 6)
  - Llamadas a `logging.info()` con `\n\n` que polucionan los logs de producción
  - `_create_release_pickings()` usa `button_validate()` que abre transacciones implícitas; si falla un picking los anteriores ya están validados sin rollback

#### `dock_n_bin.py` (208 líneas)
- **Responsabilidad**: Modelos BIN/DOCK storage, herencia de `stock.move` y `sale.order.ei` con campos WMDS.
- **Dependencias**: `qrcode`, `carriers.list`, `sale.order.ei`.
- **Calidad**: Buena. QR generación duplicada con `user.py`. El `SaleOrderEIWMDS.create()` hace un bypass del `so_id` para evitar numeración automática del padre — frágil ante cambios en el módulo padre.

#### `wmds_log.py` (122 líneas)
- **Responsabilidad**: Log unificado para picks, batches, SOs, POs, y cycle counts.
- **Dependencias**: Todos los modelos principales.
- **Calidad**: Buena. La propagación automática vía `_propagate_log()` con flag `wmds_log_duplicating` previene recursión infinita. Diseño limpio.

#### `user.py` (120 líneas)
- **Responsabilidad**: UUID de 8 dígitos, barcode Code128 y QR para operadores.
- **Dependencias**: `python-barcode`, `qrcode`.
- **Calidad**: Buena. El `_generate_packer_uuid()` usa raw SQL (`cr.execute`) en vez del ORM — la consulta usa parámetros vinculados así que no hay riesgo de SQL injection, pero rompe la abstracción del ORM.

#### `cyclic_count.py` (73 líneas)
- **Responsabilidad**: Modelos para conteo cíclico: `scheduled.cycle.count`, `cycle.count.selected.location`, `cycle.count.wave`, `cycle.count.line`.
- **Dependencias**: `stock.location`, `res.users`.
- **Calidad**: Básica. El `create()` de `ScheduledCycleCount` usa `last_rec.id + 1` para generar secuenciales — esto produce huecos si se borran registros y no es thread-safe.

### 2.2 Controladores (controllers/)

| Archivo | Líneas | Endpoints | Complejidad |
|---------|--------|-----------|-------------|
| `cycle_count.py` | 1123 | 20 | Muy alta |
| `dock_n_bin.py` | 785 | 14 | Alta |
| `get_picks.py` | 691 | 7 | Media |
| `barcode_controller.py` | 571 | 6 | Alta |
| `dispatch_session_controller.py` | 461 | 8 | Media |
| `dispatch.py` | 230 | 3 | Media |
| `batch_pickings.py` | 266 | 4 | Media |
| `operators.py` | 204 | 5 | Media |
| `get_operation_url.py` | 192 | 3 | Baja |
| `log_stock_record.py` | 134 | 2 | Baja |
| `user_access.py` | 134 | 4 | Baja |
| `pending_tasks.py` | 105 | 1 | Baja |
| `pickings.py` | 60 | 1 | Baja |
| `portal_wmds.py` | 9 | 1 | Baja |

#### `cycle_count.py` (1123 líneas — archivo más grande)
- **Crítico**: 20 endpoints en un solo archivo. Debe refactorizarse en al menos 2-3 archivos.
- **Problema**: La función `convert_value_in_label()` está duplicada de `get_picks.py`.
- **N+1 queries**: `get_cycle_count_details()` itera locations y hace búsquedas para cada una.
- **Rendimiento**: `get_locations_by_range()` carga todas las ubicaciones y las filtra en Python con regex compilado — aceptable para warehouses pequeños, problemático para >10K ubicaciones.

#### `dock_n_bin.py` (785 líneas)
- `move_to_bin()` y `move_bin_to_dock()` son endpoints largos (>200 líneas cada uno) mezclando validación, lógica de negocio, creación de logs y manejo de estado.
- `search_manual_dispatch()` hace múltiples queries anidadas por SO (N+1).

#### `barcode_controller.py`
- `process_dest_location_scan()`: Lógica COMEX compleja con múltiples condiciones anidadas — necesita extracción a métodos helper.
- `validate_operation()`: Hace stock check, sincronización `quantity`, validación, manejo de backorders, y logística DFUL en un solo método de 130 líneas.

### 2.3 Frontend (static/src/)

#### Vue 3 SPA (`WMDs_Component_Project/`)
- **Store (`store/index.js`)**: 701 líneas mezclando estado, acciones, llamadas API, mapeo de columnas, y configuración de UI. Violación clara del principio de responsabilidad única. Debe dividirse en módulos por dominio (picks, batch, operators, cycle_count, dispatch).
- **`OdooManagerMiddleware.js` (604 líneas)**: Mapa de 50+ endpoints JSON-RPC con dos modos (dev/prod). El modo dev tiene datos mock hardcodeados extensos — usar MSW o mocks de Vitest sería más mantenible.
- **`RolePickerEngine.js`**: Lógica de login con dos modos bien separada. La expiración de sesión de 12h en sessionStorage es razonable pero el token no se refresca.

#### OWL Patches (`barcode_behaviour.js`)
- **`_enviar_log()`**: Usa `fetch()` directo en vez del RPC de Odoo — esto es frágil (no maneja sesiones Odoo, no usa CSRF tokens estándar).
- **`_metodo_final_post_validacion()`**: Navegación forzada vía `window.location.href` — rompe el SPA si el usuario está en el frontend Vue.
- **`_processBarcode()`**: Modifica la funcionalidad core de stock_barcode con un parche — si Odoo actualiza `_processBarcode`, este parche puede romperse silenciosamente.

### 2.4 Seguridad

#### `ir.model.access.csv`
| Problema | Gravedad |
|----------|----------|
| `wmds.dispatch.sheet` sin grupo (acceso total a todos los usuarios) | **CRÍTICO** |
| `wmds.dispatch.session` y `.line` con create/write para `base.group_user` | ALTO |
| `wmds.queued_tasks` con create/write para `base.group_user` | ALTO |
| Sin ACLs para `scheduled.cycle.count`, `cycle.count.selected.location`, `cycle.count.wave`, `cycle.count.line` | **CRÍTICO** |

#### CSRF
- `check_pack_assigned` y `check_bin_assigned` usan `csrf=False` — deben usar `csrf=True` como el resto de endpoints.

#### Controladores
- Múltiples endpoints usan `.sudo()` sin verificación de permisos específicos, delegando toda la seguridad a la presencia de `auth='user'`.

---

## 3. AUDITORÍA DE CALIDAD Y PUNTOS CRÍTICOS

### 3.1 Deuda Técnica y Anti-patrones

| Anti-patrón | Ubicación | Detalle |
|-------------|-----------|---------|
| **Lógica duplicada** | `dock_n_bin.py` ↔ `wmds_queued_tasks.py` | `move_to_bin` y `move_to_dock` implementados dos veces (controlador síncrono + tarea asíncrona) |
| **Función duplicada** | `get_picks.py:9` ↔ `cycle_count.py:9` | `convert_value_in_label()` definida idénticamente en dos archivos |
| **QR code duplicado** | `user.py`, `dock_n_bin.py` | Tres modelos generan QR codes con lógica casi idéntica — extraer a mixin |
| **God controller** | `cycle_count.py` (1123 líneas) | 20 endpoints en un solo archivo |
| **God store** | `store/index.js` (701 líneas) | Mezcla estado, API, UI config y business logic |
| **Magic numbers** | `wmds_queued_tasks.py:98` | Advisory lock ID `847192847` hardcodeado — debería ser constante documentada |
| **Raw SQL** | `user.py:52` | `cr.execute()` en vez de usar el ORM |
| **`import requests`** | `purchase_flow_edit.py:6` | Import no utilizado |
| **`logging.info()` con saltos** | `purchase_flow_edit.py:99,112,201` | `\n\n` en mensajes de log — polución de logs |
| **Mocks en tests** | `test_rackeo_n1.py:119-133` | `bc.request = mock_request` muta estado global del módulo — no thread-safe |

### 3.2 Rendimiento y Escalabilidad

| Problema | Impacto | Ubicación |
|----------|---------|-----------|
| **N+1 queries en loops** | Alto | `dispatch.py:dispatch_packet` (por tag busca picking), `cycle_count.py:get_cycle_count_details`, `dock_n_bin.py:search_manual_dispatch` |
| **Procesamiento síncrono para >10 ítems** | Alto | `dispatch.py:dispatch_packet` procesa todos los EI tags en una sola transacción — si hay 100 tags y falla el #50, los primeros 49 quedan aplicados sin rollback completo |
| **Caché volátil en threads** | Medio | `wmds_queued_tasks.py`: `so_out_closed` diccionario en `_execute_dispatch_package` — si el OUT se reabre durante el batch, paquetes posteriores usan caché stale |
| **Carga masiva de ubicaciones** | Medio | `cycle_count.py:get_locations_by_range` carga todas las ubicaciones con `complete_name =ilike 'WH/Stock/%'` y filtra en Python |
| **Multiple `search_count` por BIN/DOCK** | Bajo | `dock_n_bin.py:active_bins` hace 2 `search_count` por cada BIN registrado |
| **PDF síncrono en request HTTP** | Medio | `dispatch_sheet_print_controller.py` renderiza QWeb PDF en el hilo de la request — puede timeout con sessions grandes |
| **`env.invalidate_all()` en cada iteración** | Bajo | `wmds_queued_tasks.py:705` — necesario para evitar MemoryError pero invalida caché del ORM forzando relecturas |

### 3.3 Manejo de Errores y Robustez

| Problema | Gravedad |
|----------|----------|
| **`except Exception as e` genérico en TODOS los controladores** — captura KeyboardInterrupt, SystemExit, MemoryError | Alto |
| **Tracebacks expuestos al cliente** — `return {"error": f"{str(e)}\n{traceback.format_exc()}"}` en múltiples controladores | **CRÍTICO** |
| **`request.env.cr.rollback()` en catch exterior de `dock_n_bin.py`** — no hace rollback de writes individuales exitosos previos al fallo | Alto |
| **No hay códigos de error estructurados** — el frontend debe hacer string matching en mensajes de error | Medio |
| **`MemoryError` manejado solo en `_execute_dispatch_package`** — otros métodos asíncronos no lo contemplan | Medio |
| **`dispatch.py:dispatch_packet` no usa savepoints** — a diferencia de `_execute_dispatch_package` que sí los usa | Alto |
| **`batch_pickings.py:save_batch`** — si falla `action_confirm()`, los logs ya fueron creados sin rollback | Medio |

### 3.4 Seguridad

| Problema | Gravedad |
|----------|----------|
| **ACLs faltantes** para modelos de cycle count (4 modelos sin entrada en `ir.model.access.csv`) | **CRÍTICO** |
| **`wmds.dispatch.sheet` sin restricción de grupo** — cualquier usuario autenticado puede crear/leer/escribir/eliminar | **CRÍTICO** |
| **`auth='user'` + `.sudo()` sin verificación de permisos de grupo** en múltiples endpoints | Alto |
| **Exposición de tracebacks en respuestas JSON de error** | Medio |
| **`csrf=False` en `check_pack_assigned` y `check_bin_assigned`** | Bajo |

---

## 4. PLAN DE ACCIÓN Y RECOMENDACIONES

### [CRÍTICO / ALTO] — Correcciones Inmediatas

1. **Añadir ACLs para los 4 modelos de cycle count** (`ir.model.access.csv`): `scheduled.cycle.count`, `cycle.count.selected.location`, `cycle.count.wave`, `cycle.count.line`.

2. **Restringir `wmds.dispatch.sheet`** a grupo `group_wmds_manager` o al menos `base.group_user` en `ir.model.access.csv`.

3. **Eliminar exposición de tracebacks** en todas las respuestas de error de controladores. Reemplazar:
   ```python
   return {"error": f"{str(e)}\n{traceback.format_exc()}"}
   ```
   por:
   ```python
   _logger.error("Error in endpoint: %s", traceback.format_exc())
   return {"error": str(e), "error_code": "INTERNAL_ERROR"}
   ```

4. **Añadir `csrf=True`** a `check_pack_assigned` y `check_bin_assigned`.

5. **Agregar savepoints en `dispatch.py:dispatch_packet`** (modo síncrono <10 ítems) para que cada tag falle independientemente, igual que hace `_execute_dispatch_package`.

6. **Añadir manejo de `MemoryError`** en `_execute_move_to_bin` y `_execute_move_to_dock`.

### [MEDIO] — Mejoras de Arquitectura y Modularización

7. **Extraer `convert_value_in_label()` a un módulo compartido** (e.g., `controllers/wmds_utils.py`).

8. **Extraer generación de QR a un mixin reutilizable** (`WmdsQRMixin`) para `bin.storage`, `dock.storage` y `res.users`.

9. **Dividir `cycle_count.py`** (1123 líneas) en al menos 3 archivos: `cycle_count_crud.py`, `cycle_count_operations.py`, `cycle_count_waves.py`.

10. **Dividir el Pinia store** (`store/index.js`, 701 líneas) en módulos por dominio: `stores/picks.js`, `stores/batch.js`, `stores/operators.js`, `stores/cycleCount.js`, `stores/dispatch.js`.

11. **Consolidar lógica `move_to_bin`/`move_to_dock`**: El controlador y el modelo `wmds.queued_tasks` comparten ~80% del código. Mover la lógica core de movimiento a métodos del modelo `bin.storage` o `stock.move`, invocados tanto desde el controlador como desde la tarea asíncrona.

12. **Usar `odoo.http.request.jsonrequest`** en lugar de `**kw` en controladores para tener tipado implícito de parámetros.

13. **Extraer lógica COMEX** de `barcode_controller.py:process_dest_location_scan()` a un helper dedicado o un método en `purchase.order`.

### [BAJO / DEUDA] — Mejoras Estéticas y de Mantenibilidad

14. **Eliminar `import requests`** no utilizado en `purchase_flow_edit.py:6`.

15. **Limpiar `logging.info()` con `\n\n`** en `purchase_flow_edit.py` — usar formato estándar de logging.

16. **Definir constantes para advisory lock ID** en `wmds_queued_tasks.py`:
    ```python
    WMDS_QUEUE_LOCK_ID = 847192847
    ```

17. **Migrar `user.py:52` de raw SQL a ORM**:
    ```python
    exists = self.env['res.users'].sudo().search_count([('packer_uuid', '=', new_uuid)])
    ```

18. **Refactorizar tests** (`test_rackeo_n1.py`) para usar `unittest.mock.patch` como context manager en lugar de mutación de `bc.request`.

19. **Añadir test para `_execute_dispatch_package`** con fixtures de múltiples paquetes y escenarios de error.

20. **Estandarizar orden de imports** en todos los archivos Python (isort).

21. **Documentar endpoints en un archivo OpenAPI/Swagger** o al menos un docstring consistente en cada endpoint.

22. **Considerar migrar `barcode_behaviour.js:fetch()` a `this.orm.call()`** para usar la capa RPC oficial de Odoo.

23. **Mover `_FORBIDDEN_LOCATIONS`** a un parámetro del sistema (`ir.config_parameter`) en lugar de constante hardcodeada.

24. **Añadir type hints progresivos** en los métodos Python más complejos (>50 líneas).

---

### Resumen de Métricas

| Métrica | Valor |
|---------|-------|
| Archivos Python | 19 |
| Archivos XML | 20 |
| Archivos JS/Vue | 9 |
| Líneas totales de código (~) | ~12,000 |
| Modelos propios | 11 |
| Modelos heredados | 10 |
| Endpoints API | ~60 |
| Endpoints con `csrf=False` | 2 |
| Modelos sin ACL | 4 |
| Funciones duplicadas | 3 |
| Archivos >500 líneas | 4 |
| Cobertura de tests | <5% (solo rackeo N1) |
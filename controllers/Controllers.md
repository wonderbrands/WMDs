# Controladores de WMDS

---

## 1. `barcode_controller.py` — `BarcodeController`

**Descripción:** Controlador principal del flujo de recolección (barcode/picking) en WMDS v2. Maneja la obtención de datos de operación, procesamiento de escaneos de productos y ubicaciones destino, validación de operaciones y logs de inicio de tarea.

### Endpoints:

| Ruta | Método | Descripción | Parámetros |
|---|---|---|---|
| `/wmds/v2/barcode/get_operation_data` | `POST` JSON | Obtiene los datos completos de una operación de picking (pick suelto o batch). Identifica si es PFUL/DFUL, devuelve líneas con cantidades demandadas/reservadas/recolectadas e info de ubicaciones. | `res_id` (int) — ID del registro. `res_model` (str, default `'stock.picking'`) — modelo (`stock.picking` o `stock.picking.batch`). `operator_email` (str) — email del operador. |
| `/wmds/v2/barcode/process_scan` | `POST` JSON | Procesa el escaneo de un producto (por barcode) y actualiza la cantidad recolectada (`wmds_picked_qty`) en la línea correspondiente. Valida no exceder la demanda. | `res_id` (int), `res_model` (str), `operator_email` (str), `barcode` (str), `location_barcode` (str, opcional), `increment` (int, default 1), `line_id` (int, opcional), `extra_products` (bool, opcional). |
| `/wmds/v2/barcode/log_task_start` | `POST` JSON | Registra en el log que el operador inició una tarea. | `res_id` (int), `res_model` (str), `operator_email` (str), `task_title` (str). |
| `/wmds/v2/barcode/process_dest_location_scan` | `POST` JSON | Cambia la ubicación destino de una línea de movimiento escaneando el barcode de una ubicación. Incluye lógica de COMEX (redirige a cuarentena si no hay visto bueno), validación de ubicaciones vacías y N1. | `line_id` (int), `barcode` (str) — barcode de ubicación. `operator_email` (str), `check_empty` (bool, opcional). |
| `/wmds/v2/barcode/check_locations_have_stock` | `POST` JSON | Verifica si un conjunto de ubicaciones tiene stock (quants > 0). | `res_id` (int, opcional), `res_model` (str, opcional), `location_ids` (list[int]). |
| `/wmds/v2/barcode/validate_operation` | `POST` JSON | Valida la operación completa. Sincroniza `wmds_picked_qty` → `quantity`, remueve pickings no iniciados en batches, chequea stock negativo, llama `button_validate()` o `action_done()`, maneja backorders, y en DFUL actualiza movimientos origen (`dispatched`, `on_bin`, `on_dock`). | `res_id` (int), `res_model` (str), `operator_email` (str). |

---

## 2. `batch_pickings.py` — `BatchPickController`

**Descripción:** Gestión de lotes de picking (batch picking). Permite validar picks individuales para agregarlos a un batch, crear/salvar batches, cancelarlos y remover pickings de un batch.

### Endpoints:

| Ruta | Método | Descripción | Parámetros |
|---|---|---|---|
| `/wmds/v2/engine/post/validate_pick_for_batch` | `POST` JSON | Valida que un pick sea apto para meter en un batch. Verifica existencia, estado, tipo (sale/full), que tenga SO lista para recolectar, que las líneas vengan de `A_Pickable`, y que no pertenezca ya a otro batch. | `pick` (str) — referencia (SO... o WH/PICK... o WH/PFUL...). `type_of_batch` (str) — `'sale'` o `'full'`. |
| `/wmds/v2/engine/post/save_batch` | `POST` JSON | Crea un nuevo batch con los picks validados. Asigna operador, confirma el batch y registra en log. | `batch_create` (list[str]) — referencias de picks. `operator_id` (str) — login o ID del operador. `type_of_batch` (str). |
| `/wmds/v2/engine/post/cancel_batch` | `POST` JSON | Cancela un batch, resetea cantidades recolectadas a 0. | `id` (int) — ID del batch. |
| `/wmds/v2/engine/post/remove_picking_from_batch` | `POST` JSON | Remueve un picking de un batch. Resetea cantidades recolectadas y elimina move_lines para forzar re-reserva. Si el batch queda vacío, lo cancela automáticamente. | `picking_id` (int), `batch_id` (int), `reason` (str). |

---

## 3. `cycle_count.py` — `CycleCount`

**Descripción:** Controlador completo para el flujo de conteo cíclico de inventario. Cubre la creación de ciclos con olas, asignación de operadores, bloqueo/desbloqueo de ubicaciones, validación de escaneos, finalización de olas, cierre/cancelación de ciclos, ajuste de inventario vía `stock.quant`, reporte de comparación entre olas y stock teórico, y marcado de ubicaciones como vacías.

### Endpoints:

| Ruta | Método | Descripción | Parámetros |
|---|---|---|---|
| `/wmds/v2/engine/get/cycle_counts` | `POST` JSON | Lista paginada de ciclos de conteo programados. | `page`, `per_page`, `sort_by`, `sort_order`, y cualquier campo del modelo como filtro `ilike`. |
| `/wmds/v2/engine/get/locations_by_range` | `POST` JSON | Busca ubicaciones dentro de un rango de pasillo/posición/frente/nivel, excluyendo las ya asignadas a ciclos activos y las de cuarentena. | `aisle_from` (str, default 'A'), `aisle_to` (str, default 'Z'), `position_from` (int, default 1), `position_to` (int, default 99), `level_from` (int, default 1), `level_to` (int, default 5), `front_from` (int, default 1), `front_to` (int, default 2). |
| `/wmds/v2/engine/create_full_cycle_count` | `POST` JSON | Crea un ciclo de conteo completo: bloquea ubicaciones (moviéndolas a `location_blocked`), crea olas con líneas para cada operador asignado. | `location_ids` (list[int]), `operators` (list[int]), `name` (str, notas). |
| `/wmds/v2/engine/get/cycle_count_details` | `POST` JSON | Obtiene detalles de un ciclo: estado, ubicaciones, olas. | `count_id` (int). |
| `/wmds/v2/engine/finish_cycle_count_wave` | `POST` JSON | Finaliza una ola si todas las ubicaciones planeadas fueron contadas. | `wave_id` (int). |
| `/wmds/v2/engine/close_cycle_count` | `POST` JSON | Finaliza el ciclo completo y restaura las ubicaciones a sus padres originales. | `count_id` (int). |
| `/wmds/v2/engine/cancel_cycle_count` | `POST` JSON | Cancela el ciclo, cancela olas no terminadas y restaura ubicaciones. | `count_id` (int). |
| `/wmds/v2/engine/reassign_cycle_count_wave_operator` | `POST` JSON | Reasigna el operador de una ola. | `wave_id` (int), `operator_id` (int). |
| `/wmds/v2/engine/cancel_cycle_count_wave` | `POST` JSON | Cancela una ola individual. | `wave_id` (int). |
| `/wmds/v2/engine/get/cycle_count_comparison` | `POST` JSON | Genera reporte de comparación entre conteos de todas las olas y el stock teórico. Detecta discrepancias. | `count_id` (int). |
| `/wmds/v2/engine/reopen_cycle_count_wave` | `POST` JSON | Reabre una ola finalizada/cancelada. | `wave_id` (int), `reason` (str, default 'Sin motivo especificado'). |
| `/wmds/v2/engine/adjust_cycle_count_stock` | `POST` JSON | Ajusta el stock de un producto en una ubicación vía `stock.quant` y `action_apply_inventory()`. Requiere que todas las olas estén cerradas. | `line` (dict con `product_id`, `location_id`), `new_qty` (float), `reason` (str), `count_name` (str). |
| `/wmds/v2/engine/get/cycle_count_details_minimal` | `POST` JSON | Obtiene info minimal de una ola: nombre y estado de cada ubicación (done/pending). | `wave_id` (int). |
| `/wmds/v2/engine/get/cycle_wave_lines` | `POST` JSON | Obtiene las líneas de conteo de una ola. | `wave_id` (int). |
| `/wmds/v2/engine/get/cycle_count_logs` | `POST` JSON | Obtiene los logs asociados a un ciclo. Convierte fechas a zona horaria del cliente. | `count_id` (int), `tz` (str, opcional). |
| `/wmds/v2/engine/create_waves_for_cycle` | `POST` JSON | Crea olas adicionales para un ciclo, excluyendo ubicaciones bloqueadas. | `location_ids` (list[int]), `operators` (list[int]), `cycle_count_id` (int). |
| `/wmds/v2/engine/toggle_location_block` | `POST` JSON | Alterna el bloqueo de una ubicación en un ciclo. | `count_id` (int), `location_id` (int). |
| `/wmds/v2/engine/mark_location_empty` | `POST` JSON | Marca una ubicación como vacía (sin productos) en una ola. Crea líneas con qty=0 para todos los productos que Odoo cree que hay. | `wave_id` (int), `location_id` (int), `operator_email` (str). |
| `/wmds/v2/engine/cycle_count_assigned` | `POST` JSON | Devuelve las olas asignadas a un operador (estados draft/ongoing, máximo 5). | `email` (str). |
| `/wmds/v2/engine/validate_cycle_count_location` | `POST` JSON | Valida que una ubicación escaneada pertenezca al ciclo y a la ola del operador. | `wave_id` (int), `location_name` (str — nombre o barcode de ubicación). |
| `/wmds/v2/engine/validate_cycle_count_product` | `POST` JSON | Valida un producto por barcode o SKU, devuelve stock teórico en la ubicación. | `barcode` (str), `location_id` (int, opcional). |
| `/wmds/v2/engine/log_cycle_count_line` | `POST` JSON | Registra una línea de conteo (crea o actualiza cantidad contada). | `wave_id` (int), `location_id` (int), `product_id` (int), `qty` (float), `operator_email` (str). |

---

## 4. `dispatch_session_controller.py` — `DispatchSessionController`

**Descripción:** Controlador de sesiones de despacho para operadores. Permite crear, recuperar, modificar y cerrar sesiones de despacho donde se escanean paquetes (EI) a entregar a un carrier.

### Endpoints:

| Ruta | Método | Descripción | Parámetros |
|---|---|---|---|
| `/wmds/v2/engine/post/validate_ei_carrier` | `POST` JSON | Valida que la EI pertenezca al carrier de la sesión actual. Compartido por BIN y DISPATCH. | `so_name` (str), `carrier_id` (int). |
| `/wmds/v2/engine/post/get_dispatch_session` | `POST` JSON | Busca la sesión activa del operador y devuelve todos sus datos para restaurar estado. | `operator_login` (str). |
| `/wmds/v2/engine/post/save_dispatch_session_line` | `POST` JSON | Agrega una línea de EI escaneada a la sesión. Crea la sesión si no existe. Obtiene producto y carrier automáticamente de la SO. Valida que no haya duplicados y que el carrier coincida. | `operator_login` (str), `carrier_id` (int), `ei_name` (str), `so_name` (str), `total` (int, default 0), `current` (int, default 0), `dispatched_count` (int, default 0). |
| `/wmds/v2/engine/post/remove_dispatch_session_line` | `POST` JSON | Elimina una línea de la sesión activa. Si es por cancelación, registra en wmds.log de la SO. | `operator_login` (str), `ei_name` (str), `cancelled_removal` (bool, default False). |
| `/wmds/v2/engine/post/clear_dispatch_session` | `POST` JSON | Limpia todas las líneas de la sesión sin cancelarla. | `operator_login` (str). |
| `/wmds/v2/engine/post/complete_dispatch_session` | `POST` JSON | Marca la sesión como completada, genera la hoja de salida (`wmds.dispatch.sheet`), y devuelve resumen de SOs y EIs. | `operator_login` (str). |
| `/wmds/v2/engine/post/cancel_dispatch_session` | `POST` JSON | Cancela la sesión activa. | `operator_login` (str). |
| `/wmds/v2/engine/post/get_active_dispatch_sessions` | `POST` JSON | Devuelve todas las sesiones activas (para el Manager). | Ninguno. |
| `/wmds/v2/engine/post/get_carrier_list` | `POST` JSON | Lista todos los carriers disponibles. | Ninguno. |

---

## 5. `dispatch_sheet_print_controller.py` — `DispatchSheetPrintController`

**Descripción:** Controlador para la impresión de hojas de salida de despacho. Genera el PDF vía report action de Odoo.

### Endpoints:

| Ruta | Método | Descripción | Parámetros |
|---|---|---|---|
| `/wmds/v2/engine/post/print_dispatch_sheet` | `POST` JSON | Crea/obtiene el `wmds.dispatch.sheet` y devuelve la action del reporte PDF para impresión IoT. | `session_id` (int). |

---

## 6. `dispatch.py` — `Dispatch`

**Descripción:** Controlador para el despacho de paquetes (Ecommerce y Full/Wholesale). Maneja el despacho de ítems de fulfillment (`dispatch_full_items`) y de paquetes EI (`dispatch_packet`). Para despachos grandes (>10 paquetes), encola en `wmds.queued_tasks`.

### Endpoints:

| Ruta | Método | Descripción | Parámetros |
|---|---|---|---|
| `/wmds/v2/engine/get/pending_full_dispatch` | `POST` JSON | Lista todos los movimientos de stock que están en DOCK y no han sido despachados. | Ninguno. |
| `/wmds/v2/engine/post/dispatch_full_items` | `POST` JSON | Despacha parcial o totalmente ítems de fulfillment. Actualiza `qty_dispatched`, `dispatched`, `on_dock`. | `items` (list[dict] — `[{move_id, qty}]`), `operator_login` (str). |
| `/wmds/v2/engine/post/dispatch_packet` | `POST` JSON | Despacha paquetes EI. Marca `dispatched=True`, limpia `on_dock`/`dock_id`. Si >10 paquetes, encola. Si todos los paquetes de una SO están despachados, valida automáticamente los pickings relacionados. | `picks_ids` (list[str]) — nombres de EI. `operator_login` (str). |

---

## 7. `dock_n_bin.py` — `DockNBin`

**Descripción:** Controlador central para el flujo BIN → DOCK. Maneja validación de guías/EI, movimiento a BIN, validación/bloqueo de BINs y DOCKs, movimiento BIN→DOCK, búsqueda manual de despachos, y consulta de BINs/DOCKs activos y disponibles. Soporta tanto flujo Ecommerce (EI tags) como Full/Wholesale (stock moves). Encola operaciones grandes (>10 ítems) en tareas asíncronas.

### Endpoints:

| Ruta | Método | Descripción | Parámetros |
|---|---|---|---|
| `/wmds/v2/engine/post/validate_attachment_guide` | `POST` JSON | Valida una guía/EI por su `display_name_custom`. Si no existe la etiqueta EI, intenta validar por formato `SO/N`. Devuelve conteos de procesados y despachados. | `attachment_id` (str). |
| `/wmds/v2/engine/post/move_to_bin` | `POST` JSON | Mueve paquetes o productos a un BIN. Soporta 3 modos: por `orders` (lista de EIs), por `batch_id`, o por `pick_id`. Valida no mezclar Ecommerce con Full. Asigna carrier al BIN. >10 ítems encola. | `bin` (str), `operator` (str), `orders` (list[str], opcional), `batch_id` (int, opcional), `pick_id` (int, opcional), `carrier_id` (int, opcional). |
| `/wmds/v2/engine/post/validate_bin` | `POST` JSON | Valida un BIN: existencia, estado bloqueado, contenido actual (EI tags y stock moves). | `bin` (str), `purpose` (str — `'in'` o `'out'`). |
| `/wmds/v2/engine/post/block_bin` | `POST` JSON | Bloquea un BIN. Si tiene stock, cualquiera puede. Si está vacío, solo Manager. | `bin` (str). |
| `/wmds/v2/engine/post/validate_dock` | `POST` JSON | Valida un DOCK: existencia, estado bloqueado, si ya tiene Ecommerce o Full. | `dock` (str). |
| `/wmds/v2/engine/post/move_bin_to_dock` | `POST` JSON | Mueve ítems de un BIN a un DOCK. Soporta selección parcial (`selected_packages`). Valida no mezclar tipos. Libera el BIN si queda vacío. >10 ítems encola. | `bin` (str), `dock` (str), `operator` (str), `selected_packages` (list[dict], opcional). |
| `/wmds/v2/engine/get/search_manual_dispatch` | `POST` JSON | Búsqueda manual de órdenes de venta por nombre, tracking o EI. Devuelve info de paquetes y productos. | `term` (str). |
| `/wmds/v2/engine/get/active_bins` | `POST` JSON | Lista todos los BINs que tienen ítems (Ecommerce o Full). | Ninguno. |
| `/wmds/v2/engine/get/active_docks` | `POST` JSON | Lista todos los DOCKs que tienen ítems. | Ninguno. |
| `/wmds/v2/engine/get/available_docks` | `POST` JSON | Lista DOCKs disponibles (estado `available`). | Ninguno. |
| `/wmds/v2/engine/get/available_bins` | `POST` JSON | Lista BINs disponibles. Opcionalmente filtrados por carrier. | `carrier_id` (int, opcional). |
| `/wmds/v2/engine/get/dock_contents` | `POST` JSON | Obtiene el contenido detallado de un DOCK (EI tags y stock moves). | `dock` (str). |

---

## 8. `get_operation_url.py` — `GetURLOfPick`

**Descripción:** Genera URLs de acceso a la vista de código de barras nativa de Odoo para picks o batches. También valida operaciones DFUL y obtiene la URL de la app WMDS.

### Endpoints:

| Ruta | Método | Descripción | Parámetros |
|---|---|---|---|
| `/wmds/v2/engine/get/barcode_url` | `POST` JSON | Genera la URL de la vista barcode de Odoo para un pick o batch. | `pick_name` (str). |
| `/wmds/v2/engine/get/validate_dfull_pick` | `POST` JSON | Valida un picking DFUL: existencia, formato WH/DFUL/, estado `assigned`. Actualiza los movimientos PFUL origen como despachados, maneja despacho parcial. | `pick_name` (str). |
| `/wmds/v2/engine/get/wmds-url` | `POST` JSON | Devuelve la URL de la acción principal de WMDS. | Ninguno. |

---

## 9. `get_picks.py` — `GetPicks`

**Descripción:** Controlador de consulta y gestión de picks, packs y batches. Lista pickings con paginación/filtrado, asigna operadores y BINs, consulta productos de un picking, y maneja la asignación de empaquetadores.

### Endpoints:

| Ruta | Método | Descripción | Parámetros |
|---|---|---|---|
| `/wmds/v2/engine/get/picks` | `POST` JSON | Lista paginada de pickings tipo "Pick". Filtrable por cualquier campo vía `ilike`. | `page`, `per_page`, `sort_by`, `sort_order`, y filtros opcionales como `name`, `origin`, `state`, `wmds_status`. |
| `/wmds/v2/engine/get/pick_products` | `POST` JSON | Obtiene los productos (moves) de un picking con cantidades esperadas, recolectadas y trasladadas. | `id` (int) — ID del picking. |
| `/wmds/v2/engine/post/pick_assign_operator` | `POST` JSON | Asigna operador y/o BIN a uno o varios pickings (incluyendo Packs relacionados). Reasigna si se pasa `responsible`. | `id` (int), `operation_type` (str — `'Pick'` o `'Pack'`), `operator` (dict), `operator_mail` (str), `responsible` (dict), `is_batch` (bool), `bin_id` (dict). |
| `/wmds/v2/engine/get/pack` | `POST` JSON | Lista paginada de pickings tipo "Pack". Similar a `get_picks`. | Igual que `get_picks`. |
| `/wmds/v2/engine/get/batch_details` | `POST` JSON | Obtiene detalles de un batch: picks que contiene, logs, operador, BIN, empaquetador asignado. | `id` (int). |
| `/wmds/v2/engine/post/check_pack_assigned` | `POST` JSON | Verifica si ya existe un Pack asignado (con operador) para los mismos SOs de un pick/batch. | `pick_id` (int), `is_batch` (bool). |
| `/wmds/v2/engine/post/check_bin_assigned` | `POST` JSON | Verifica si ya hay movimientos `on_bin=True` para un pick/batch. | `pick_id` (int), `is_batch` (bool). |
| `/wmds/v2/engine/get/batch_pick` | `POST` JSON | Lista paginada de batches de picking. Incluye tipo (sale/full/mix/wholesale), picks contenidos, SOs. | `page`, `per_page`, `sort_by`, `sort_order`, y filtros como `name`, `pick_type`, `picks`, `so_list`, `state`. |

---

## 10. `inherit_barcode_module_record.py` — `StockBarcodeControllerInherit`

**Descripción:** Hereda de `StockBarcodeController` (módulo `stock_barcode`). Actualmente es un passthrough — el código original que añadía el operador al registro del barcode está comentado. Solo llama a `super()`.

### Endpoints:

Hereda los endpoints del controlador padre (`stock_barcode`). No añade rutas nuevas.

---

## 11. `log_stock_record.py` — `LogStockRecord`

**Descripción:** Registra logs de operaciones de stock en `wmds.log`. Detecta automáticamente el tipo de operación (Pick, Pack, Recepción, Rackeo, etc.) y extrae cantidades de productos para el mensaje.

### Endpoints:

| Ruta | Método | Descripción | Parámetros |
|---|---|---|---|
| `/wmds/v2/engine/post/log_stock_record` | `POST` JSON | Crea un log en `wmds.log` con detalles de la operación: tipo, productos con cantidades done/demand, ubicación destino. Soporta tipos `external` y `backorder`. | `pick_id` (int), `pick_name` (str), `operator_mail` (str), `message` (str), `type` (str — `'external'` o `'backorder'`). |
| `/wmds/v2/engine/post/change_wmds_status` | `POST` JSON | **Deshabilitado** — el código está comentado. Originalmente cambiaba el estado WMDS de un picking. | (No activo) |

---

## 12. `operators.py` — `AvailableOperators`

**Descripción:** Gestión CRUD de operadores WMDS. Lista, crea, edita y regenera datos de operadores (UUID, barcode).

### Endpoints:

| Ruta | Método | Descripción | Parámetros |
|---|---|---|---|
| `/wmds/engine/available_operators` | `POST` JSON | Búsqueda de operadores por nombre. Devuelve datos incluyendo `packer_uuid`, `packer_barcode_image`, `is_packer`. | `name` (str). |
| `/wmds/v2/engine/get/operators` | `POST` JSON | Lista paginada de operadores. Filtrable por cualquier campo de `res.users`. | `page`, `per_page`, `sort_by`, `sort_order`, y filtros opcionales. |
| `/wmds/v2/engine/post/save_operator` | `POST` JSON | Crea o actualiza un operador. Asigna grupos de portal y roles WMDs. | `id` (int, opcional), `name` (str), `login` (str), `role_ids` (list[int]). |
| `/wmds/v2/engine/post/recompute_operators_data` | `POST` JSON | Recalcula `packer_uuid` y `packer_barcode_image` para todos los operadores. | Ninguno. |
| `/wmds/v2/engine/get/operator_roles` | `POST` JSON | Lista los roles disponibles (grupos que empiezan con `WMDs Operator -`). | Ninguno. |

---

## 13. `pending_tasks.py` — `PendingTasks`

**Descripción:** Devuelve las tareas pendientes de un operador según el tipo de tarea solicitado (picks, ingresos, acomodo, pack, reabastecimiento, despacho fulfillment, devoluciones, batch_pick).

### Endpoints:

| Ruta | Método | Descripción | Parámetros |
|---|---|---|---|
| `/wmds/v2/engine/get/pending_tasks` | `POST` JSON | Lista tareas pendientes del operador: picks, recepciones, acomodo (storage/rackeo), packs, reabastecimiento, despacho fulfillment, devoluciones, o batch picks. Para packs, incluye carrier y batch de origen. | `task` (str) — uno de: `'picks'`, `'ingresos'`, `'acomodo'`, `'pack'`, `'reabastecimiento'`, `'dispatch_ful'`, `'devoluciones'`, `'batch_pick'`. `email` (str) — login del operador. `tz` (str, opcional) — zona horaria. |

---

## 14. `pickings.py` — `AvailableOperators` (duplica nombre de clase con `operators.py`)

**Descripción:** Controlador legacy para búsqueda simple de pickings de tipo "Recepciones". Búsqueda por nombre exacto o wildcard `*`.

### Endpoints:

| Ruta | Método | Descripción | Parámetros |
|---|---|---|---|
| `/wmds/engine/picks` | `POST` JSON | Busca pickings de tipo "Recepciones" en estado `assigned`. | `type` (str — `'ingreso'` o `'recepcion'`), `name` (str — nombre o `'*'`). |

---

## 15. `portal_wmds.py` — `WMDS_Portal`

**Descripción:** Extiende el portal de cliente de Odoo para renderizar la vista principal de WMDS como página web.

### Endpoints:

| Ruta | Método | Descripción | Parámetros |
|---|---|---|---|
| `/wmds` | `HTTP GET` | Renderiza la plantilla `portal_wmds` (interfaz principal de WMDS). | Ninguno. |

---

## 16. `user_access.py` — `UserAccess`

**Descripción:** Controlador de autenticación y permisos de WMDS. Valida usuarios, obtiene roles y permisos, y verifica si un usuario logueado es manager.

### Endpoints:

| Ruta | Método | Descripción | Parámetros |
|---|---|---|---|
| `/wmds/engine/user` | `POST` JSON | Devuelve el rol del usuario (manager/operator/user). | `email` (str). |
| `/wmds/engine/user_validate` | `POST` JSON | Valida la sesión actual y devuelve nombre y login del usuario. | Ninguno (usa `request.uid`). |
| `/wmds/v2/engine/get/valid_user` | `POST` JSON | Busca usuario por email o `packer_uuid`. Devuelve nombre, login, UUID y barcode si es operador/manager. | `email` (str) — puede ser login o UUID. |
| `/wmds/v2/engine/get/user_role_permissions` | `POST` JSON | Devuelve nombre, login, permisos (grupos WMDs), UUID y barcode del usuario. | `email` (str). |
| `/wmds/v2/engine/post/skip_log_if_manager` | `POST` JSON | Verifica si el usuario actual es manager. Si lo es, devuelve sus datos en JSON. | Ninguno. |

---

## Resumen de responsabilidades

| Archivo | Clase | Responsabilidad principal |
|---|---|---|
| `barcode_controller.py` | `BarcodeController` | Flujo de recolección con escáner (picking) |
| `batch_pickings.py` | `BatchPickController` | Creación y gestión de lotes de picking |
| `cycle_count.py` | `CycleCount` | Conteo cíclico de inventario completo |
| `dispatch_session_controller.py` | `DispatchSessionController` | Sesiones de despacho de paquetes EI |
| `dispatch_sheet_print_controller.py` | `DispatchSheetPrintController` | Impresión de hojas de despacho |
| `dispatch.py` | `Dispatch` | Despacho de paquetes y fulfillment |
| `dock_n_bin.py` | `DockNBin` | Flujo BIN ↔ DOCK (Ecommerce + Full) |
| `get_operation_url.py` | `GetURLOfPick` | URLs de operaciones y validación DFUL |
| `get_picks.py` | `GetPicks` | Consulta y gestión de picks/packs/batches |
| `inherit_barcode_module_record.py` | `StockBarcodeControllerInherit` | Extensión (passthrough) del barcode nativo |
| `log_stock_record.py` | `LogStockRecord` | Logging de operaciones de stock |
| `operators.py` | `AvailableOperators` | CRUD de operadores |
| `pending_tasks.py` | `PendingTasks` | Tareas pendientes del operador |
| `pickings.py` | `AvailableOperators` | Búsqueda legacy de recepciones |
| `portal_wmds.py` | `WMDS_Portal` | Página principal de WMDS |
| `user_access.py` | `UserAccess` | Autenticación y permisos |
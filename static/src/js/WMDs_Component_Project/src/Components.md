# Arquitectura Vue.js de WMDS — Componentes e Interacciones

---

## Estructura del proyecto

```
src/
├── App.vue                    # Raíz: orquestador de pantallas
├── main.js                    # Bootstrap: Pinia, PrimeVue, mount
├── style.css
├── store/
│   ├── index.js               # Pinia store global (useGeneralStore)
│   └── MandatoryUncompleted.js # Estado de tareas obligatorias en progreso
└── components/
    ├── BackButton/
    ├── Forms/                  # Vistas de formulario CRUD del Manager
    ├── LoadingComponent/
    ├── ManagerComponent/       # Pantallas del Manager
    ├── ModalContextComponent/
    ├── OperatorComponent/      # Pantallas del Operador
    ├── QRScannerComponent/     # Escáner QR/Láser/Cámara
    ├── ResuableComponentIcons/
    └── RolePicker/             # Login, selección de rol, logout
```

**Tecnologías:** Vue 3 (Options API), Pinia (store), PrimeVue (UI), Quagga (barcode cámara), QrScanner (QR cámara)

**Comunicación con backend:** JSON-RPC vía `fetch()` a endpoints Odoo. La store expone `callOdoo(context, term, params)` que delega en `OdooManagerMiddleware`.

**Montaje externo:** La app se monta desde Odoo llamando `window.mountWMDSApp('#wmds-app')` en `main.js:39`.

---

## Store global (`store/index.js` — `useGeneralStore`)

### Estado principal

| Campo | Tipo | Descripción |
|---|---|---|
| `role` | `RolePickerEngine` | Identidad del usuario (login, permisos, email, UUID) |
| `current_screen` | string | Pantalla activa: `role_picker`, `manager_screen`, `operator_screen` |
| `loading` | boolean | Spinner global |
| `modal_open` | boolean | Modal del manager abierto |
| `manual_uncompleted` | `MandatoryUncompleted` | Tarea forzosa en curso (component + props) |
| `available_main_manager_screens` | object | Configuración de pantallas del manager (Picks, Packs, Operadores, Cycle Count, etc.) |
| `main_manager_screen` | object | Pantalla actual del manager seleccionada del sidebar |
| `odoo_middleware` | `OdooManagerMiddleware` | Capa de comunicación con Odoo |

### Métodos clave

| Método | Descripción |
|---|---|
| `callOdoo(context, term, params)` | Llama un endpoint Odoo vía el middleware. Muestra toasts en errores. |
| `setCurrentScreen(screen)` | Cambia la pantalla principal de la app |
| `setMainManagerScreen(screen)` | Cambia la sub-pantalla del manager |
| `executeActionByContext(context, data, extra)` | Ejecuta una acción por nombre (ver tabla abajo). Usado por escáneres para disparar flujos. |
| `executeBeforeMount()` | Ejecuta `before_mount` de la tarea obligatoria antes de mostrar el componente |

### Acciones por contexto (`executeActionByContext`)

| Contexto | Qué hace | Llamadas Odoo |
|---|---|---|
| `open_dfull_operation` | Valida WH/DFUL, abre `BarcodeOperationComponent` | `validate_dfull_pick` |
| `bin_scan_so` | Valida guía EI y la agrega al array `so` del `BinComponent` | `validate_attachment_guide`, `validate_ei_carrier` |
| `dock_validate_bin` | Valida BIN para salida, carga contenido en `DockComponent` | `validate_bin` |
| `assign_pack_for_operator` | Escanea operador Packer, valida permisos, asigna Pack | `get_user_role_permissions`, `assign_pick` |
| `assign_bin_for_ful` | Escanea BIN para fulfillment, mueve lote a BIN, opcionalmente bloquea | `validate_bin`, `move_to_bin`, `block_bin` |
| `check_pack_assigned` | Verifica si ya hay Pack asignado, si sí, libera mandatory | `check_pack_assigned` |
| `check_bin_assigned` | Verifica si ya hay BIN asignado, si sí, libera mandatory | `check_bin_assigned` |
| `post_batch_validate` | Post-validación de batch: abre scanner para asignar Packer | Ninguna directa (abre `BarcodeScannerComponent`) |

### `MandatoryUncompleted` (`store/MandatoryUncompleted.js`)

Clase que representa una tarea que **interrumpe el flujo normal** y debe completarse antes de volver.

| Campo | Descripción |
|---|---|
| `screen` | Pantalla a la que volver al terminar |
| `component` | Componente Vue a renderizar (ej: `BinComponent`, `BarcodeOperationComponent`) |
| `component_props` | Props que recibe el componente |
| `user` | Email del operador |
| `doneMandatory()` | Limpia todo y permite volver al flujo normal |

**Flujo:** `App.vue` verifica `mandatory_uncompleted.component`. Si existe, renderiza ese componente **por encima** de todo lo demás, incluso del RolePicker y OperatorComponent.

---

## Capa de comunicación: `OdooManagerMiddleware` (`Forms/OdooManagerMiddleware.js`)

Usa el patrón Strategy con dos implementaciones según `VITE_ENVIRONMENT`:

- **`OdooManagerMiddlewareDev`**: Devuelve datos mock para desarrollo sin backend.
- **`OdooManagerMiddlewareProd`**: Mapea `context` → `{url, method}` y hace `fetch()` JSON-RPC a Odoo.

### Mapa de endpoints (Prod)

El `endpointMap` mapea ~90 contextos a endpoints Odoo. Ejemplos:

| Contexto | Endpoint Odoo |
|---|---|
| `operator_list` | `/wmds/v2/engine/get/operators` |
| `pick` | `/wmds/v2/engine/get/picks` |
| `pending_tasks` | `/wmds/v2/engine/get/pending_tasks` |
| `get_operation_data` | `/wmds/v2/barcode/get_operation_data` |
| `process_scan` | `/wmds/v2/barcode/process_scan` |
| `validate_operation` | `/wmds/v2/barcode/validate_operation` |
| `dispatch_orders` | `/wmds/v2/engine/post/dispatch_packet` |
| `move_to_bin` | `/wmds/v2/engine/post/move_to_bin` |
| `cycle_count_assigned` | `/wmds/v2/engine/cycle_count_assigned` |
| (etc.) | ... |

---

## `App.vue` — Orquestador principal

### Jerarquía de renderizado (orden de prioridad)

```
1. Toast (siempre visible)
2. LoadingComponent (si store.loading)
3. mandatory_uncompleted.component   ← Tarea forzosa interrumpe todo
4. QRScannerComponent               ← Si no hay usuario identificado
5. currentScreenComponent           ← RolePicker / Manager / Operator
```

### Flujo de inicio

1. `beforeMount`: Restaura sesión de `sessionStorage` (`wmds_logged_user`)
2. `mounted`: Carga `mandatory_uncompleted` → si hay tarea pendiente, la ejecuta
3. Si no hay usuario → intenta `skipLogIfManager()` (auto-login si es manager Odoo)
4. Si no hay `current_screen` → redirige a `role_picker`

---

## `RolePickerEngine` (`RolePicker/RolePickerEngine.js`) — Autenticación

Patrón Strategy (Dev/Prod):

- **Dev**: Simula login como "John Doe" manager.
- **Prod**: 
  - `getUserFromServer(qrContent)`: Parsea JSON del QR → extrae email/login → llama `/wmds/v2/engine/get/valid_user`
  - `getRole()`: Llama `/wmds/engine/user` para obtener `manager`/`operator`
  - `getPermissions()`: Llama `/wmds/v2/engine/get/user_role_permissions`
  - `persistSessionInStorage()`: Guarda en `sessionStorage` (12h de validez)
  - `logout()`: Limpia `sessionStorage`

---

## `RolePicker.vue` — Selección de rol

- Si el usuario es **manager**: muestra botones "Manager" y "Operador"
- Si es solo **operator**: redirige directo a `operator_screen`
- En `mounted`: obtiene rol y permisos del backend

---

## `OperatorComponent.vue` — Dashboard del operador

### Flujo

1. Si el usuario tiene permiso `WMDs Operator - Packer` → renderiza `PackerView` directamente
2. Si no → muestra **tarjetas de tareas** según permisos

### Tarjetas de tareas (`taskDefinitions`)

| ID | Título | Permiso requerido | Fetch | Vista |
|---|---|---|---|---|
| `ingresos` | Recepciones | Reception | `pending_tasks` | `BarcodeOperationComponent` |
| `acomodo` | Rackeo | Forklift operator | `pending_tasks` | `BarcodeOperationComponent` |
| `batch_pick` | Plan de pickeo | Picker | `pending_tasks` | `BarcodeOperationComponent` |
| `bin` | BIN | BIN | No | `BinComponent` |
| `dock` | DOCK | DOCK | No | `DockComponent` |
| `dispatch` | Despacho | Dispatch | No | `DispatchComponent` |
| `dispatch_ful` | Despacho fulfilment | Dispatch | No | `DispatchComponentFul` (abre BarcodeOperationComponent) |
| `cycle_count_assigned` | Conteo cíclico | Stock Counter | `cycle_count_assigned` | `CycleCountOperator` |
| `reabastecimiento` | Reabastecimiento/Traslado | Replenishment | `pending_tasks` | `BarcodeOperationComponent` |
| `devoluciones` | Devoluciones | Replenishment | `pending_tasks` | `BarcodeOperationComponent` |

### Configuración de cada tarea de picking

Cada tarea con `res_model` define:

| Campo | Significado |
|---|---|
| `buttons_to_add` | Mostrar botones +1/+5/Todo |
| `buttons_to_subtract` | Mostrar botón -1 |
| `stock_input_add` | Mostrar input manual de cantidad |
| `backorder` | Permitir backorders (entrega parcial) |
| `extra_products` | Permitir exceder demanda |
| `post_validate` | Acción post-validación (ej: `post_batch_validate`) |
| `scan_source` | Requiere escanear ubicación origen |
| `scan_dest` | Requiere escanear ubicación destino |
| `check_empty_dest_location` | Verificar ubicación destino vacía (COMEX) |

### Al abrir una tarea

- Las tareas con `res_model` abren `BarcodeOperationComponent` vía `mandatory_uncompleted`
- Las tareas con `view` abren el componente especificado (BinComponent, DockComponent, etc.)
- `cycle_count_assigned` abre `CycleCountOperator`
- El operador no puede salir hasta completar la tarea (mecanismo `mandatory_uncompleted`)

---

## `BarcodeOperationComponent.vue` — Flujo de recolección (picking)

**Componente central del operador.** Maneja el escaneo paso a paso.

### Props

| Prop | Tipo | Descripción |
|---|---|---|
| `res_id` | int | ID del picking/batch |
| `res_model` | string | `stock.picking` o `stock.picking.batch` |
| `config` | object | Configuración de botones, escaneos, backorder |

### Flujo de pasos (`currentStep`)

```
location_src → product → [location_dest] → (repite)
```

1. **`location_src`**: Escanea ubicación origen (solo si `scan_source=true`)  
   → Llama `process_dest_location_scan` indirectamente vía el handler `handleScan()` que hace `process_scan`
2. **`product`**: Escanea producto (barcode) o usa botones +/-  
   → Llama `get_operation_data` para cargar, `process_scan` para cada pick
3. **`location_dest`**: Escanea ubicación destino (solo si `scan_dest=true`)  
   → Llama `process_dest_location_scan` con validación COMEX

### Interacciones con Controllers

| Acción | Controller llamado | Endpoint |
|---|---|---|
| Cargar datos | `BarcodeController` | `get_operation_data` |
| Escanear producto | `BarcodeController` | `process_scan` |
| Escanear ubicación destino | `BarcodeController` | `process_dest_location_scan` |
| Validar operación | `BarcodeController` | `validate_operation` |
| Log inicio tarea | `BarcodeController` | `log_task_start` |

### Post-validación

Tras validar, según el tipo:
- **Batch sale** → abre scanner para asignar Packer (`assign_pack_for_operator`)
- **PFUL / Batch full** → abre scanner para asignar BIN (`assign_bin_for_ful`)
- **Normal** → llama `post_validate` si existe, o cierra (`exitFlow`)

### Agrupación de líneas

Las líneas se pueden agrupar por **ubicación** o por **picking** (toggle en la UI). Auto-avance al siguiente producto incompleto en la misma ubicación.

---

## Componentes del flujo BIN → DOCK → Despacho

### `BinComponent.vue` — Escaneo a BIN

**Flujo:**
1. Selección de **Carrier** (dropdown, llama `get_carrier_list`)
2. Escaneo de **etiquetas EI** (SOXXXX/N) → valida con `validate_attachment_guide` y `validate_ei_carrier`
3. Acumula en array `so[]` con resumen visual (n/total por SO)
4. Botón "Trasladar a BIN" → escanea QR del BIN → confirma → `move_to_bin`
5. Opción de bloquear BIN (`block_bin`)

**Endpoints llamados:** `get_carrier_list`, `validate_attachment_guide`, `validate_ei_carrier`, `validate_bin`, `move_to_bin`, `block_bin`

### `DockComponent.vue` — Traslado BIN → DOCK

**Flujo:**
1. Escanea **BIN origen** (QR) → `validate_bin` con `purpose: "out"` → carga `packageDetails`
2. Escanea **DOCK destino** (QR) → `validate_dock` → valida no mezclar Ecommerce/Full
3. Confirmación → `move_bin_to_dock`
4. Soporta >10 ítems vía encolado (`status: "queued"`)

**Endpoints llamados:** `validate_bin`, `validate_dock`, `move_bin_to_dock`

### `DispatchComponent.vue` — Despacho a paquetería

**Flujo (modo individual):**
1. Selección de **Carrier** → crea/recupera sesión de despacho (`get_dispatch_session`)
2. Escaneo de **etiquetas EI** → valida con `validate_attachment_guide`
3. Persiste cada scan en backend (`save_dispatch_session_line`)
4. Maneja pedidos cancelados con modal (`CancelledModalComponent`)
5. Botón "Entregar a paquetería" → `dispatch_orders` (que llama `dispatch_packet`)
6. Completa sesión → `complete_dispatch_session` → genera **hoja de salida** imprimible
7. Impresión IoT: busca el `actionService` de Odoo OWL para enviar a IoT Box

**Endpoints llamados:** `get_carrier_list`, `get_dispatch_session`, `save_dispatch_session_line`, `remove_dispatch_session_line`, `clear_dispatch_session`, `complete_dispatch_session`, `cancel_dispatch_session`, `validate_attachment_guide`, `dispatch_orders` → `dispatch_packet`, `print_dispatch_sheet`

**Vista de impresión:** Tabla resumen por SO + detalle de escaneos + firmas. Botón para imprimir vía Odoo IoT.

### `DispatchComponentFul.vue` — Despacho Fulfillment (WH/DFUL)

**Flujo simple:**
1. Escanea **WH/DFUL/xxxxx** → `validate_dfull_pick`
2. Si es válido → `get_barcode_url` → redirige a la vista nativa de barcode de Odoo

**Endpoints llamados:** `validate_dfull_pick`, `get_barcode_url`

---

## `CycleCountOperator.vue` — Conteo cíclico (operador)

### Flujo

1. Carga info de la ola (`get_cycle_count_details_minimal`)
2. Auto-selecciona la primera ubicación pendiente
3. **Paso producto**: Escanea barcode de producto → `validate_cycle_count_product`
4. **Paso cantidad**: Setea cantidad contada con +/- o input manual → `log_cycle_count_line`
5. Botón "Ubicación vacía" → `mark_location_empty`
6. Botón "Siguiente ubicación" → avanza
7. Al terminar todas → `finish_cycle_count_wave`

**Endpoints llamados:** `get_cycle_count_details_minimal`, `validate_cycle_count_product`, `log_cycle_count_line`, `mark_location_empty`, `finish_cycle_count_wave`

---

## `PackerView.vue` — Vista del empaquetador

- Si el usuario tiene permiso `WMDs Operator - Packer`, `OperatorComponent` renderiza esto directamente
- Carga tareas de tipo "pack" vía `pending_tasks` con `task="pack"`
- Agrupa por batch (con colores por lote)
- Muestra SO, carrier, fecha
- Al hacer clic → `get_barcode_url` → redirige a vista nativa de Odoo

---

## Componentes del Manager

### `ManagerComponent.vue`

- Sidebar izquierdo (25vw) + área principal (75vw)
- Verifica que el rol sea `manager`, si no redirige a `role_picker`
- Delega a `MainManagerScreen` según la opción seleccionada

### `SidebarManagerComponent.vue`

- Menú lateral con opciones configurables desde `store.available_main_manager_screens`
- Soporta submenús (Pick → Picks / Planes de pickeo)
- Incluye botón de logout
- Opciones: Home, Picks, Planes de pickeo, Mesa de empaque, Conteo cíclico, Operadores, Despacho Manual, Bloqueo/Desbloqueo de Ubicaciones

### `MainManagerScreen.vue`

- Si la opción es `pick`, `pack`, `batch_pick`, `cycle_count`, `operator_list` → renderiza `ListView`
- Si es `manual_dispatch` → `ManualDispatch`
- Si es `location_blocking` → `LocationBlocking`
- Si es `location_unblocking` → `LocationUnblocking`
- Si es `home` → pantalla de bienvenida

### `ListView.vue` (genérico)

- Vista de tabla con paginación, ordenamiento y filtros
- Usa la configuración de columnas (`map_columns`) de la pantalla activa
- Soporta formularios modales para crear/editar registros
- Endpoints dinámicos según el contexto

### `ManualDispatch.vue`

- Flujo manual BIN → DOCK → Despacho para Managers
- Búsqueda manual de órdenes (`search_manual_dispatch`)
- Muestra BINs y DOCKs activos
- Permite despachar individualmente desde la UI del manager

### `LocationBlocking.vue` / `LocationUnblocking.vue`

- **Bloqueo**: Buscar ubicación, ver adyacentes, bloquear por sobredimensionado
- **Desbloqueo**: Listar ubicaciones bloqueadas (excluyendo cuarentenas y cíclicos), desbloquear
- Endpoints específicos: `location_blocking_search`, `location_blocking_get_adjacent`, `location_blocking_block`, `location_blocking_unblock`

---

## Componentes de escaneo

### `QRScannerComponent.vue`

- Soporta **dos modos**: láser (input oculto que captura teclado) y cámara (QR scanner)
- ToggleSwitch para cambiar entre modos
- Props: `context` (acción en store), `instructions`, `can_close`, `onScan`, `extra_data`
- Al escanear → `playBeep()` → `triggerScan(code)` → `store.executeActionByContext(context, code, extra_data)` o `onScan(code)`
- Lockout de 3 segundos tras cada scan
- Pull-to-refresh integrado

### `BarcodeScannerComponent.vue`

- Similar a QRScannerComponent pero para **códigos de barras 1D**
- Modo cámara usa **Quagga** (no QrScanner)
- Soporta `disableFocus` para pausar el escaneo láser cuando hay un input manual activo
- Misma interfaz de props y comportamiento

---

## Componentes auxiliares

| Componente | Descripción |
|---|---|
| `BackButton.vue` | Botón de retroceso genérico |
| `LoadingComponent.vue` | Spinner de carga global (usa PrimeVue ProgressSpinner) |
| `ModalContextComponent.vue` | Modal dinámico que renderiza formularios del manager |
| `CancelledModalComponent.vue` | Modal para manejar pedidos cancelados en despacho |
| `ButtonCamera.vue` / `ButtonScanner.vue` | Iconos reutilizables para activar cámara/escáner |
| `LogoutComponent.vue` | Botón de logout con icono SVG |
| `Forms/GenericFormView.vue` | Formulario genérico para crear/editar registros |
| `Forms/AggregateCreation.vue` | Formulario de creación agregada (batch picking) |
| `Forms/BatchDetailView.vue` | Vista de detalle de batch |
| `Forms/CycleCount.vue` | Gestión de conteo cíclico (manager) |
| `Forms/IngresoComponent.vue` | Formulario de recepciones |
| `Forms/PickComponent.vue` | Formulario de asignación de picks |

---

## Diagrama de flujo de pantallas

```
App.vue
│
├── [no user] → QRScannerComponent (login QR)
│   └── handleUserScan() → store.role.getUserFromServer()
│       └── current_screen = 'role_picker'
│
├── RolePicker
│   ├── [manager] → botones Manager / Operador
│   │   ├── Manager → ManagerComponent
│   │   └── Operador → OperatorComponent
│   └── [operator] → OperatorComponent (directo)
│
├── ManagerComponent
│   ├── SidebarManagerComponent (menú)
│   └── MainManagerScreen
│       ├── ListView (picks, packs, batches, operators, cycle_count)
│       ├── ManualDispatch
│       ├── LocationBlocking / LocationUnblocking
│       └── Home
│
├── OperatorComponent
│   ├── [Packer] → PackerView
│   └── [otros] → Tarjetas de tareas
│       ├── Recepciones/Rackeo/Reabastecimiento/Devoluciones → BarcodeOperationComponent
│       ├── Batch Pick → BarcodeOperationComponent → post-validate → BarcodeScannerComponent (Packer)
│       ├── BIN → BinComponent → (scan EIs → scan BIN → move_to_bin)
│       ├── DOCK → DockComponent → (scan BIN → scan DOCK → move_bin_to_dock)
│       ├── Despacho → DispatchComponent → (scan EIs → dispatch → hoja de salida)
│       ├── Despacho Ful → BarcodeOperationComponent (vía open_dfull_operation)
│       └── Conteo Cíclico → CycleCountOperator
│
└── [mandatory_uncompleted] → Componente forzoso (interrumpe todo)
    ├── BarcodeOperationComponent (picking)
    ├── BinComponent / DockComponent / DispatchComponent
    ├── CycleCountOperator
    └── BarcodeScannerComponent / QRScannerComponent (post-acciones)
```

---

## Resumen: interacción Vue ↔ Controllers Odoo

| Flujo Vue | Controllers principales usados |
|---|---|
| **Login/autenticación** | `user_access.py` → `valid_user`, `user_role_permissions`, `skip_log_if_manager` |
| **Picking (barcode)** | `barcode_controller.py` → `get_operation_data`, `process_scan`, `process_dest_location_scan`, `validate_operation`, `log_task_start`, `check_locations_have_stock` |
| **BIN → DOCK → Despacho** | `dock_n_bin.py` → `validate_attachment_guide`, `move_to_bin`, `validate_bin`, `validate_dock`, `move_bin_to_dock`, `block_bin`, + `dispatch.py` → `dispatch_packet`, `dispatch_full_items`, + `dispatch_session_controller.py` → sesiones de despacho |
| **Batch picking** | `batch_pickings.py` → `validate_pick_for_batch`, `save_batch`, + `get_picks.py` → `pick_assign_operator`, `batch_details` |
| **Conteo cíclico** | `cycle_count.py` → `cycle_count_assigned`, `validate_cycle_count_location`, `validate_cycle_count_product`, `log_cycle_count_line`, `mark_location_empty`, `finish_cycle_count_wave`, `get_cycle_count_details_minimal` |
| **Manager (listas)** | `get_picks.py` → `get_picks`, `get_pack`, `get_batch_pick`, + `operators.py` → `get_operators`, `save_operator` |
| **Tareas pendientes** | `pending_tasks.py` → `get_pending_tasks` |
| **Logs** | `log_stock_record.py` → `log_stock_record` |
| **URLs/redirecciones** | `get_operation_url.py` → `get_barcode_url`, `validate_dfull_pick` |

---

## Capa de Middleware: modo Dev vs Prod

| Archivo | Dev | Prod |
|---|---|---|
| `RolePickerEngine.js` | Login falso "John Doe", rol "manager" | `fetch()` a `/wmds/v2/engine/get/valid_user`, `/wmds/engine/user`, `/wmds/v2/engine/get/user_role_permissions` |
| `OdooManagerMiddleware.js` | Datos mock para todos los contextos (~50 casos) | `fetch()` JSON-RPC a los endpoints Odoo reales (~90 endpoints mapeados) |

El switch se controla con `import.meta.env.VITE_ENVIRONMENT === 'DEV'`.
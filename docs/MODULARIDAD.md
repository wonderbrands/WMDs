# WMDs modular: núcleo + complementos

Desde la versión `18.0.18.3`, WMDs es un **núcleo** al que se le activan **complementos** (`wmds_<funcionalidad>`)
desde Ajustes. Sin complementos instalados, WMDs se comporta exactamente igual que la 18.0 anterior: cada punto de
extensión devuelve un valor neutro.

Primer complemento: **`wmds_cancel`** (repo `wonderbrands/wmds_cancel`): reubica a Guardería (`WH/CAN/00001`) el
stock de las SO canceladas y retiene el OUT si la cancelación llega en pleno despacho.

## 1. Activar o desactivar un complemento

**WMDS → Configuración → Ajustes → Complementos.** Marcar el interruptor y guardar instala el módulo; desmarcarlo lo
desinstala (campo `module_wmds_<x>` de `res.config.settings`). El módulo debe estar en el `addons_path`; si no está,
el interruptor no hace nada.

## 2. Qué cambió en el núcleo

| Pieza | Archivo | Para qué |
|---|---|---|
| Puntos de extensión | `models/wmds_extension_points.py` | Métodos neutros que los complementos sobrescriben (§3). |
| Ajustes | `models/res_config_settings.py`, `views/res_config_settings_views.xml` | Un interruptor por complemento. |
| Funcionalidades activas | `wmds.features` + `controllers/features.py` | `POST /wmds/v2/features` → `{"features": {"cancel": true}}`. |
| Despacho síncrono | `controllers/dispatch.py` (`dispatch_packet`) | Llama a `_wmds_dispatch_prefilter`, `_wmds_dispatch_allows_cancelled` y `_wmds_dispatch_handle`. |
| Despacho en cola | `models/wmds_queued_tasks.py` (`_execute_dispatch_package`) | Llama a `_wmds_dispatch_handle`; sus errores cuentan como errores de la tarea y su log va al detalle. |
| Escaneo de guía | `controllers/dock_n_bin.py` (`validate_attachment_guide`) | Agrega `_wmds_scan_extra_values()` a la respuesta. |
| Sesión de despacho | `controllers/dispatch_session_controller.py` | `_wmds_extra_values` por línea, `_wmds_after_line_removed`, `_wmds_on_session_released`. |
| Front | `store/index.js`, `OdooManagerMiddleware.js`, `SidebarManagerComponent.vue`, `DispatchComponent.vue`, `scanQueueWorker.js` | Carga las funcionalidades al iniciar y muestra solo lo que está activo (§4). |

Un endpoint de complemento que no está instalado responde 404; el front lo convierte en un aviso
«funcionalidad no disponible» en lugar de un error.

## 3. Puntos de extensión

Todos se sobrescriben con `_inherit` y **siempre combinando con `super()`**, para no anular a otros complementos.

| Modelo | Método | Cuándo se llama | Valor neutro |
|---|---|---|---|
| `sale.order.ei` | `_wmds_dispatch_prefilter(operator)` | Antes de validar el despacho síncrono. | `(self, False)` |
| `sale.order.ei` | `_wmds_dispatch_handle(operator)` | Despacho síncrono y en cola: EI que el complemento resuelve por su cuenta. | `{consumed, handled, errors, log}` vacíos |
| `sale.order.ei` | `_wmds_scan_extra_values()` | Respuesta de `validate_attachment_guide`. | `{}` |
| `sale.order` | `_wmds_dispatch_allows_cancelled()` | Una SO cancelada puede entrar al despacho. | `False` |
| `wmds.dispatch.session` | `_wmds_after_line_removed(ei_name, so_name, cancelled_removal, operator)` | Después de quitar una línea de la sesión. | `None` |
| `wmds.dispatch.session` | `_wmds_on_session_released(lines)` | Sesión limpiada o cancelada sin despachar. | `None` |
| `wmds.dispatch.session.line` | `_wmds_extra_values()` | Datos extra por línea en `get_dispatch_session`. | `{line.id: {}}` |
| `wmds.features` | `_wmds_features()` | `/wmds/v2/features`. | `{}` |

Del resultado de `_wmds_dispatch_handle`: el núcleo deja de procesar las EI `consumed`, marca
`dispatch_status = 'success'` en las `handled`, y los `errors` detienen el despacho síncrono (en la cola se cuentan
como errores de la tarea).

## 4. Front

- Al iniciar, `App.vue` llama a `store.loadFeatures()`; `store.hasFeature('cancel')` indica si el complemento está.
- El menú lateral muestra solo las opciones cuya funcionalidad está activa.
- Despacho: con `cancel` activo, antes de enviar al transportista se refresca el estado de cancelación de las
  guías escaneadas; las guías de SO canceladas abren el modal de canceladas (embarcar / retirar).
- Escaneo offline (`scanQueueWorker`): si una guía escaneada pertenece a una SO cancelada con OUT retenido
  (`cancel_hold`), igual se guarda en la sesión para que el operador decida.
- Retirar una guía cancelada de la sesión también la quita de la cola local (Dexie), así el buffer no la reintenta.

## 5. Crear un complemento nuevo

1. Módulo `wmds_<x>` con `depends: ['wmds', ...]`.
2. Heredar los puntos de extensión que necesite (§3), siempre con `super()`.
3. Registrar su clave en `wmds.features`:
   ```python
   class WmdsFeaturesX(models.AbstractModel):
       _inherit = 'wmds.features'

       def _wmds_features(self):
           res = super()._wmds_features()
           res['x'] = True
           return res
   ```
4. En el núcleo: agregar `module_wmds_<x>` en `res_config_settings.py` y su interruptor en la vista de Ajustes.
5. En el front: condicionar la UI con `store.hasFeature('x')` y declarar en el middleware los endpoints del
   complemento con `feature: 'x'`.

## 6. Pruebas

`tests/test_settings.py` (interruptor y menú; se omite si el complemento no está en el `addons_path`) y
`tests/test_features.py` (endpoint y agregación). Con `wmds_cancel` instalado, sus 37 pruebas cubren el despacho
con complemento.

```bash
cd <carpeta-raiz-de-odoo>
PYTHONPATH=. .venv/bin/python3 setup/odoo -c odoo.conf -d wmds_test \
  -i wb_sale_wholesale_approval,wmds,wmds_cancel --test-tags /wmds,/wmds_cancel \
  --stop-after-init --http-port=8099
```
Usar siempre una BD desechable.

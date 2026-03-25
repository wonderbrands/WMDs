/** @odoo-module **/

import BarcodeModel from "@stock_barcode/models/barcode_model";
import MainComponent from "@stock_barcode/components/main";
import { patch } from "@web/core/utils/patch";

patch(BarcodeModel.prototype, {

    async _validate() {
        const isBatch = this.resModel === 'stock.picking.batch';
        const recordData = Object.assign({}, this.record);
        const originalPickingIds = isBatch ? (recordData.picking_ids || []) : [recordData.id];

        // -------------------------------------------------------
        // PRE-VALIDACIÓN: Impresión combinada para PACK
        // Dispara guía + etiqueta ZPL antes de validar
        // -------------------------------------------------------
        if (!isBatch && recordData.name && recordData.name.includes('PACK')) {
            try {
                await this._printCombinedPack(recordData.id);
            } catch (error) {
                // Si la impresión falla, logueamos pero NO bloqueamos la validación
                console.warn("Error en impresión combinada pre-validación:", error);
            }
        }

        // Validación normal (super)
        const result = await super._validate(...arguments);

        // -------------------------------------------------------
        // POST-VALIDACIÓN: Logs externos
        // -------------------------------------------------------
        try {
            if (!isBatch) {
                await this._enviar_log(recordData, "external", `Validación simple: ${recordData.name}`);
            } 
            else {
                for (const pickId of originalPickingIds) {
                    await this._enviar_log({ id: pickId }, "external", `Validación vía Batch: ${recordData.name}`);
                }

                const newBackorders = await this.orm.searchRead(
                    'stock.picking',
                    [['backorder_id', 'in', originalPickingIds]],
                    ['id', 'name']
                );

                if (newBackorders && newBackorders.length > 0) {
                    for (const bo of newBackorders) {
                        await this._enviar_log({ id: bo.id }, "backorder", `Backorder generado desde Batch ${recordData.name}`);
                    }
                }
            }
        } catch (error) {
            console.error(error);
        }

        // -------------------------------------------------------
        // POST-VALIDACIÓN: Marcar como impreso + redirección WMDS
        // -------------------------------------------------------
        if (!isBatch && recordData.name && recordData.name.includes('PACK')) {
            try {
                await this.orm.call('stock.picking', 'action_mark_barcode_printed', [[recordData.id]]);
            } catch (e) {
                console.warn("No se pudo marcar barcode_printed:", e);
            }
        }

        await this._metodo_final_post_validacion(recordData, result);
        return result;
    },

    /**
     * Dispara la impresión combinada (Guía + Etiqueta ZPL)
     * usando el reporte report_combined_pack_validate.
     * Se ejecuta vía doAction para que el IoT handler envíe a la impresora.
     */
    async _printCombinedPack(pickingId) {
        const action = await this.orm.call(
            'stock.picking',
            'action_print_combined_barcode',
            [[pickingId]]
        );
        if (action) {
            await this.action.doAction(action, {
                onClose: () => {},  // Evitar navegación al cerrar
            });
        }
    },

    async _executeAction(action) {
        if (action.res_model === 'stock.backorder.confirmation') {
            const method = action.method; 
            const oldPickIds = action.context.default_pick_ids || [];
            const result = await super._executeAction(...arguments);
            const decision = (method === 'process') ? "CREATE" : "CANCELLED";

            for (const oldId of oldPickIds) {
                await this._enviar_log({ id: oldId }, "backorder", `Decisión de Backorder: ${decision}`);
            }
            return result;
        }
        return await super._executeAction(...arguments);
    },

    async _enviar_log(pick_info, type = "external", message = "") {
        const session_wmds = window.sessionStorage.getItem("wmds_logged_user");
        let user = "";
        if (session_wmds) {
            try {
                user = JSON.parse(session_wmds).email;
            } catch (e) {}
        }

        try {
            const response = await fetch('/wmds/v2/engine/post/log_stock_record', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    params: {
                        pick_id: pick_info.id,
                        type: type, 
                        operator_mail: user,
                        message: message
                    }
                })
            });
            const res = await response.json();
            return res.result;
        } catch (error) {
            return { 'error': 'network_error' };
        }
    },

    async _metodo_final_post_validacion(record, result) {
        const session_wmds = window.sessionStorage.getItem("wmds_logged_user");
        let user = "";
        if (session_wmds) {
            try {
                user = JSON.parse(session_wmds).email;
            } catch (e) {}
        } else {
            return;
        }
        
        const isBatch = this.resModel === 'stock.picking.batch';
        let isOnlyPick = false;

        if (isBatch && record.picking_ids && record.picking_ids.length > 0) {
            const pickings = await this.orm.read('stock.picking', record.picking_ids, ['picking_type_id']);
            isOnlyPick = pickings.every(p => p.picking_type_id && p.picking_type_id[1].includes('Pick'));
        }

        if (isBatch && isOnlyPick) {
            localStorage.setItem("mandatory_uncompleted",
                JSON.stringify({
                    screen: null,
                    component: "BarcodeScannerComponent",
                    component_props: {
                        context: "assign_pack_for_operator",
                        instructions: "Escanea la linea de empaque para asignar el Pack",
                        can_close: true,
                        extra_data: {
                            pick_id: record.id,
                            is_batch: isBatch,
                            operation_type: "Pack"
                        }
                    },
                    user: user
                })
            );
        }

        try {
            const response = await fetch('/wmds/v2/engine/get/wmds-url', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ jsonrpc: "2.0", params: {} })
            });
            const data = await response.json();
            if (data.result && data.result.url) {
                window.location.href = data.result.url;
            }
        } catch (error) {}
    },
    
});

patch(MainComponent.prototype, {
    async onCustomAction(actionName) {
        const recordId = this.env.model.record.id;
        if (!recordId) return;
        try {
            const action = await this.env.services.orm.call('stock.picking', actionName, [[recordId]]);
            if (action) {
                await this.env.services.action.doAction(action);
            }
        } catch (error) {}
    }
});
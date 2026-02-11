/** @odoo-module **/

import BarcodeModel from "@stock_barcode/models/barcode_model";
import { patch } from "@web/core/utils/patch";

patch(BarcodeModel.prototype, {

    /**
     * MÉTODO 1: INTERCEPTAR VALIDACIÓN (Paso 2 y 3 del pseudo-código)
     */
    async _validate() {
        console.log("[Custom] >> 1. Iniciando proceso de validación...");
        
        const isBatch = this.resModel === 'stock.picking.batch';
        console.log(`[Custom] >> Modelo: ${this.resModel} | Es Batch: ${isBatch}`);

        // Ejecutamos la validación estándar de Odoo
        const result = await super._validate(...arguments);
        
        console.log("[Custom] >> 2. Validación estándar completada. Analizando...");

        // CASO: STOCK.PICKING (SINGLE)
        if (!isBatch) {
            console.log("[Custom] >> 2.1 Procesando Single Picking");
            await this._enviar_log(this.record, "external", `Validación simple: ${this.record.name}`);
        } 
        
        // CASO: STOCK.PICKING.BATCH
        else {
            console.log("[Custom] >> 3.1 Procesando Batch Picking");
            const pickings = this.record.picking_ids || [];
            console.log(`[Custom] >> 3.2 Iterando sobre ${pickings.length} pickings del batch`);

            for (const pickId of pickings) {
                // Obtenemos info del cache para cada pick del lote
                const pickInfo = this.cache.getRecord('stock.picking', pickId);
                console.log(`[Custom] >> 3.3 Mandando log individual para Pick ID: ${pickId}`);
                await this._enviar_log(pickInfo, "external", `Validación vía Batch: ${this.record.name}`);
            }
        }

        // 3.6 PLACEHOLDER: Espacio para método final personalizado
        await this._metodo_final_post_validacion(this.record, result);

        return result;
    },

    /**
     * MÉTODO 2: INTERCEPTAR WIZARD DE BACKORDER (Cachar creación o cancelación)
     */
    async _executeAction(action) {
        if (action.res_model === 'stock.backorder.confirmation') {
            console.log("[Custom Wizard] >> Asistente de Backorder detectado");
            
            const method = action.method; // 'process' (Crear) o 'process_cancel_backorder' (No)
            const oldPickIds = action.context.default_pick_ids || [];
            
            // Ejecutamos la acción en el servidor primero
            const result = await super._executeAction(...arguments);

            const decision = (method === 'process') ? "CREATE" : "CANCELLED";
            console.log(`[Custom Wizard] >> Decisión: ${decision} para Picks: ${oldPickIds}`);

            for (const oldId of oldPickIds) {
                const msg = `Se detectó decisión de Backorder: ${decision} para el pick ${oldId}`;
                // Enviamos log tipo backorder con la lista [viejo, ?]
                // Como el nuevo ID se genera en server, mandamos el viejo en la lista
                await this._enviar_log({ id: oldId }, "backorder", msg, [oldId, null], decision);
            }

            return result;
        }

        return await super._executeAction(...arguments);
    },

    /**
     * MÉTODO 3: ENVÍO HTTP AL CONTROLADOR
     */
    async _enviar_log(pick_info, type = "external", message = "", backorder_list = [], decision = null) {
        const session_wmds = window.sessionStorage.getItem("wmds_logged_user");
        let user = "";
        if (session_wmds) {
            try {
                const json_session = JSON.parse(session_wmds);
                user = json_session.email;
            } catch (e) { console.error("Error parseando sesión", e); }
        }

        console.log(`[HTTP Request] >> Enviando ${type} | ID: ${pick_info.id} | User: ${user}`);

        try {
            const response = await fetch('/wmds/v2/engine/post/log_stock_record', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    params: {
                        pick_id: pick_info.id,
                        type: type, // "external" o "backorder"
                        operator_mail: user,
                        message: message,
                        backorder_list: backorder_list, // [old_id, new_id]
                        decision: decision // CREATE o CANCELLED
                    }
                })
            });

            const res = await response.json();
            return res.result;
        } catch (error) {
            console.error("[Fetch Error]", error);
            return { 'error': 'Error de red', 'message': error };
        }
    },

    /**
     * MÉTODO 4: PLACEHOLDER FINAL
     */
    async _metodo_final_post_validacion(record, result) {
        console.log("[Custom] >> 3.6 Ejecución de placeholder final de iciu-erp");
        // Aquí puedes añadir lógica de limpieza o cierre de UI
    }
});
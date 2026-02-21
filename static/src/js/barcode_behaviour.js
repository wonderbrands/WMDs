/** @odoo-module **/

import BarcodeModel from "@stock_barcode/models/barcode_model";
import  MainComponent  from "@stock_barcode/components/main";
import { patch } from "@web/core/utils/patch";

patch(BarcodeModel.prototype, {

    async _validate() {
        console.log("[Custom] >> 1. Iniciando proceso de validación...");
        
        const isBatch = this.resModel === 'stock.picking.batch';
        console.log(`[Custom] >> Modelo: ${this.resModel} | Es Batch: ${isBatch}`);

        const result = await super._validate(...arguments);
        
        console.log("[Custom] >> 2. Validación estándar completada. Analizando...");

        if (!isBatch) {
            console.log("[Custom] >> 2.1 Procesando Single Picking");
            await this._enviar_log(this.record, "external", `Validación simple: ${this.record.name}`);
        } 
        else {
            console.log("[Custom] >> 3.1 Procesando Batch Picking");
            const pickings = this.record.picking_ids || [];
            console.log(`[Custom] >> 3.2 Iterando sobre ${pickings.length} pickings del batch`);

            for (const pickId of pickings) {
                const pickInfo = this.cache.getRecord('stock.picking', pickId);
                console.log(`[Custom] >> 3.3 Mandando log individual para Pick ID: ${pickId}`);
                await this._enviar_log(pickInfo, "external", `Validación vía Batch: ${this.record.name}`);
            }

            await this._metodo_final_post_validacion(this.record, result);
        }


        return result;
    },

    async _executeAction(action) {
        if (action.res_model === 'stock.backorder.confirmation') {
            console.log("[Custom Wizard] >> Asistente de Backorder detectado");
            
            const method = action.method; 
            const oldPickIds = action.context.default_pick_ids || [];
            
            const result = await super._executeAction(...arguments);

            const decision = (method === 'process') ? "CREATE" : "CANCELLED";
            console.log(`[Custom Wizard] >> Decisión: ${decision} para Picks: ${oldPickIds}`);

            for (const oldId of oldPickIds) {
                const msg = `Se detectó decisión de Backorder: ${decision} para el pick ${oldId}`;
                await this._enviar_log({ id: oldId }, "backorder", msg, [oldId, null], decision);
            }

            return result;
        }

        return await super._executeAction(...arguments);
    },

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
                        type: type, 
                        operator_mail: user,
                        message: message,
                        backorder_list: backorder_list, 
                        decision: decision 
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

    async _metodo_final_post_validacion(record, result) {
        console.log("[Custom] >> 3.6 Ejecución de placeholder final ");
        const session_wmds = window.sessionStorage.getItem("wmds_logged_user");
        let user = "";
        if (session_wmds) {
            try {
                const json_session = JSON.parse(session_wmds);
                user = json_session.email;
            } catch (e) { console.error("Error parseando sesión", e); }
        }
        
        localStorage.setItem("mandatory_uncompleted",
            JSON.stringify(
                {
                    screen: null,
                    component: "QRScannerComponent",
                    component_props: {
                        context: "assign_pack_for_operator",
                        instructions: "Escanea la linea de empaque para asignar el Pack",
                        can_close: true,
                        extra_data: {
                            pick_id: record.id,
                            operation_type: "Pack"
                        }
                    },
                    user: user
                }
            )
        );

        console.log("[Custom] >> Solicitando URL de redirección a WMDS...");
        
        try {
            const response = await fetch('/wmds/v2/engine/get/wmds-url', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    params: {}
                })
            });

            const data = await response.json();
            
            if (data.result && data.result.url) {
                console.log(`[Custom] >> Redirigiendo a: ${data.result.url}`);
                window.location.href = data.result.url;
            } else {
                console.error("[Custom] >> No se pudo obtener la URL de redirección", data.error);
            }
        } catch (error) {
            console.error("[Custom] >> Error en la petición de URL", error);
        }
    },
});

patch(MainComponent.prototype, {
    
    async onCustomAction(actionName) {
            console.log("AAAAAAAAAAAAAAAAAAAAAAAAAAAA")
            console.log(actionName)
    }
});
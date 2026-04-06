/** @odoo-module **/

import BarcodeModel from "@stock_barcode/models/barcode_model";
import MainComponent from "@stock_barcode/components/main";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";


patch(BarcodeModel.prototype, {

    _getQtyDone(line) {
        return line.qty_done || 0;
    },

    _getQtyDemand(line) {
        return line.reserved_uom_qty || line.qty_reserved || 0;
    },

    async _validate() {
        if (this.notificationCache) {
            this.notificationCache.clear();
        }
        const isBatch = this.resModel === 'stock.picking.batch';
        const isBatchSale = isBatch && this.record && this.record.pick_type === "sale";
        const isBatchFull = isBatch && this.record && this.record.pick_type === "full";
        const recordData = Object.assign({}, this.record);
        const originalPickingIds = isBatch ? (recordData.picking_ids || []) : [recordData.id];

        //para pack ni para plan de pick de pedidos se admiten parciales/incompletos/extras
        if (isBatchSale || recordData.name.includes('PACK')) {
            const linesByPicking = {};
            for (const line of this.currentState.lines) {
                const pId = line.picking_id.id || line.picking_id;
                if (!linesByPicking[pId]) { linesByPicking[pId] = []; }
                linesByPicking[pId].push(line);
            }

            let partiallyStartedName = null;
            let untouchedCount = 0;
            let completeCount = 0;
            const totalPickings = Object.keys(linesByPicking).length;

            for (const [pId, pLines] of Object.entries(linesByPicking)) {
                const pQtyDone = pLines.reduce((acc, l) => acc + this._getQtyDone(l), 0);
                const pQtyDemand = pLines.reduce((acc, l) => acc + this._getQtyDemand(l), 0);
                
                if (pQtyDone > 0 && pQtyDone < pQtyDemand) {
                    const pickData = await this.orm.read('stock.picking', [parseInt(pId)], ['name', 'origin']);
                    const name = pickData[0].name;
                    const origin = pickData[0].origin ? ` - ${pickData[0].origin}` : "";
                    partiallyStartedName = `${name}${origin}`;
                    break;
                }
                if (pQtyDone === 0) {
                    untouchedCount++;
                } else if (pQtyDone >= pQtyDemand) {
                    completeCount++;
                }
            }

            if (partiallyStartedName) {
                return this.notification(
                    _t("La orden %s está incompleta. Debe recolectar todos los productos o no recoger ninguno (regresarlos).", partiallyStartedName),
                    { type: "danger", title: _t("Orden Incompleta") }
                );
            }

            if (untouchedCount === totalPickings) {
                return this.notification(
                    _t("No ha recolectado ningún producto en este lote. No se puede validar."),
                    { type: "danger", title: _t("Lote Vacío") }
                );
            }

            if (untouchedCount > 0) {
                // Hay órdenes sin empezar, las excluimos para que Odoo no cree backorders de ellas
                try {
                    await this.orm.call('stock.picking.batch', 'action_exclude_unstarted_pickings', [[recordData.id]]);
                } catch (e) {
                    console.warn("Error excluyendo no iniciados:", e);
                }
            }
        } else {
            const hasStarted = this.currentState.lines.some(l => this._getQtyDone(l) > 0);
            const isComplete = this.currentState.lines.every(l => this._getQtyDone(l) >= this._getQtyDemand(l));
            
        }


        if (!isBatch && recordData.name && recordData.name.includes('PACK')) {
            try {
                const guiaAction = await this.orm.call(
                    'stock.picking',
                    'action_print_guia_from_barcode',
                    [[recordData.id]]
                );
                if (guiaAction) {
                    await this.action.doAction(guiaAction, { onClose: () => {} });
                }
            } catch (error) {
                console.warn("Error imprimiendo guía de envío:", error);
            }

            try {
                const etiquetaAction = await this.orm.call(
                    'stock.picking',
                    'action_print_etiqueta_from_barcode',
                    [[recordData.id]]
                );
                if (etiquetaAction) {
                    await this.action.doAction(etiquetaAction, { onClose: () => {} });
                }
            } catch (error) {
                console.warn("Error imprimiendo etiqueta ZPL:", error);
            }
        }

        const result = await super._validate(...arguments);

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

        if (!isBatch && recordData.name && recordData.name.includes('PACK')) {
            try {
                await this.orm.call('stock.picking', 'action_mark_barcode_printed', [[recordData.id]]);
            } catch (e) {
                console.warn("No se pudo marcar data_barcode_printed:", e);
            }
        }

        await this._metodo_final_post_validacion(recordData, result);
        return result;
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
        const isBatchSale = isBatch && this.record && this.record.pick_type === "sale";
        const isBatchFull = isBatch && this.record && this.record.pick_type === "full";

        if (isBatchSale) {
            localStorage.setItem("mandatory_uncompleted",
                JSON.stringify({
                    screen: null,
                    component: "BarcodeScannerComponent",
                    component_props: {
                        context: "assign_pack_for_operator",
                        instructions: "Escanea la linea de empaque para asignar el Pack",
                        can_close: false,
                        before_mount: "check_pack_assigned",
                        extra_data: {
                            pick_id: record.id,
                            is_batch: isBatch,
                            operation_type: "Pack"
                        }
                    },
                    user: user
                })
            );
        } else if (isBatchFull) {
            localStorage.setItem("mandatory_uncompleted",
                JSON.stringify({
                    screen: null,
                    component: "QRScannerComponent",
                    component_props: {
                        context: "assign_bin_for_ful",
                        instructions: "Escanea el Bin para almacenar el pedido",
                        can_close: false,
                        before_mount: "check_bin_assigned",
                        extra_data: {
                            pick_id: record.id,
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
    
    async _processBarcode(barcode) {
        if (this.notificationCache) {
            this.notificationCache.clear();
        }
        const barcodeData = await this._parseBarcode(barcode, {});
        if (barcodeData.product && (this.resModel === 'stock.picking.batch' || this.resModel === 'stock.picking')) {
            // No permitir productos extra
            const existingLine = this._findLine(barcodeData);
            if (!existingLine) {
                return this.notification(
                    _t("El producto escaneado no pertenece a esta Orden/Plan de pickeo."),
                    { type: "danger", title: _t("Producto no permitido") }
                );
            }

            // No permitir cantidades extra
            const lines = this.currentState.lines.filter(l => {
                const lineProductId = (typeof l.product_id === 'object') ? l.product_id.id : l.product_id;
                return lineProductId === barcodeData.product.id;
            });

            if (lines.length > 0) {
                const allFull = lines.every(line => this._getQtyDone(line) >= this._getQtyDemand(line));
                if (allFull) {
                    return this.notification(
                        _t("Ya se ha completado la cantidad solicitada para el producto: %s.", barcodeData.product.display_name),
                        { type: "danger", title: _t("Cantidad Excedida") }
                    );
                }
            }
        }
        return await super._processBarcode(...arguments);
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
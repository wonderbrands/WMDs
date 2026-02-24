/** @odoo-module **/

import BarcodePickingModel from '@stock_barcode/models/barcode_picking_model';
import { patch } from '@web/core/utils/patch';
import { _t } from "@web/core/l10n/translation";
import { markup } from "@odoo/owl";

patch(BarcodePickingModel.prototype, {
    
    async _closeValidate(ev) {
        try {
            const backorders = await this.orm.searchRead(
                this.backorderModel,
                this.backordersDomain,
                ["display_name"]
            );

            if (backorders.length > 0) {
                const backorderNames = backorders.map(b => b.display_name).join(', ');
                console.log("WMDS Log: Backorders detectados:", backorderNames);

                const session_wmds = window.sessionStorage.getItem("wmds_logged_user");
                let user = "";
                if (session_wmds) {
                    try {
                        const json_session = JSON.parse(session_wmds);
                        user = json_session.email;
                    } catch (e) { console.error("Error parseando sesión", e); }
                }
                
                backorders.forEach(async bo => {
                    console.log("Backorder!!!!!")
                    console.log(bo);
                    try {
                        const response = await fetch('/wmds/v2/engine/post/log_stock_record', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                jsonrpc: "2.0",
                                params: {
                                    pick_id: bo.id,
                                    type: "backorder", 
                                    operator_mail: user,
                                }
                            })
                        });
    
                        const res = await response.json();
                        return res.result;
                    } catch (error) {
                        console.error("[Fetch Error]", error);
                        return { 'error': 'Error de red', 'message': error };
                    }
                }); 
            }
        } catch (error) {
            console.error("WMDS Error logging backorder:", error);
        }

        return super._closeValidate(ev);

    }
});
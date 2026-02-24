/** @odoo-module **/

import BarcodePickingModel from '@stock_barcode/models/barcode_picking_model';
import { patch } from '@web/core/utils/patch';


patch(BarcodePickingModel.prototype, {
    async _closeValidate(ev) {
        try {
            const backorders = await this.orm.searchRead(
                this.backorderModel,
                this.backordersDomain,
                ["display_name"]
            );

            if (backorders.length > 0) {
                const session_wmds = window.sessionStorage.getItem("wmds_logged_user");
                let user = "";
                if (session_wmds) {
                    try {
                        const json_session = JSON.parse(session_wmds);
                        user = json_session.email;
                    } catch (e) {}
                }

                for (const bo of backorders) {
                    await fetch('/wmds/v2/engine/post/log_stock_record', {
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
                }
            }
        } catch (error) {
            console.error(error);
        }

        const isWMDSUser = window.sessionStorage.getItem("wmds_logged_user");
        if (isWMDSUser) {
            return true; 
        }

        return super._closeValidate(ev);
    }
});
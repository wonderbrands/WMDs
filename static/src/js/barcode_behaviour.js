/** @odoo-module **/

import  BarcodeModel  from "@stock_barcode/models/barcode_model";
import { patch } from "@web/core/utils/patch";

patch(BarcodeModel.prototype, {

    async _validate() {
        console.log("[Custom] >> Inicio: Lógica ANTES de validar");

        const result = await super._validate(...arguments);

        console.log("[Custom] >> Fin: Lógica DESPUÉS de validar");
        
        await this._enviar_log(this.record);

        return result;
    },




    async _enviar_log(pick_info) {
        const session_wmds = window.sessionStorage.getItem("wmds_logged_user");
        let user = ""
        if (session_wmds){
            const json_session = JSON.parse(session_wmds)
            user = json_session.email
        } 

        try {
            const response = await fetch('/wmds/v2/engine/post/log_stock_record', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    params: {
                        pick_id: pick_info.id,
                        type: "external",
                        operator_mail: user,
                        message: ``,
                    }
                  })
            })   
            const result = await response.json()
            console.log(result)
            if (result.error) {
                console.log(result.error)
                return []
            }
            return result.result
        } catch (error) {
            return {
                'error': 'Error while doing request',
                'message': error
            }
        }
    }
});
/** @odoo-module */

import { Component, onMounted, xml, mount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";



class WMDSClientAction extends Component {
    static template = xml`
    <div id="wmds-app">
    </div>`;
    
    setup() {
        /*onMounted(() => {
        })*/
        onMounted(
            () => {   
                console.log(":D")               

        })
    }
}

// Register for backend (client action)
registry.category("actions").add(
    "WMDs.wmds_client",
    WMDSClientAction
);

// Mount for frontend (portal) when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPortal);
} else {
    initPortal();
}

function initPortal() {
    const root = document.getElementById('wmds-root');
    if (root && !root.hasAttribute('data-mounted')) {
        root.setAttribute('data-mounted', 'true');
        mount(WMDSClientAction, root);
    }
}
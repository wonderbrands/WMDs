<template>
    <div 
        class="barcode-operation-container"
        @touchstart="handleTouchStart"
        @touchmove="handleTouchMove"
        @touchend="handleTouchEnd"
    >
        <!-- Pull to refresh indicator -->
        <div v-if="pulling" class="pull-to-refresh-indicator" :style="{ height: pullDistance + 'px', opacity: pullDistance / 100 }">
            <i class="fa fa-refresh" :class="{ 'fa-spin': refreshing }"></i>
            <span>{{ refreshing ? 'Actualizando...' : 'Tire para actualizar' }}</span>
        </div>

        <!-- Header -->
        <div class="op-header">
            <div class="op-info">
                <span class="op-name">{{ operationData?.name || 'Cargando...' }}</span>
                <span class="op-type">{{ operationTypeTitle }}</span>
            </div>
            <div class="op-actions">
                <div class="picked-summary-badge">
                    <i class="fa fa-shopping-basket"></i>
                    <span>{{ totalPickedCount }} / {{ totalDemandCount }}</span>
                </div>
                <Button icon="fa fa-times" class="p-button-text p-button-danger p-button-sm" @click="exitFlow" />
            </div>
        </div>

        <!-- Main Scrollable Content -->
        <div class="main-content-scroll" ref="mainScroll">
            
            <!-- Scanner Area -->
            <div class="scanner-section">
                <div class="instruction-banner" :class="currentStep">
                    <i :class="stepIcon"></i>
                    <span>{{ stepInstruction }}</span>
                </div>

                <div class="scanner-box">
                    <BarcodeScannerComponent 
                        :key="scannerKey"
                        :onScan="handleScan"
                        :instructions="stepInstruction"
                    />
                </div>
                
                <!-- Quick Actions (Add/Subtract) -->
                <div class="quick-actions" v-if="currentLine">
                    <div class="line-summary">
                        <img :src="currentLine.image_url" class="line-img" />
                        <div class="line-details">
                            <span class="line-name">{{ currentLine.product_name }}</span>
                            <div class="flex gap-2 align-items-center">
                                <span class="line-progress">{{ currentLine.picked }} / {{ currentLine.qty_demand }}</span>
                                <small class="text-secondary" v-if="res_model === 'stock.picking.batch'">{{ currentLine.picking_name }}</small>
                            </div>
                            <small class="text-info font-bold">{{ currentLine.location_name }} → {{ currentLine.location_dest_name }}</small>
                        </div>
                    </div>
                    <div class="action-buttons">
                        <template v-if="localConfig.buttons_to_add">
                            <Button label="+1" class="p-button-success" @click="incrementPicked(1)" :disabled="isLineComplete && !localConfig.extra_products" />
                            <Button label="+5" class="p-button-success" @click="incrementPicked(5)" :disabled="isLineComplete && !localConfig.extra_products" />
                            <Button label="Todo" class="p-button-success" @click="incrementPicked(currentLine.qty_demand - currentLine.picked)" :disabled="isLineComplete" />
                        </template>
                        <template v-if="localConfig.buttons_to_subtract">
                            <Button label="-1" class="p-button-warning" @click="incrementPicked(-1)" :disabled="currentLine.picked <= 0" />
                        </template>
                    </div>

                    <!-- Manual Input Area -->
                    <div class="manual-input-area mt-3" v-if="localConfig.stock_input_add">
                        <div class="flex gap-2">
                            <InputNumber v-model="manualQty" :min="0" class="flex-1" placeholder="Cant. piezas" showButtons buttonLayout="horizontal" />
                            <Button label="ESTABLECER" icon="fa fa-check" class="p-button-primary" @click="incrementTo(manualQty)" :disabled="manualQty <= 0" />
                        </div>
                    </div>

                    <div class="action-buttons mt-3" v-if="localConfig.scan_dest && localConfig.backorder">
                        <Button label="ESTABLECER UBICACIÓN DESTINO" icon="fa fa-map-marker" class="p-button-info w-full" @click="currentStep = 'location_dest'" />
                    </div>
                </div>
            </div>

            <!-- Product List Area (Always present) -->
            <div class="list-section">
                <div class="list-header-sticky">
                    <i class="fa fa-list-ul"></i> Lista de Productos
                </div>
                <div v-for="(group, locationName) in groupedLines" :key="locationName" class="picking-group">
                    <div class="picking-header">
                        <i class="fa fa-map-marker"></i> {{ locationName }}
                    </div>
                    <DataTable :value="group" class="p-datatable-sm clickable-rows" @row-click="(event) => selectLine(event.data)">
                        <Column header="Producto">
                            <template #body="slotProps">
                                <div class="flex align-items-center gap-2 product-row-container" 
                                     :class="{'highlight-location': slotProps.data.location_name === scannedLocationSrc || slotProps.data.location_barcode === scannedLocationSrc, 'line-selected': currentLine?.id === slotProps.data.id}">
                                    <img :src="slotProps.data.image_url" style="width: 35px; border-radius: 4px;" />
                                    <div class="flex flex-column flex-1">
                                        <div class="flex justify-content-between align-items-start">
                                            <span class="font-bold text-xs">{{ slotProps.data.product_name }}</span>
                                            <span v-if="slotProps.data.location_name === scannedLocationSrc" class="location-badge-small">MISMA UBICACIÓN</span>
                                        </div>
                                        <div class="flex justify-content-between align-items-center mt-1">
                                            <small class="text-secondary" style="font-size: 0.7rem;">{{ slotProps.data.sku }}</small>
                                            <small class="text-info font-bold" style="font-size: 0.65rem;">{{ slotProps.data.picking_name }}</small>
                                        </div>
                                    </div>
                                </div>
                            </template>
                        </Column>
                        <Column header="Progreso" style="width: 80px">
                            <template #body="slotProps">
                                <span :class="{'text-success font-bold': slotProps.data.picked >= slotProps.data.qty_demand}" class="text-xs">
                                    {{ slotProps.data.picked }} / {{ slotProps.data.qty_demand }}
                                </span>
                            </template>
                        </Column>
                    </DataTable>
                </div>
            </div>
        </div>

        <!-- Footer / Validate -->
        <div class="op-footer">
            <div class="progress-overall">
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" :style="{ width: overallProgress + '%' }"></div>
                </div>
                <span>{{ Math.round(overallProgress) }}% completado</span>
            </div>
            <Button label="VALIDAR OPERACIÓN" icon="fa fa-check" class="p-button-success validate-btn" 
                @click="validateOperation" 
                :disabled="!canValidate"
                :loading="loading" />
        </div>

        <!-- Backorder Confirmation Dialog -->
        <Dialog v-model:visible="showBackorderDialog" header="Confirmar Entrega Parcial" modal :style="{ width: '90vw', maxWidth: '500px' }">
            <div class="p-3">
                <p class="mb-4">Se detectaron <b>{{ missingLines.length }}</b> productos incompletos. ¿Deseas validar la operación y crear un backorder?</p>
                
                <div class="missing-list mb-4">
                    <div v-for="line in missingLines" :key="line.id" class="flex justify-content-between align-items-center py-2 border-bottom-1 border-eee">
                        <span class="text-sm">{{ line.product_name }}</span>
                        <span class="text-danger font-bold text-sm">{{ line.picked }} / {{ line.qty_demand }}</span>
                    </div>
                </div>

                <div class="flex flex-column gap-3">
                    <Button label="SÍ, CREAR BACKORDER" icon="fa fa-check" class="p-button-success w-full" @click="processValidation" :loading="loading" />
                    <Button label="CANCELAR" icon="fa fa-times" class="p-button-text p-button-secondary w-full" @click="showBackorderDialog = false" />
                </div>
            </div>
        </Dialog>
    </div>
</template>

<script>
import BarcodeScannerComponent from '../QRScannerComponent/BarcodeScannerComponent.vue';
import Button from 'primevue/button';
import InputNumber from 'primevue/inputnumber';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Dialog from 'primevue/dialog';
import { useGeneralStore } from "../../store/index";

export default {
    name: "BarcodeOperationComponent",
    components: { BarcodeScannerComponent, Button, InputNumber, DataTable, Column, Dialog },
    props: {
        res_id: { required: true },
        res_model: { default: 'stock.picking' },
        config: {
            type: Object,
            default: () => ({
                buttons_to_add: true,
                buttons_to_subtract: true,
                stock_input_add: false,
                extra_products: false,
                backorder: true,
                scan_source: false,
                scan_dest: false
            })
        }
    },
    data() {
        return {
            store: useGeneralStore(),
            operationData: { lines: [] },
            currentStep: 'location_src', 
            currentLine: null,
            scannedLocationSrc: null,
            scannedLocationDest: null,
            scannerKey: 0,
            loading: false,
            localConfig: { ...this.config },
            showBackorderDialog: false,
            manualQty: 0,
            // Pull to refresh state
            startY: 0,
            pullDistance: 0,
            pulling: false,
            refreshing: false,
            maxPullDistance: 100
        }
    },
    computed: {
        operationTypeTitle() {
            if (this.operationData.is_pful) return 'Resurtido Full (Pick)';
            if (this.operationData.is_dful) return 'Resurtido Full (Despacho)';
            
            if (this.res_model === 'stock.picking.batch') {
                const subType = this.operationData.pick_type === 'sale' ? ' - Pedidos' : (this.operationData.pick_type === 'full' ? ' - Full' : '');
                return 'Plan de Pickeo' + subType;
            }
            return 'Operación de Almacén';
        },
        stepInstruction() {
            if (this.currentStep === 'location_src') return 'Escanea UBICACIÓN ORIGEN';
            if (this.currentStep === 'product') return 'Escanea PRODUCTO';
            if (this.currentStep === 'location_dest') return 'Escanea UBICACIÓN DESTINO';
            return '';
        },
        stepIcon() {
            if (this.currentStep.includes('location')) return 'fa fa-map-marker';
            return 'fa fa-barcode';
        },
        isLineComplete() {
            return this.currentLine && this.currentLine.picked >= this.currentLine.qty_demand;
        },
        totalPickedCount() {
            return (this.operationData.lines || []).reduce((acc, l) => acc + l.picked, 0);
        },
        totalDemandCount() {
            return (this.operationData.lines || []).reduce((acc, l) => acc + l.qty_demand, 0);
        },
        overallProgress() {
            if (!this.totalDemandCount) return 0;
            return (this.totalPickedCount / this.totalDemandCount) * 100;
        },
        canValidate() {
            return (this.operationData.lines || []).some(l => l.picked > 0);
        },
        missingLines() {
            return (this.operationData.lines || []).filter(l => l.picked < l.qty_demand);
        },
        groupedLines() {
            const groups = {};
            // Sort lines by location name first to ensure alphabetical order of groups
            const sortedLines = [...(this.operationData.lines || [])].sort((a, b) => {
                const locA = a.location_name || '';
                const locB = b.location_name || '';
                return locA.localeCompare(locB);
            });

            sortedLines.forEach(line => {
                const groupKey = line.location_name || 'Sin ubicación';
                if (!groups[groupKey]) groups[groupKey] = [];
                groups[groupKey].push(line);
            });
            return groups;
        }
    },
    async mounted() {
        await this.loadData();
    },
    methods: {
        async loadData(silent = false) {
            if (!silent) this.loading = true;
            try {
                const res = await this.store.callOdoo("get_operation_data", "", {
                    res_id: this.res_id,
                    res_model: this.res_model,
                    operator_email: this.store.role.email
                });
                if (res.status === 'ok') {
                    const currentLineId = this.currentLine?.id;
                    this.operationData = res;
                    
                    if (currentLineId) {
                        this.currentLine = this.operationData.lines.find(l => l.id === currentLineId) || null;
                    } else if (this.operationData.lines.length > 0) {
                        // Set first incomplete line as current if none selected
                        this.currentLine = this.operationData.lines.find(l => l.picked < l.qty_demand) || this.operationData.lines[0];
                    }

                    if (res.is_dful) {
                        this.localConfig.scan_source = false;
                        this.localConfig.scan_dest = false;
                        this.localConfig.backorder = true;
                    }
                    if (res.is_pful) {
                        this.localConfig.scan_dest = false; 
                        this.localConfig.backorder = true;
                    }

                    if (this.res_model === 'stock.picking.batch') {
                        if (res.pick_type === 'sale') {
                            this.localConfig.backorder = false;
                            this.localConfig.buttons_to_add = false;
                        } else if (res.pick_type === 'full') {
                            this.localConfig.backorder = true;
                            this.localConfig.buttons_to_add = true;
                        }
                    }

                    if (!silent) this.checkInitialStep();
                } else {
                    this.$toast.add({ severity: 'error', summary: 'Error', detail: res.message, life: 5000 });
                    if (res.message.includes('cancelada') || res.message.includes('reasignada')) {
                        this.exitFlow();
                    }
                }
            } finally {
                if (!silent) this.loading = false;
            }
        },
        checkInitialStep() {
            if (this.localConfig.scan_source) {
                this.currentStep = 'location_src';
            } else {
                this.currentStep = 'product';
            }
        },
        async handleScan(barcode) {
            if (this.currentStep === 'location_src') {
                if (!this.localConfig.any_source && this.currentLine) {
                    const isValid = this.currentLine.location_name === barcode || this.currentLine.location_barcode === barcode || this.currentLine.location_id.toString() === barcode;
                    if (!isValid) {
                        this.$toast.add({ severity: 'error', summary: 'Ubicación Incorrecta', detail: `Debe escanear la ubicación reservada: ${this.currentLine.location_name}`, life: 3000 });
                        return;
                    }
                }
                this.scannedLocationSrc = barcode;
                this.currentStep = 'product';
                this.$toast.add({ severity: 'info', summary: 'Ubicación Origen', detail: barcode, life: 2000 });
            } else if (this.currentStep === 'product') {
                await this.processProductScan(barcode);
            } else if (this.currentStep === 'location_dest') {
                if (!this.currentLine) return;
                
                if (this.localConfig.any_dest) {
                    this.loading = true;
                    try {
                        const res = await this.store.callOdoo("process_dest_location_scan", "", {
                            line_id: this.currentLine.id,
                            barcode: barcode,
                            operator_email: this.store.role.email
                        });

                        if (res.status === 'ok') {
                            this.scannedLocationDest = barcode;
                            this.currentLine.location_dest_name = res.new_location_name;
                            this.currentLine.location_dest_id = res.new_location_id;

                            if (this.localConfig.scan_source) {
                                this.currentStep = 'location_src';
                            } else {
                                this.currentStep = 'product';
                            }
                            this.$toast.add({ severity: 'info', summary: 'Ubicación Destino', detail: res.new_location_name, life: 2000 });
                        } else {
                            this.$toast.add({ severity: 'error', summary: 'Ubicación Destino Inválida', detail: res.message, life: 4000 });
                        }
                    } finally {
                        this.loading = false;
                    }
                } else {
                    const isValid = this.currentLine.location_dest_name === barcode || this.currentLine.location_dest_barcode === barcode || this.currentLine.location_dest_id.toString() === barcode;
                    if (isValid) {
                        this.scannedLocationDest = barcode;
                        if (this.localConfig.scan_source) {
                            this.currentStep = 'location_src';
                        } else {
                            this.currentStep = 'product';
                        }
                        this.$toast.add({ severity: 'info', summary: 'Ubicación Destino', detail: barcode, life: 2000 });
                    } else {
                        this.$toast.add({ severity: 'error', summary: 'Ubicación Destino Incorrecta', detail: `Debe ser el destino asignado: ${this.currentLine.location_dest_name}`, life: 3000 });
                    }
                }
            }
            this.scannerKey++;
            await this.loadData(true);
            
            // After data is refreshed, check if current line is complete and auto-advance
            this.checkAndAutoAdvance();
        },
        async processProductScan(barcode) {
            this.loading = true;
            try {
                const res = await this.store.callOdoo("process_scan", "", {
                    res_id: this.res_id,
                    res_model: this.res_model,
                    operator_email: this.store.role.email,
                    barcode: barcode,
                    location_barcode: this.scannedLocationSrc,
                    extra_products: this.localConfig.extra_products
                });

                if (res.status === 'ok') {
                    const line = this.operationData.lines.find(l => l.id === res.line_id);
                    if (line) {
                        line.picked = res.new_picked;
                        this.currentLine = line;
                        
                        if (this.isLineComplete && !this.localConfig.extra_products) {
                            this.$toast.add({ severity: 'success', summary: 'Completado', detail: line.product_name, life: 2000 });
                        }
                    }
                } else {
                    this.$toast.add({ severity: 'error', summary: 'Atención', detail: res.message, life: 4000 });
                    if (res.message.includes('reasignada') || res.message.includes('cancelada')) {
                        this.exitFlow();
                    }
                }
            } finally {
                this.loading = false;
            }
        },
        async incrementPicked(amt) {
            if (!this.currentLine) return;
            
            if (amt > 0 && !this.localConfig.extra_products && (this.currentLine.picked + amt > this.currentLine.qty_demand)) {
                this.$toast.add({ severity: 'error', summary: 'Límite alcanzado', detail: 'has recogido la cantidad necesaria del SKU para este pedido', life: 3000 });
                return;
            }

            this.loading = true;
            try {
                const res = await this.store.callOdoo("process_scan", "", {
                    res_id: this.res_id,
                    res_model: this.res_model,
                    operator_email: this.store.role.email,
                    line_id: this.currentLine.id,
                    increment: amt,
                    extra_products: this.localConfig.extra_products
                });

                if (res.status === 'ok') {
                    this.currentLine.picked = res.new_picked;
                    await this.loadData(true);
                    this.checkAndAutoAdvance();
                } else {
                    this.$toast.add({ severity: 'error', summary: 'Atención', detail: res.message, life: 4000 });
                    if (res.message.includes('reasignada') || res.message.includes('cancelada')) {
                        this.exitFlow();
                    }
                }
            } finally {
                this.loading = false;
            }
        },
        async incrementTo(targetQty) {
            if (!this.currentLine) return;
            
            // Calculate increment needed to reach targetQty
            const amt = targetQty - this.currentLine.picked;
            if (amt === 0) return;

            if (amt > 0 && !this.localConfig.extra_products && (this.currentLine.picked + amt > this.currentLine.qty_demand)) {
                this.$toast.add({ severity: 'error', summary: 'Límite alcanzado', detail: 'has recogido la cantidad necesaria del SKU para este pedido', life: 3000 });
                return;
            }

            this.loading = true;
            try {
                const res = await this.store.callOdoo("process_scan", "", {
                    res_id: this.res_id,
                    res_model: this.res_model,
                    operator_email: this.store.role.email,
                    line_id: this.currentLine.id,
                    increment: amt,
                    extra_products: this.localConfig.extra_products
                });

                if (res.status === 'ok') {
                    this.currentLine.picked = res.new_picked;
                    this.manualQty = 0; // Reset after success
                    await this.loadData(true);
                    this.checkAndAutoAdvance();
                } else {
                    this.$toast.add({ severity: 'error', summary: 'Atención', detail: res.message, life: 4000 });
                    if (res.message.includes('reasignada') || res.message.includes('cancelada')) {
                        this.exitFlow();
                    }
                }
            } finally {
                this.loading = false;
            }
        },
        checkAndAutoAdvance() {
            // If current line is finished, find the next one automatically
            if (this.currentLine && this.currentLine.picked >= this.currentLine.qty_demand) {
                const lines = this.operationData.lines || [];
                
                // Priority 1: Next incomplete line in SAME location
                let nextLine = lines.find(l => 
                    l.picked < l.qty_demand && 
                    (l.location_name === this.scannedLocationSrc || l.location_barcode === this.scannedLocationSrc)
                );

                // Priority 2: Next incomplete line anywhere
                if (!nextLine) {
                    nextLine = lines.find(l => l.picked < l.qty_demand);
                }

                if (nextLine && nextLine.id !== this.currentLine.id) {
                    this.selectLine(nextLine);
                    this.$toast.add({ severity: 'info', summary: 'Siguiente producto', detail: nextLine.product_name, life: 2000 });
                }
            }
        },
        async validateOperation() {
            console.log("Action: validateOperation triggered");
            const incomplete = this.missingLines.length > 0;

            if (incomplete) {
                if (!this.localConfig.backorder) {
                    this.$toast.add({ 
                        severity: 'error', 
                        summary: 'Operación Incompleta', 
                        detail: 'Esta operación no permite entregas parciales.', 
                        life: 5000 
                    });
                    return;
                }
                this.showBackorderDialog = true;
            } else {
                await this.processValidation();
            }
        },
        async processValidation() {
            this.loading = true;
            this.showBackorderDialog = false;
            try {
                const res = await this.store.callOdoo("validate_operation", "", {
                    res_id: this.res_id,
                    res_model: this.res_model,
                    operator_email: this.store.role.email
                });

                if (res && res.status === 'ok') {
                    this.$toast.add({ severity: 'success', summary: 'Éxito', detail: 'Operación validada correctamente.', life: 3000 });
                    
                    const confirmedResModel = res.res_model;
                    const confirmedPickType = res.pick_type;
                    const isBatch = confirmedResModel === 'stock.picking.batch';
                    const isPFUL = res.is_pful;

                    if (isBatch && confirmedPickType === "sale") {
                        this.store.mandatory_uncompleted.screen = null;
                        this.store.mandatory_uncompleted.component = "BarcodeScannerComponent";
                        this.store.mandatory_uncompleted.component_props = {
                            context: "assign_pack_for_operator",
                            instructions: "Escanea la línea de empaque para asignar el Pack",
                            can_close: false,
                            before_mount: "check_pack_assigned",
                            extra_data: {
                                pick_id: this.res_id,
                                is_batch: true,
                                operation_type: "Pack"
                            }
                        };
                        this.store.mandatory_uncompleted.user = this.store.role.email;
                        this.store.mandatory_uncompleted.loadToStorage();
                    } else if (isPFUL || (isBatch && (confirmedPickType === "full" || confirmedPickType === "wholesale"))) {
                        this.store.mandatory_uncompleted.screen = null;
                        this.store.mandatory_uncompleted.component = "BarcodeScannerComponent";
                        this.store.mandatory_uncompleted.component_props = {
                            context: "assign_bin_for_ful",
                            instructions: "Escanea el BIN para trasladar el lote",
                            can_close: false,
                            before_mount: "check_bin_assigned",
                            extra_data: {
                                pick_id: this.res_id,
                                is_batch: isBatch,
                                operation_type: "Bin"
                            }
                        };
                        this.store.mandatory_uncompleted.user = this.store.role.email;
                        this.store.mandatory_uncompleted.loadToStorage();
                    } else {
                        if (this.localConfig.post_validate) {
                            await this.store.executeActionByContext(this.localConfig.post_validate, null, {
                                res_id: this.res_id,
                                res_model: this.res_model,
                                ...this.localConfig.extra_data
                            });
                        }
                        this.exitFlow();
                    }
                } else {
                    const errorMsg = res?.message || 'Error desconocido durante la validación.';
                    this.$toast.add({ severity: 'error', summary: 'Error de Validación', detail: errorMsg, life: 5000 });
                }
            } catch (e) {
                console.error("Validation crash:", e);
                this.$toast.add({ severity: 'error', summary: 'Error Crítico', detail: 'No se pudo procesar la validación. Verifique logs.', life: 5000 });
            } finally {
                this.loading = false;
            }
        },
        selectLine(line) {
            this.currentLine = line;
            this.manualQty = 0;
            const isComplete = line.picked >= line.qty_demand;
            const allowPartial = this.localConfig.backorder;
            
            if ((isComplete || allowPartial) && this.localConfig.scan_dest) {
                this.currentStep = 'location_dest';
            } else if (this.localConfig.scan_source) {
                this.currentStep = 'location_src';
            } else {
                this.currentStep = 'product';
            }

            if (this.$refs.mainScroll) {
                this.$refs.mainScroll.scrollTo({ top: 0, behavior: 'smooth' });
            }
        },
        exitFlow() {
            this.store.mandatory_uncompleted.doneMandatory();
        },
        // Pull to refresh handlers
        handleTouchStart(e) {
            if (this.$el.scrollTop === 0) {
                this.startY = e.touches[0].pageY;
                this.pulling = true;
            }
        },
        handleTouchMove(e) {
            if (!this.pulling || this.refreshing) return;
            const currentY = e.touches[0].pageY;
            const diff = currentY - this.startY;
            if (diff > 0) {
                this.pullDistance = Math.min(diff, this.maxPullDistance);
                if (diff > 10) e.preventDefault(); 
            }
        },
        async handleTouchEnd() {
            if (!this.pulling) return;
            if (this.pullDistance >= 60) {
                this.refreshing = true;
                await this.loadData();
                this.refreshing = false;
            }
            this.pulling = false;
            this.pullDistance = 0;
        }
    }
}
</script>

<style scoped>
.barcode-operation-container {
    overflow-y: auto; 
    width: 100%; 
    height: 100vh; 
    display: flex; 
    flex-direction: column;
    position: relative;
    overscroll-behavior-y: contain;
    background: #f8f9fa;
    padding-bottom: 15rem;
}

.pull-to-refresh-indicator {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    background: rgba(59, 130, 246, 0.1);
    color: #3B82F6;
    z-index: 1000;
    transition: height 0.1s ease;
    font-size: 0.8rem;
    font-weight: bold;
    gap: 5px;
}

.pull-to-refresh-indicator i {
    font-size: 1.2rem;
}

.op-header {
    background: #fff;
    padding: 0.75rem 1rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #dee2e6;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    flex-shrink: 0;
}

.op-info { display: flex; flex-direction: column; }
.op-name { font-weight: 800; font-size: 1rem; }
.op-type { font-size: 0.7rem; color: #6c757d; }
.op-actions { display: flex; align-items: center; gap: 10px; }

.picked-summary-badge {
    background: #111827;
    color: #facc15;
    padding: 4px 12px;
    border-radius: 20px;
    font-weight: 800;
    font-size: 0.9rem;
    display: flex;
    align-items: center;
    gap: 6px;
}

.main-content-scroll {
    padding: 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    flex-shrink: 0;
}

.scanner-section { display: flex; flex-direction: column; gap: 0.75rem; }
.scanner-box { height: 200px; border-radius: 8px; overflow: hidden; }

.instruction-banner {
    padding: 0.75rem;
    border-radius: 8px;
    text-align: center;
    font-weight: bold;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    font-size: 0.9rem;
}

.instruction-banner.location_src { background: #e3f2fd; color: #0d47a1; }
.instruction-banner.product { background: #e8f5e9; color: #1b5e20; }
.instruction-banner.location_dest { background: #fff3e0; color: #e65100; }

.quick-actions {
    background: #fff;
    padding: 0.75rem;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.line-summary { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem; }
.line-img { width: 50px; height: 50px; border-radius: 8px; object-fit: cover; }
.line-details { display: flex; flex-direction: column; }
.line-name { font-weight: bold; font-size: 0.8rem; line-height: 1.2; }
.line-progress { font-size: 1.1rem; font-weight: 800; color: #2ecc71; }

.action-buttons { display: flex; gap: 8px; }
.action-buttons button { flex: 1; height: 40px; font-weight: bold; font-size: 0.8rem; }

.list-section { background: #fff; border-radius: 8px; overflow: hidden; border: 1px solid #eee; }
.list-header-sticky { padding: 0.75rem; background: #f1f5f9; font-weight: 800; font-size: 0.85rem; color: #475569; border-bottom: 1px solid #e2e8f0; }
.picking-group { margin-bottom: 1rem; }
.picking-header { background: #f8fafc; padding: 0.4rem 0.75rem; font-weight: bold; color: #64748b; border-bottom: 1px solid #f1f5f9; font-size: 0.75rem; }

/* Highlight Logic */
.product-row-container {
    padding: 8px;
    border-radius: 6px;
    transition: all 0.2s ease;
    border: 2px solid transparent;
}

.highlight-location {
    background: #eff6ff;
    border-color: #3b82f6;
}

.line-selected {
    background: #f0fdf4;
    border-left: 4px solid #22c55e;
}

.location-badge-small {
    background: #3b82f6;
    color: white;
    font-size: 0.55rem;
    padding: 2px 6px;
    border-radius: 10px;
    font-weight: 900;
}

.op-footer {
    background: #fff;
    padding: 0.75rem 1rem;
    border-top: 1px solid #dee2e6;
    flex-shrink: 0;
}

.progress-overall {
    margin-bottom: 0.75rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    font-size: 0.75rem;
    font-weight: bold;
}

.progress-bar-bg { width: 100%; height: 6px; background: #e9ecef; border-radius: 3px; overflow: hidden; }
.progress-bar-fill { height: 100%; background: #2ecc71; transition: width 0.3s ease; }
.validate-btn { width: 100%; height: 50px; font-size: 1rem; font-weight: 800; }

:deep(.clickable-rows .p-datatable-tbody > tr) { cursor: pointer; }
:deep(.p-datatable .p-datatable-tbody > tr > td) { padding: 0.2rem 0.5rem; }

</style>
<template>
    <Dialog 
        v-model:visible="visibleModel" 
        modal 
        :header="dialogTitle" 
        :style="{ width: '92vw', maxWidth: '640px' }"
        :dismissableMask="true"
        class="universal-lookup-dialog"
        @show="onDialogShow"
        @hide="onHide"
    >
        <template #header>
            <div class="modal-header-custom">
                <i :class="['header-icon', headerIcon]"></i>
                <div class="header-texts">
                    <span class="header-type-badge">{{ entityTypeLabel }}</span>
                    <h3 class="header-main-title">{{ entityTitle }}</h3>
                </div>
            </div>
        </template>

        <div v-if="loading" class="loading-state">
            <i class="fa fa-spinner fa-spin fa-2x"></i>
            <span>Consultando datos...</span>
        </div>

        <div v-else-if="result" class="modal-body-scrollable" @scroll="handleScroll">
            <!-- ============================================== -->
            <!-- CASO 1: UBICACIÓN                             -->
            <!-- ============================================== -->
            <div v-if="result.type === 'location'" class="location-view">
                <!-- Status Chips Grid -->
                <div class="status-grid">
                    <div :class="['status-card', result.data.empty_status.is_empty ? 'card-warning' : 'card-success']">
                        <i :class="['fa', result.data.empty_status.is_empty ? 'fa-inbox' : 'fa-cubes']"></i>
                        <div>
                            <span class="status-card-label">{{ result.data.empty_status.is_empty ? 'Ubicación Vacía' : 'Stock Total' }}</span>
                            <span class="status-card-val">
                                {{ result.data.empty_status.is_empty ? (result.data.empty_status.empty_duration || 'Sin stock') : (result.data.stock_summary.total_units + ' uds') }}
                            </span>
                        </div>
                    </div>

                    <div :class="['status-card', result.data.blocking.is_blocked ? 'card-danger' : 'card-neutral']">
                        <i :class="['fa', result.data.blocking.is_blocked ? 'fa-lock' : 'fa-unlock']"></i>
                        <div>
                            <span class="status-card-label">Bloqueo</span>
                            <span class="status-card-val">
                                {{ result.data.blocking.is_blocked ? (result.data.blocking.block_reason_type || 'Bloqueada') : 'Libre' }}
                            </span>
                        </div>
                    </div>

                    <div :class="['status-card', result.data.cycle_count.in_cycle_count ? 'card-info' : 'card-neutral']">
                        <i class="fa fa-repeat"></i>
                        <div>
                            <span class="status-card-label">Conteo Cíclico</span>
                            <span class="status-card-val">
                                {{ result.data.cycle_count.in_cycle_count ? 'En conteo' : 'Al día' }}
                            </span>
                        </div>
                    </div>

                    <div :class="['status-card', result.data.reservations.has_pending_reservations ? 'card-purple' : 'card-neutral']">
                        <i class="fa fa-clock-o"></i>
                        <div>
                            <span class="status-card-label">Reservas</span>
                            <span class="status-card-val">
                                {{ result.data.reservations.reservations_count }} pendientes
                            </span>
                        </div>
                    </div>
                </div>

                <!-- Lista de Productos en la Ubicación (Lazy 5 en 5) -->
                <div class="section-title">
                    <span>Productos en ubicación ({{ result.data.stock_summary.items.length }})</span>
                    <small class="lazy-counter">Mostrando {{ visibleLocationItems.length }} de {{ result.data.stock_summary.items.length }}</small>
                </div>

                <div v-if="result.data.stock_summary.items.length === 0" class="empty-list-msg">
                    <i class="fa fa-inbox fa-2x"></i>
                    <span>No hay stock registrado en esta ubicación</span>
                </div>

                <div v-else class="items-list">
                    <div 
                        v-for="item in visibleLocationItems" 
                        :key="item.quant_id"
                        class="item-card"
                    >
                        <div class="item-img-wrapper">
                            <img 
                                :src="item.image_url" 
                                :alt="item.product_name"
                                class="item-thumb"
                                @error="handleImageError"
                            />
                        </div>
                        <div class="item-info">
                            <h4 class="item-name">{{ item.product_name }}</h4>
                            <div class="item-tags">
                                <span class="tag-sku"><i class="fa fa-tag"></i> {{ item.default_code || 'S/SKU' }}</span>
                                <span class="tag-barcode" v-if="item.barcode"><i class="fa fa-barcode"></i> {{ item.barcode }}</span>
                                <span class="tag-lot" v-if="item.lot_name && item.lot_name !== 'Sin lote'"><i class="fa fa-hashtag"></i> {{ item.lot_name }}</span>
                            </div>
                        </div>
                        <div class="item-qty-box">
                            <span class="qty-avail">{{ item.available_quantity }}</span>
                            <span class="qty-uom">{{ item.uom || 'uds' }} disp.</span>
                            <span class="qty-total" v-if="item.reserved_quantity > 0">({{ item.quantity }} en mano / {{ item.reserved_quantity }} res.)</span>
                        </div>
                    </div>

                    <!-- Botón cargar más si hay más de 5 -->
                    <div v-if="hasMoreLocationItems" class="load-more-section">
                        <Button 
                            label="Ver más..." 
                            icon="fa fa-arrow-down" 
                            class="p-button-outlined p-button-sm w-full btn-load-more"
                            @click="loadMore"
                        />
                    </div>
                </div>
            </div>

            <!-- ============================================== -->
            <!-- CASO 2: PRODUCTO                              -->
            <!-- ============================================== -->
            <div v-else-if="result.type === 'product'" class="product-view">
                <!-- Product Card Principal -->
                <div class="product-header-card">
                    <div class="product-photo-box">
                        <img 
                            :src="result.data.product.image_url" 
                            :alt="result.data.product.name" 
                            class="product-large-img"
                            @error="handleImageError"
                        />
                    </div>
                    <div class="product-core-data">
                        <h3 class="product-name">{{ result.data.product.name }}</h3>
                        <div class="product-code-row">
                            <span class="badge-sku"><i class="fa fa-tag mr-1"></i> SKU: {{ result.data.product.default_code || 'N/A' }}</span>
                            <span class="badge-barcode" v-if="result.data.product.barcode"><i class="fa fa-barcode mr-1"></i> {{ result.data.product.barcode }}</span>
                        </div>
                        <div class="product-stock-totals">
                            <div class="stock-pill avail">
                                <span class="label">Disponible</span>
                                <span class="num">{{ result.data.stock_summary.total_available }}</span>
                            </div>
                            <div class="stock-pill total">
                                <span class="label">A la mano</span>
                                <span class="num">{{ result.data.stock_summary.total_quantity }}</span>
                            </div>
                            <div class="stock-pill reserved">
                                <span class="label">Reservado</span>
                                <span class="num">{{ result.data.stock_summary.total_reserved }}</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Dimensiones y Peso -->
                <div class="dimensions-card">
                    <span class="dim-title"><i class="fa fa-arrows-alt mr-1"></i> Dimensiones de Empaque</span>
                    <div class="dim-grid">
                        <div class="dim-item">
                            <span class="dim-lbl">Largo</span>
                            <span class="dim-val">{{ result.data.product.dimensions.length }} cm</span>
                        </div>
                        <div class="dim-item">
                            <span class="dim-lbl">Ancho</span>
                            <span class="dim-val">{{ result.data.product.dimensions.width }} cm</span>
                        </div>
                        <div class="dim-item">
                            <span class="dim-lbl">Alto</span>
                            <span class="dim-val">{{ result.data.product.dimensions.height }} cm</span>
                        </div>
                        <div class="dim-item">
                            <span class="dim-lbl">Peso</span>
                            <span class="dim-val">{{ result.data.product.dimensions.weight }} kg</span>
                        </div>
                        <div class="dim-item" v-if="result.data.product.dimensions.volume > 0">
                            <span class="dim-lbl">Volumen</span>
                            <span class="dim-val">{{ result.data.product.dimensions.volume }} m³</span>
                        </div>
                    </div>
                </div>

                <!-- Ubicaciones Disponibles (Lazy 5 en 5) -->
                <div class="section-title">
                    <span>Disponible en {{ result.data.stock_summary.locations_count }} ubicaciones</span>
                    <small class="lazy-counter">Mostrando {{ visibleProductLocations.length }} de {{ result.data.stock_summary.locations_count }}</small>
                </div>

                <div v-if="result.data.stock_summary.locations.length === 0" class="empty-list-msg">
                    <i class="fa fa-map-marker fa-2x"></i>
                    <span>No hay stock disponible en ubicaciones internas</span>
                </div>

                <div v-else class="locations-list">
                    <div 
                        v-for="loc in visibleProductLocations" 
                        :key="loc.quant_id"
                        class="location-row-card"
                    >
                        <div class="loc-marker">
                            <i class="fa fa-map-marker"></i>
                        </div>
                        <div class="loc-details">
                            <span class="loc-name">{{ loc.location_name }}</span>
                            <span class="loc-sub" v-if="loc.barcode"><i class="fa fa-barcode"></i> {{ loc.barcode }}</span>
                            <span class="loc-lot" v-if="loc.lot_name"><i class="fa fa-hashtag"></i> {{ loc.lot_name }}</span>
                        </div>
                        <div class="loc-stock-box">
                            <span class="loc-avail">{{ loc.available_quantity }}</span>
                            <span class="loc-uom">disp.</span>
                            <small class="loc-breakdown" v-if="loc.reserved_quantity > 0">
                                ({{ loc.quantity }} total / {{ loc.reserved_quantity }} res.)
                            </small>
                        </div>
                    </div>

                    <div v-if="hasMoreProductLocations" class="load-more-section">
                        <Button 
                            label="Ver más..." 
                            icon="fa fa-arrow-down" 
                            class="p-button-outlined p-button-sm w-full btn-load-more"
                            @click="loadMore"
                        />
                    </div>
                </div>
            </div>

            <!-- ============================================== -->
            <!-- CASO 3: BIN O DOCK                            -->
            <!-- ============================================== -->
            <div v-else-if="result.type === 'bin' || result.type === 'dock'" class="container-view">
                <!-- Meta Info -->
                <div class="container-meta-card">
                    <div class="meta-row">
                        <div class="meta-name-box">
                            <span class="meta-type">{{ result.type.toUpperCase() }}</span>
                            <h2 class="meta-title">{{ result.data.name }}</h2>
                        </div>
                        <span :class="['state-badge', result.data.state === 'available' ? 'badge-ok' : 'badge-blocked']">
                            {{ result.data.state_label }}
                        </span>
                    </div>

                    <div class="meta-extra" v-if="result.data.carrier || result.data.origin_doc">
                        <span v-if="result.data.carrier" class="extra-item"><i class="fa fa-truck mr-1"></i> {{ result.data.carrier }}</span>
                        <span v-if="result.data.origin_doc" class="extra-item"><i class="fa fa-lock mr-1"></i> {{ result.data.origin_doc }}</span>
                    </div>
                </div>

                <!-- Selector de Pestaña EIs vs Moves -->
                <div class="tab-switcher">
                    <button 
                        :class="['switch-btn', activeContainerTab === 'packages' ? 'active' : '']"
                        @click="activeContainerTab = 'packages'"
                    >
                        <i class="fa fa-archive mr-1"></i> Paquetes / Guías ({{ result.data.packages_count }})
                    </button>
                    <button 
                        :class="['switch-btn', activeContainerTab === 'moves' ? 'active' : '']"
                        @click="activeContainerTab = 'moves'"
                    >
                        <i class="fa fa-cubes mr-1"></i> Productos Fulfillment ({{ result.data.moves_count }})
                    </button>
                </div>

                <!-- Lista de Paquetes (Lazy 5 en 5) -->
                <div v-if="activeContainerTab === 'packages'">
                    <div v-if="result.data.packages.length === 0" class="empty-list-msg">
                        <i class="fa fa-box-open fa-2x"></i>
                        <span>No hay paquetes registrados en este {{ result.type.toUpperCase() }}</span>
                    </div>
                    <div v-else class="packages-list">
                        <div 
                            v-for="pkg in visiblePackages" 
                            :key="pkg.id"
                            class="package-card"
                        >
                            <div class="pkg-icon"><i class="fa fa-file-text-o"></i></div>
                            <div class="pkg-info">
                                <span class="pkg-name">{{ pkg.name }}</span>
                                <span class="pkg-so" v-if="pkg.so_name"><i class="fa fa-shopping-cart"></i> {{ pkg.so_name }}</span>
                            </div>
                            <span class="pkg-status">{{ pkg.status }}</span>
                        </div>

                        <div v-if="hasMorePackages" class="load-more-section">
                            <Button 
                                label="Ver más..." 
                                icon="fa fa-arrow-down" 
                                class="p-button-outlined p-button-sm w-full btn-load-more"
                                @click="loadMore"
                            />
                        </div>
                    </div>
                </div>

                <!-- Lista de Moves / Productos (Lazy 5 en 5) -->
                <div v-if="activeContainerTab === 'moves'">
                    <div v-if="result.data.moves.length === 0" class="empty-list-msg">
                        <i class="fa fa-cubes fa-2x"></i>
                        <span>No hay productos de fulfillment en este {{ result.type.toUpperCase() }}</span>
                    </div>
                    <div v-else class="moves-list">
                        <div 
                            v-for="m in visibleMoves" 
                            :key="m.id"
                            class="move-card"
                        >
                            <img 
                                :src="m.image_url" 
                                :alt="m.product_name"
                                class="move-thumb"
                                @error="handleImageError"
                            />
                            <div class="move-info">
                                <span class="move-name">{{ m.product_name }}</span>
                                <span class="move-sub"><i class="fa fa-tag"></i> {{ m.default_code || 'S/SKU' }} | {{ m.picking_name }}</span>
                            </div>
                            <div class="move-qty">
                                <span class="qty-done">{{ m.done_qty }}</span>
                                <span class="qty-demand">/ {{ m.demand_qty }}</span>
                            </div>
                        </div>

                        <div v-if="hasMoreMoves" class="load-more-section">
                            <Button 
                                label="Ver más..." 
                                icon="fa fa-arrow-down" 
                                class="p-button-outlined p-button-sm w-full btn-load-more"
                                @click="loadMore"
                            />
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <template #footer>
            <div class="modal-footer-custom">
                <Button 
                    label="Cerrar (Esc)" 
                    icon="fa fa-times" 
                    class="p-button-secondary p-button-sm w-full" 
                    @click="closeDialog"
                />
            </div>
        </template>
    </Dialog>
</template>

<script>
import Dialog from 'primevue/dialog';
import Button from 'primevue/button';

export default {
    name: "UniversalLookupModal",
    components: { Dialog, Button },
    props: {
        visible: {
            type: Boolean,
            default: false
        },
        result: {
            type: Object,
            default: null
        },
        loading: {
            type: Boolean,
            default: false
        }
    },
    emits: ["update:visible", "closed"],
    data() {
        return {
            lazyLimit: 5,
            activeContainerTab: 'packages'
        };
    },
    computed: {
        visibleModel: {
            get() {
                return this.visible;
            },
            set(val) {
                this.$emit("update:visible", val);
            }
        },
        dialogTitle() {
            if (!this.result) return "Consulta Rápida";
            const map = {
                location: "Información de Ubicación",
                product: "Ficha del Producto",
                bin: "Detalle de BIN",
                dock: "Detalle de DOCK"
            };
            return map[this.result.type] || "Consulta Rápida";
        },
        entityTypeLabel() {
            if (!this.result) return "";
            const map = {
                location: "UBICACIÓN",
                product: "PRODUCTO",
                bin: "BIN STORAGE",
                dock: "DOCK STORAGE"
            };
            return map[this.result.type] || "";
        },
        entityTitle() {
            if (!this.result || !this.result.data) return "";
            if (this.result.type === 'location') return this.result.data.location?.complete_name || this.result.data.location?.name;
            if (this.result.type === 'product') return this.result.data.product?.default_code || this.result.data.product?.name;
            if (this.result.type === 'bin' || this.result.type === 'dock') return this.result.data.name;
            return "";
        },
        headerIcon() {
            if (!this.result) return "fa fa-search";
            const map = {
                location: "fa fa-map-marker text-warning",
                product: "fa fa-cube text-primary",
                bin: "fa fa-archive text-success",
                dock: "fa fa-truck text-info"
            };
            return map[this.result.type] || "fa fa-info-circle";
        },
        // Lazy items for location products
        visibleLocationItems() {
            if (!this.result?.data?.stock_summary?.items) return [];
            return this.result.data.stock_summary.items.slice(0, this.lazyLimit);
        },
        hasMoreLocationItems() {
            if (!this.result?.data?.stock_summary?.items) return false;
            return this.visibleLocationItems.length < this.result.data.stock_summary.items.length;
        },
        // Lazy items for product locations
        visibleProductLocations() {
            if (!this.result?.data?.stock_summary?.locations) return [];
            return this.result.data.stock_summary.locations.slice(0, this.lazyLimit);
        },
        hasMoreProductLocations() {
            if (!this.result?.data?.stock_summary?.locations) return false;
            return this.visibleProductLocations.length < this.result.data.stock_summary.locations.length;
        },
        // Lazy items for container packages
        visiblePackages() {
            if (!this.result?.data?.packages) return [];
            return this.result.data.packages.slice(0, this.lazyLimit);
        },
        hasMorePackages() {
            if (!this.result?.data?.packages) return false;
            return this.visiblePackages.length < this.result.data.packages.length;
        },
        // Lazy items for container moves
        visibleMoves() {
            if (!this.result?.data?.moves) return [];
            return this.result.data.moves.slice(0, this.lazyLimit);
        },
        hasMoreMoves() {
            if (!this.result?.data?.moves) return false;
            return this.visibleMoves.length < this.result.data.moves.length;
        }
    },
    watch: {
        result() {
            this.lazyLimit = 5;
            this.activeContainerTab = 'packages';
        }
    },
    methods: {
        loadMore() {
            this.lazyLimit += 5;
        },
        handleScroll(e) {
            const target = e.target;
            if (!target) return;
            const { scrollTop, scrollHeight, clientHeight } = target;
            if (scrollTop + clientHeight >= scrollHeight - 50) {
                if (this.scrollDebounceTimer) return;
                this.scrollDebounceTimer = setTimeout(() => {
                    this.scrollDebounceTimer = null;
                }, 200);
                this.loadMore();
            }
        },
        onDialogShow() {
            this.$nextTick(() => {
                const dialogContent = document.querySelector('.universal-lookup-dialog .p-dialog-content');
                if (dialogContent) {
                    dialogContent.removeEventListener('scroll', this.handleScroll);
                    dialogContent.addEventListener('scroll', this.handleScroll);
                }
            });
        },
        handleImageError(e) {
            e.target.style.display = 'none';
        },
        closeDialog() {
            this.visibleModel = false;
        },
        onHide() {
            const dialogContent = document.querySelector('.universal-lookup-dialog .p-dialog-content');
            if (dialogContent) {
                dialogContent.removeEventListener('scroll', this.handleScroll);
            }
            this.$emit("closed");
        }
    }
};
</script>

<style scoped>
.modal-header-custom {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}
.header-icon {
    font-size: 1.6rem;
}
.header-texts {
    display: flex;
    flex-direction: column;
}
.header-type-badge {
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    color: var(--primary-color, #eab308);
    text-transform: uppercase;
}
.header-main-title {
    margin: 0;
    font-size: 1.1rem;
    font-weight: 700;
    color: #1f2937;
    line-height: 1.2;
}

.loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3rem 1rem;
    gap: 1rem;
    color: #6b7280;
}

.modal-body-scrollable {
    max-height: 70vh;
    overflow-y: auto;
    padding: 0.25rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

/* Status Grid (Location) */
.status-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.5rem;
}
.status-card {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.6rem 0.75rem;
    border-radius: 8px;
    border: 1px solid #e5e7eb;
    background: #f9fafb;
}
.status-card i {
    font-size: 1.2rem;
}
.status-card-label {
    display: block;
    font-size: 0.68rem;
    text-transform: uppercase;
    color: #6b7280;
    font-weight: 600;
}
.status-card-val {
    display: block;
    font-size: 0.85rem;
    font-weight: 700;
    color: #111827;
}

.card-success { background: #f0fdf4; border-color: #bbf7d0; color: #166534; }
.card-success i { color: #16a34a; }
.card-warning { background: #fffbeb; border-color: #fde68a; color: #92400e; }
.card-warning i { color: #d97706; }
.card-danger { background: #fef2f2; border-color: #fecaca; color: #991b1b; }
.card-danger i { color: #dc2626; }
.card-info { background: #eff6ff; border-color: #bfdbfe; color: #1e40af; }
.card-info i { color: #2563eb; }
.card-purple { background: #faf5ff; border-color: #e9d5ff; color: #6b21a8; }
.card-purple i { color: #9333ea; }
.card-neutral { background: #f9fafb; border-color: #e5e7eb; color: #4b5563; }
.card-neutral i { color: #9ca3af; }

/* Sections */
.section-title {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.82rem;
    font-weight: 700;
    color: #374151;
    border-bottom: 1px solid #e5e7eb;
    padding-bottom: 0.35rem;
    margin-top: 0.5rem;
}
.lazy-counter {
    color: #6b7280;
    font-size: 0.72rem;
    font-weight: normal;
}

.empty-list-msg {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 1.5rem 1rem;
    gap: 0.5rem;
    color: #9ca3af;
    background: #f9fafb;
    border-radius: 8px;
    font-size: 0.85rem;
}

/* Item cards in Location */
.items-list, .locations-list, .packages-list, .moves-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}
.item-card {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 0.5rem 0.65rem;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03);
}
.item-img-wrapper {
    width: 44px;
    height: 44px;
    flex-shrink: 0;
    background: #f3f4f6;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
}
.item-thumb {
    width: 100%;
    height: 100%;
    object-fit: cover;
}
.item-info {
    flex: 1;
    min-width: 0;
}
.item-name {
    margin: 0;
    font-size: 0.82rem;
    font-weight: 600;
    color: #111827;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.item-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-top: 0.2rem;
}
.tag-sku, .tag-barcode, .tag-lot {
    font-size: 0.68rem;
    background: #f3f4f6;
    padding: 1px 5px;
    border-radius: 4px;
    color: #4b5563;
}
.item-qty-box {
    text-align: right;
    flex-shrink: 0;
}
.qty-avail {
    display: block;
    font-size: 1.05rem;
    font-weight: 800;
    color: #16a34a;
}
.qty-uom {
    display: block;
    font-size: 0.68rem;
    color: #6b7280;
}
.qty-total {
    display: block;
    font-size: 0.62rem;
    color: #9ca3af;
}

/* Product View */
.product-header-card {
    display: flex;
    gap: 1rem;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 0.75rem;
}
.product-photo-box {
    width: 88px;
    height: 88px;
    flex-shrink: 0;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
}
.product-large-img {
    width: 100%;
    height: 100%;
    object-fit: contain;
}
.product-core-data {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}
.product-name {
    margin: 0;
    font-size: 0.95rem;
    font-weight: 700;
    color: #0f172a;
    line-height: 1.25;
}
.product-code-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin: 0.35rem 0;
}
.badge-sku, .badge-barcode {
    font-size: 0.7rem;
    background: #e2e8f0;
    padding: 2px 6px;
    border-radius: 4px;
    color: #334155;
    font-weight: 600;
}
.product-stock-totals {
    display: flex;
    gap: 0.5rem;
}
.stock-pill {
    flex: 1;
    text-align: center;
    padding: 0.25rem 0.4rem;
    border-radius: 6px;
    background: #ffffff;
    border: 1px solid #cbd5e1;
}
.stock-pill .label {
    display: block;
    font-size: 0.62rem;
    color: #64748b;
    text-transform: uppercase;
    font-weight: 600;
}
.stock-pill .num {
    display: block;
    font-size: 0.95rem;
    font-weight: 800;
}
.stock-pill.avail .num { color: #16a34a; }
.stock-pill.total .num { color: #0284c7; }
.stock-pill.reserved .num { color: #d97706; }

/* Dimensions card */
.dimensions-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 0.6rem 0.75rem;
}
.dim-title {
    display: block;
    font-size: 0.75rem;
    font-weight: 700;
    color: #4b5563;
    text-transform: uppercase;
    margin-bottom: 0.4rem;
}
.dim-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(70px, 1fr));
    gap: 0.4rem;
}
.dim-item {
    background: #f9fafb;
    border: 1px solid #f3f4f6;
    border-radius: 6px;
    padding: 0.35rem;
    text-align: center;
}
.dim-lbl {
    display: block;
    font-size: 0.62rem;
    color: #6b7280;
    text-transform: uppercase;
}
.dim-val {
    display: block;
    font-size: 0.8rem;
    font-weight: 700;
    color: #111827;
}

/* Locations for product */
.location-row-card {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 0.5rem 0.75rem;
}
.loc-marker {
    font-size: 1.2rem;
    color: #f59e0b;
}
.loc-details {
    flex: 1;
    min-width: 0;
}
.loc-name {
    display: block;
    font-size: 0.82rem;
    font-weight: 700;
    color: #111827;
}
.loc-sub, .loc-lot {
    display: inline-block;
    font-size: 0.68rem;
    color: #6b7280;
    margin-right: 0.4rem;
}
.loc-stock-box {
    text-align: right;
}
.loc-avail {
    font-size: 1.05rem;
    font-weight: 800;
    color: #16a34a;
}
.loc-uom {
    font-size: 0.68rem;
    color: #6b7280;
    margin-left: 2px;
}
.loc-breakdown {
    display: block;
    font-size: 0.62rem;
    color: #9ca3af;
}

/* Container view (BIN / DOCK) */
.container-meta-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 0.75rem;
}
.meta-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.meta-type {
    font-size: 0.68rem;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
}
.meta-title {
    margin: 0;
    font-size: 1.15rem;
    font-weight: 800;
    color: #0f172a;
}
.state-badge {
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 0.72rem;
    font-weight: 700;
}
.badge-ok { background: #dcfce7; color: #166534; }
.badge-blocked { background: #fee2e2; color: #991b1b; }
.meta-extra {
    display: flex;
    gap: 0.75rem;
    margin-top: 0.4rem;
    font-size: 0.75rem;
    color: #475569;
}

.tab-switcher {
    display: flex;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    overflow: hidden;
}
.switch-btn {
    flex: 1;
    padding: 0.5rem;
    border: none;
    background: #f1f5f9;
    color: #475569;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
}
.switch-btn.active {
    background: #ffffff;
    color: #0f172a;
    border-bottom: 2px solid var(--primary-color, #eab308);
}

.package-card, .move-card {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 0.5rem 0.65rem;
}
.pkg-icon {
    font-size: 1.2rem;
    color: #64748b;
}
.pkg-info {
    flex: 1;
    min-width: 0;
}
.pkg-name {
    display: block;
    font-size: 0.82rem;
    font-weight: 700;
    color: #0f172a;
}
.pkg-so {
    display: block;
    font-size: 0.7rem;
    color: #64748b;
}
.pkg-status {
    font-size: 0.7rem;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
    background: #f1f5f9;
    color: #334155;
}

.move-thumb {
    width: 40px;
    height: 40px;
    border-radius: 6px;
    object-fit: cover;
    background: #f8fafc;
}
.move-info {
    flex: 1;
    min-width: 0;
}
.move-name {
    display: block;
    font-size: 0.8rem;
    font-weight: 700;
    color: #0f172a;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.move-sub {
    display: block;
    font-size: 0.68rem;
    color: #64748b;
}
.move-qty {
    text-align: right;
}
.qty-done {
    font-size: 0.95rem;
    font-weight: 800;
    color: #16a34a;
}
.qty-demand {
    font-size: 0.72rem;
    color: #64748b;
}

.load-more-section {
    padding-top: 0.35rem;
}
.btn-load-more {
    font-weight: 600;
}

.modal-footer-custom {
    width: 100%;
}
</style>

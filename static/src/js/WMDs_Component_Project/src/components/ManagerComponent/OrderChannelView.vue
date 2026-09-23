<template>
  <div class="order-channel-view">
    <!-- Header Title Bar -->
    <div class="header-bar">
      <div class="title-group">
        <i class="fa fa-bullhorn title-icon"></i>
        <div>
          <h2 class="view-title">Canal SLA & Pedidos</h2>
          <p class="view-subtitle">Monitoreo en tiempo real de estatus de pedidos y compromisos de recolección SLA</p>
        </div>
      </div>
      <div class="badges-group">
        <button class="btn-config-sla mr-2" @click="openSlaModal">
          <i class="fa fa-sliders mr-1"></i> Configurar SLA
        </button>
        <div v-if="overdueCount > 0" class="alert-summary-badge overdue-badge">
          <i class="fa fa-exclamation-triangle mr-1"></i>
          <span>{{ overdueCount }} Vencidos</span>
        </div>
        <div v-if="criticalCount > 0" class="alert-summary-badge critical-badge">
          <i class="fa fa-clock-o mr-1"></i>
          <span>{{ criticalCount }} Críticos (&lt; 1h)</span>
        </div>
      </div>
    </div>

    <!-- Filters and Search Toolbar -->
    <div class="toolbar-card">
      <div class="search-input-wrapper">
        <i class="fa fa-search search-icon"></i>
        <input 
          type="text" 
          v-model="searchQuery" 
          @input="onSearchInput"
          @keyup.enter="fetchOrders"
          placeholder="Buscar por Folio SO, Picking, Guía o Cliente..." 
          class="custom-input"
        />
        <button v-if="searchQuery" class="btn-clear" @click="clearSearch">
          <i class="fa fa-times-circle"></i>
        </button>
      </div>

      <!-- Status Filter Chips -->
      <div class="filter-chips">
        <button 
          v-for="st in statusOptions" 
          :key="st.value"
          class="chip-button"
          :class="{ active: activeStatus === st.value }"
          @click="setStatusFilter(st.value)"
        >
          {{ st.label }}
          <span v-if="st.count !== undefined" class="chip-badge">({{ st.count }})</span>
        </button>
      </div>

      <!-- Channel Select & Refresh -->
      <div class="channel-controls">
        <label class="filter-label"><i class="fa fa-filter mr-1"></i>Canal:</label>
        <select v-model="activeChannel" @change="fetchOrders" class="custom-select">
          <option value="all">Todos los Canales</option>
          <option v-for="ch in availableChannels" :key="ch" :value="ch">{{ ch }}</option>
        </select>

        <button class="btn-refresh" @click="fetchOrders" title="Actualizar Datos">
          <i class="fa fa-refresh" :class="{'fa-spin': isRefreshing}"></i>
        </button>
      </div>
    </div>

    <!-- Data Display Content -->
    <div class="content-body">
      <div v-if="isRefreshing && orders.length === 0" class="state-message">
        <i class="fa fa-spinner fa-spin fa-2x mb-2"></i>
        <p>Cargando información de pedidos...</p>
      </div>

      <div v-else-if="orders.length === 0" class="state-message">
        <i class="fa fa-inbox fa-3x mb-2 text-muted"></i>
        <p>No se encontraron pedidos con los criterios de búsqueda aplicados.</p>
      </div>

      <div v-else class="orders-grid">
        <div 
          v-for="ord in orders" 
          :key="ord.id" 
          class="order-data-card"
          :class="{'card-alert-critical': ord.sla_priority_level === 'critical_1h' || ord.sla_priority_level === 'overdue'}"
        >
          <!-- Top Row: Order Name & Channel -->
          <div class="card-row-top">
            <span class="so-number">{{ ord.sale_order_name || ord.name }}</span>
            <span class="channel-pill" :class="getChannelClass(ord.channel)">
              {{ ord.channel || 'Directo' }}
            </span>
          </div>

          <!-- Middle Row: Latest Registered Picking & WMDS Log Hover -->
          <div class="card-row-sub">
            <span 
              class="pick-code-wrapper"
              :title="ord.latest_wmds_log ? ('Último log WMDS (' + (ord.latest_wmds_log_date || '') + ' - ' + (ord.latest_wmds_log_user || 'Sistema') + '):\n' + ord.latest_wmds_log) : 'Sin logs WMDS registrados para este traslado'"
            >
              <i class="fa fa-cube mr-1 text-primary"></i>
              <span class="pick-name">Último Traslado: <strong>{{ ord.name }}</strong></span>
              <i v-if="ord.latest_wmds_log" class="fa fa-info-circle ml-1 log-hover-icon"></i>
            </span>
          </div>

          <!-- SLA Priority Row -->
          <div v-if="ord.sla_priority_label || ord.sla_date" class="sla-info-box">
            <div class="sla-status-tag" :class="ord.sla_priority_level || 'normal'">
              <i class="fa fa-clock-o mr-1"></i>
              <span>{{ ord.sla_priority_label || 'SLA Programado' }}</span>
            </div>
            <span v-if="ord.sla_date" class="sla-timestamp">
              Límite: {{ formatSlaTime(ord.sla_date) }}
            </span>
          </div>

          <div v-if="ord.yuju_due_date" class="yuju-due-box">
            <i class="fa fa-calendar-check-o mr-1"></i>
            <span>Due Marketplace: <strong>{{ ord.yuju_due_date }}</strong></span>
          </div>
        </div>
      </div>
    </div>

    <!-- SLA Configuration Modal -->
    <div v-if="showSlaModal" class="modal-backdrop" @click.self="closeSlaModal">
      <div class="modal-card">
        <div class="modal-header">
          <h3 class="modal-title"><i class="fa fa-sliders mr-2 text-primary"></i>Configuración de Horarios SLA por Marketplace</h3>
          <button class="btn-modal-close" @click="closeSlaModal"><i class="fa fa-times"></i></button>
        </div>

        <div class="modal-body">
          <div class="modal-actions-bar">
            <p class="section-desc">Gestiona las reglas de SLA para marketplaces que no provienen de Yuju o requieren cálculo por horario.</p>
            <button class="btn-primary-sm" @click="prepareNewRule">
              <i class="fa fa-plus mr-1"></i> Nueva Regla SLA
            </button>
          </div>

          <!-- Rules Table -->
          <div class="table-responsive mb-3">
            <table class="rules-table">
              <thead>
                <tr>
                  <th>Marketplace</th>
                  <th>Origen SLA</th>
                  <th>Límite Recolección</th>
                  <th>Lun-Vie</th>
                  <th>Sáb</th>
                  <th>Dom</th>
                  <th>Flex</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="schedulesLoading">
                  <td colspan="8" class="text-center py-3"><i class="fa fa-spinner fa-spin mr-1"></i> Cargando reglas...</td>
                </tr>
                <tr v-else-if="schedulesList.length === 0">
                  <td colspan="8" class="text-center py-3 text-muted">No hay reglas SLA configuradas. Haz clic en "Nueva Regla SLA" para agregar una.</td>
                </tr>
                <tr v-for="rule in schedulesList" :key="rule.id" :class="{ 'row-editing': formRule.id === rule.id }">
                  <td><strong>{{ rule.marketplace }}</strong></td>
                  <td>
                    <span class="badge-source" :class="rule.sla_source">
                      {{ getSlaSourceLabel(rule.sla_source) }}
                    </span>
                  </td>
                  <td>{{ formatCutoffTime(rule.collection_cutoff_time) }}</td>
                  <td>{{ rule.monday_to_friday_ }}h</td>
                  <td>{{ rule.saturday }}h</td>
                  <td>{{ rule.sunday }}h</td>
                  <td>{{ rule.flex || 0 }}m</td>
                  <td class="action-buttons">
                    <button class="btn-icon text-info mr-2" @click="editRule(rule)" title="Editar"><i class="fa fa-pencil"></i></button>
                    <button class="btn-icon text-danger" @click="deleteRule(rule.id)" title="Eliminar"><i class="fa fa-trash"></i></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Rule Edit / Form Panel -->
          <div v-if="showRuleForm" class="rule-form-card">
            <h4 class="form-title">
              {{ formRule.id ? 'Editar Regla SLA - ' + formRule.marketplace : 'Nueva Regla SLA por Marketplace' }}
            </h4>

            <div class="form-grid">
              <div class="form-group">
                <label>Marketplace:</label>
                <select v-model="formRule.marketplace" class="custom-select-sm">
                  <option value="" disabled>Selecciona un Marketplace</option>
                  <option v-for="ch in availableChannels" :key="ch" :value="ch">{{ ch }}</option>
                </select>
              </div>

              <div class="form-group">
                <label>Origen de SLA:</label>
                <select v-model="formRule.sla_source" class="custom-select-sm">
                  <option value="auto">Automático / Híbrido (Yuju si existe, si no Calcular)</option>
                  <option value="yuju">Yuju (Fecha Límite Marketplace)</option>
                  <option value="calculated">Cálculo por Horario (SLA Schedule)</option>
                </select>
              </div>

              <div class="form-group">
                <label>Hora Límite Recolección (ej. 17.0 = 5:00 PM):</label>
                <input type="number" step="0.5" min="0" max="24" v-model.number="formRule.collection_cutoff_time" class="custom-input-sm" />
              </div>

              <div class="form-group">
                <label>Lunes a Viernes (Horas a sumar):</label>
                <input type="number" step="0.5" min="0" v-model.number="formRule.monday_to_friday_" class="custom-input-sm" />
              </div>

              <div class="form-group">
                <label>Sábado (Horas a sumar):</label>
                <input type="number" step="0.5" min="0" v-model.number="formRule.saturday" class="custom-input-sm" />
              </div>

              <div class="form-group">
                <label>Domingo (Horas a sumar):</label>
                <input type="number" step="0.5" min="0" v-model.number="formRule.sunday" class="custom-input-sm" />
              </div>

              <div class="form-group" v-if="isMercadoLibreForm">
                <label>Flex (Minutos - Mercado Libre):</label>
                <input type="number" min="0" v-model.number="formRule.flex" class="custom-input-sm" />
              </div>

              <div class="form-group checkbox-group">
                <label class="checkbox-label">
                  <input type="checkbox" v-model="formRule.auto_fill_dates" />
                  Auto-completar Priority Date
                </label>
              </div>
            </div>

            <div class="form-actions">
              <button class="btn-secondary-sm mr-2" @click="showRuleForm = false">Cancelar</button>
              <button class="btn-primary-sm" @click="saveRule" :disabled="isSavingRule">
                <i class="fa fa-save mr-1"></i> Guardar Regla
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { useGeneralStore } from "../../store/index";

export default {
  name: "OrderChannelView",
  data() {
    return {
      store: useGeneralStore(),
      isRefreshing: false,
      searchQuery: "",
      searchTimeout: null,
      activeStatus: "all",
      activeChannel: "all",
      availableChannels: [],
      orders: [],
      criticalCount: 0,
      overdueCount: 0,
      timerId: null,

      // Modal SLA Config
      showSlaModal: false,
      schedulesLoading: false,
      schedulesList: [],
      showRuleForm: false,
      isSavingRule: false,
      formRule: {
        id: null,
        marketplace: "",
        sla_source: "auto",
        collection_cutoff_time: 17.0,
        monday_to_friday_: 24,
        saturday: 0,
        sunday: 0,
        flex: 0,
        sameDay_nextDay: 0,
        auto_fill_dates: false
      }
    };
  },
  computed: {
    statusOptions() {
      return [
        { label: "Todos", value: "all" },
        { label: "Vencidos", value: "overdue", count: this.overdueCount },
        { label: "Críticos (< 1h)", value: "critical_1h", count: this.criticalCount },
        { label: "Urgentes (< 2h)", value: "urgent_2h" },
        { label: "Advertencia (< 6h)", value: "warning_6h" },
        { label: "En Tiempo (< 24h)", value: "notice_24h" },
        { label: "Normal (> 24h)", value: "normal" }
      ];
    },
    isMercadoLibreForm() {
      if (!this.formRule.marketplace) return false;
      const m = this.formRule.marketplace.toLowerCase();
      return m.includes("mercado") || m.includes("meli");
    }
  },
  methods: {
    setStatusFilter(val) {
      this.activeStatus = val;
      this.fetchOrders();
    },
    onSearchInput() {
      if (this.searchTimeout) clearTimeout(this.searchTimeout);
      this.searchTimeout = setTimeout(() => {
        this.fetchOrders();
      }, 400);
    },
    clearSearch() {
      this.searchQuery = "";
      this.fetchOrders();
    },
    async fetchOrders() {
      this.isRefreshing = true;
      try {
        const res = await this.store.callOdooSilent("order_channel_query", "", {
          query: this.searchQuery,
          status_filter: this.activeStatus,
          channel_filter: this.activeChannel,
          limit: 50
        });

        if (res) {
          if (res.results) {
            this.orders = res.results;
          } else {
            this.orders = [];
          }
          if (res.available_channels && Array.isArray(res.available_channels) && res.available_channels.length > 0) {
            this.availableChannels = res.available_channels;
          }
        }
      } catch (e) {
        console.error("Error al consultar el canal de pedidos:", e);
      } finally {
        this.isRefreshing = false;
      }
    },
    async checkExpiringAlerts() {
      try {
        const res = await this.store.callOdooSilent("sla_expiring_alerts", "", {});
        if (res && res.success) {
          const prevCount = this.criticalCount;
          this.criticalCount = res.critical_count !== undefined ? res.critical_count : (res.total_critical || 0);
          this.overdueCount = res.overdue_count !== undefined ? res.overdue_count : (res.total_overdue || 0);
          this.store.sla_critical_count = this.criticalCount;
          this.store.sla_overdue_count = this.overdueCount;

          if (this.criticalCount > prevCount && this.criticalCount > 0) {
            this.$toast.add({
              severity: "warn",
              summary: "ALERTA DE RECOLECCIÓN SLA",
              detail: `Hay ${this.criticalCount} pedido(s) con vencimiento en menos de 1 hora.`,
              life: 7000
            });
          }
        }
      } catch (e) {
        console.error("Error al verificar alertas SLA:", e);
      }
    },

    // Modal SLA Management
    async openSlaModal() {
      this.showSlaModal = true;
      await this.fetchSchedules();
    },
    closeSlaModal() {
      this.showSlaModal = false;
      this.showRuleForm = false;
    },
    async fetchSchedules() {
      this.schedulesLoading = true;
      try {
        const res = await this.store.callOdooSilent("get_marketplace_schedules", "", {});
        if (res && res.success) {
          this.schedulesList = res.schedules || [];
          if (res.available_channels && Array.isArray(res.available_channels)) {
            this.availableChannels = res.available_channels;
          }
        }
      } catch (e) {
        console.error("Error cargando horarios SLA:", e);
      } finally {
        this.schedulesLoading = false;
      }
    },
    prepareNewRule() {
      this.formRule = {
        id: null,
        marketplace: this.availableChannels.length > 0 ? this.availableChannels[0] : "",
        sla_source: "auto",
        collection_cutoff_time: 17.0,
        monday_to_friday_: 24,
        saturday: 0,
        sunday: 0,
        flex: 0,
        sameDay_nextDay: 0,
        auto_fill_dates: false
      };
      this.showRuleForm = true;
    },
    editRule(rule) {
      this.formRule = { ...rule };
      this.showRuleForm = true;
    },
    async saveRule() {
      if (!this.formRule.marketplace) return;
      this.isSavingRule = true;
      try {
        const res = await this.store.callOdooSilent("save_marketplace_schedule", "", { data: this.formRule });
        if (res && res.success) {
          await this.fetchSchedules();
          this.showRuleForm = false;
          this.fetchOrders();
        }
      } catch (e) {
        console.error("Error guardando regla SLA:", e);
      } finally {
        this.isSavingRule = false;
      }
    },
    async deleteRule(id) {
      if (!confirm("¿Eliminar esta regla de SLA?")) return;
      try {
        const res = await this.store.callOdooSilent("delete_marketplace_schedule", "", { id });
        if (res && res.success) {
          await this.fetchSchedules();
          this.fetchOrders();
        }
      } catch (e) {
        console.error("Error eliminando regla SLA:", e);
      }
    },
    getSlaSourceLabel(src) {
      switch (src) {
        case "auto": return "Automático / Yuju";
        case "yuju": return "Yuju";
        case "calculated": return "Calculado";
        default: return src || "Auto";
      }
    },
    formatCutoffTime(val) {
      if (val === undefined || val === null) return "17:00";
      const hrs = Math.floor(val);
      const mins = Math.round((val - hrs) * 60);
      return `${String(hrs).padStart(2, "0")}:${String(mins).padStart(2, "0")}`;
    },

    getChannelClass(ch) {
      if (!ch) return "ch-default";
      const c = ch.toLowerCase();
      if (c.includes("mercadolibre") || c.includes("mercado libre")) return "ch-meli";
      if (c.includes("coppel")) return "ch-coppel";
      if (c.includes("tiktok")) return "ch-tiktok";
      if (c.includes("amazon")) return "ch-amazon";
      if (c.includes("walmart")) return "ch-walmart";
      if (c.includes("shopify")) return "ch-shopify";
      return "ch-default";
    },
    getStateClass(st) {
      switch (st) {
        case "assigned": return "st-assigned";
        case "done": return "st-done";
        case "cancel": return "st-cancel";
        case "waiting":
        case "confirmed": return "st-waiting";
        default: return "st-default";
      }
    },
    getStatusLabel(st) {
      switch (st) {
        case "assigned": return "Asignado";
        case "done": return "Completado";
        case "cancel": return "Cancelado";
        case "waiting": return "Esperando";
        case "confirmed": return "Confirmado";
        case "draft": return "Borrador";
        default: return st || "Procesando";
      }
    },
    formatSlaTime(dtStr) {
      if (!dtStr) return "";
      try {
        const dt = new Date(dtStr.endsWith("Z") ? dtStr : dtStr + "Z");
        return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      } catch (e) {
        return dtStr;
      }
    }
  },
  mounted() {
    this.fetchOrders();
    this.checkExpiringAlerts();
    this.timerId = setInterval(() => {
      this.checkExpiringAlerts();
    }, 60000);
  },
  beforeUnmount() {
    if (this.timerId) clearInterval(this.timerId);
  }
};
</script>

<style scoped>
.order-channel-view {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #ffffff;
}

.header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  width: 100%;
}
.title-group {
  display: flex;
  align-items: center;
  gap: 12px;
}
.title-icon {
  font-size: 1.8rem;
  color: #d97706;
}
.view-title {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 700;
  color: #111827;
}
.view-subtitle {
  margin: 2px 0 0 0;
  font-size: 0.85rem;
  color: #6b7280;
}
.badges-group {
  display: flex;
  align-items: center;
}
.btn-config-sla {
  background: #4f46e5;
  color: #ffffff;
  border: none;
  padding: 7px 14px;
  border-radius: 6px;
  font-weight: 600;
  font-size: 0.85rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  transition: background-color 0.2s;
}
.btn-config-sla:hover {
  background: #4338ca;
}
.alert-summary-badge {
  background-color: #ef4444;
  color: #ffffff;
  padding: 6px 14px;
  border-radius: 20px;
  font-weight: 700;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  box-shadow: 0 2px 4px rgba(239, 68, 68, 0.2);
  margin-left: 8px;
}
.overdue-badge {
  background-color: #dc2626;
}
.critical-badge {
  background-color: #f59e0b;
}

.toolbar-card {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
}
.search-input-wrapper {
  position: relative;
  flex: 1;
  min-width: 250px;
}
.search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: #9ca3af;
}
.custom-input {
  width: 100%;
  padding: 8px 32px 8px 34px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 0.9rem;
  outline: none;
}
.custom-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}
.btn-clear {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: #9ca3af;
  cursor: pointer;
}

.filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.chip-button {
  background: #ffffff;
  border: 1px solid #d1d5db;
  color: #374151;
  padding: 6px 12px;
  border-radius: 16px;
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}
.chip-button:hover {
  background: #f3f4f6;
}
.chip-button.active {
  background: #2563eb;
  color: #ffffff;
  border-color: #2563eb;
}
.chip-badge {
  margin-left: 4px;
  font-size: 0.75rem;
  opacity: 0.9;
}

.channel-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}
.filter-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: #4b5563;
}
.custom-select {
  padding: 6px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 0.85rem;
  background-color: #ffffff;
  outline: none;
}
.btn-refresh {
  background: #ffffff;
  border: 1px solid #d1d5db;
  padding: 6px 10px;
  border-radius: 6px;
  color: #4b5563;
  cursor: pointer;
}
.btn-refresh:hover {
  background: #f3f4f6;
}

.content-body {
  flex: 1;
  overflow-y: auto;
}
.state-message {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
  color: #6b7280;
}

.orders-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
  padding-bottom: 16px;
}

.order-data-card {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.order-data-card:hover {
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
  transform: translateY(-2px);
}
.card-alert-critical {
  border-left: 4px solid #ef4444;
}

.card-row-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.so-number {
  font-weight: 700;
  font-size: 1.05rem;
  color: #111827;
}

.channel-pill {
  padding: 3px 8px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
}
.ch-meli { background: #ffe600; color: #2d3277; }
.ch-coppel { background: #fff100; color: #0055a5; }
.ch-tiktok { background: #000000; color: #ffffff; }
.ch-amazon { background: #ff9900; color: #111111; }
.ch-walmart { background: #0071ce; color: #ffffff; }
.ch-shopify { background: #95bf47; color: #ffffff; }
.ch-default { background: #e5e7eb; color: #374151; }

.card-row-sub {
  font-size: 0.85rem;
  color: #4b5563;
}
.pick-code-wrapper {
  display: inline-flex;
  align-items: center;
  cursor: pointer;
}
.log-hover-icon {
  color: #3b82f6;
  font-size: 0.85rem;
}

.sla-info-box {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #f8fafc;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 0.8rem;
}
.sla-status-tag {
  font-weight: 600;
  display: flex;
  align-items: center;
}
.sla-status-tag.critical_1h { color: #dc2626; }
.sla-status-tag.urgent_2h { color: #d97706; }
.sla-status-tag.warning_6h { color: #b45309; }
.sla-status-tag.notice_24h { color: #2563eb; }
.sla-status-tag.normal { color: #059669; }
.sla-status-tag.overdue { color: #991b1b; }

.sla-timestamp {
  font-size: 0.75rem;
  color: #64748b;
  font-weight: 500;
}

.yuju-due-box {
  font-size: 0.78rem;
  color: #475569;
}

/* Modal CSS */
.modal-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}
.modal-card {
  background: #ffffff;
  border-radius: 12px;
  width: 90%;
  max-width: 920px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);
  overflow: hidden;
}
.modal-header {
  padding: 16px 24px;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #f9fafb;
}
.modal-title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  color: #111827;
}
.btn-modal-close {
  background: none;
  border: none;
  font-size: 1.2rem;
  color: #9ca3af;
  cursor: pointer;
}
.btn-modal-close:hover {
  color: #374151;
}
.modal-body {
  padding: 20px 24px;
  overflow-y: auto;
}
.modal-actions-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.section-desc {
  margin: 0;
  font-size: 0.85rem;
  color: #6b7280;
}

.rules-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
.rules-table th, .rules-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #e5e7eb;
  text-align: left;
}
.rules-table th {
  background-color: #f9fafb;
  font-weight: 600;
  color: #4b5563;
}
.badge-source {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}
.badge-source.auto { background-color: #e0e7ff; color: #3730a3; }
.badge-source.yuju { background-color: #d1fae5; color: #065f46; }
.badge-source.calculated { background-color: #fef3c7; color: #92400e; }

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.9rem;
}

.rule-form-card {
  background-color: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  margin-top: 16px;
}
.form-title {
  margin: 0 0 14px 0;
  font-size: 1rem;
  font-weight: 700;
  color: #1f2937;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.form-group label {
  font-size: 0.78rem;
  font-weight: 600;
  color: #374151;
}
.custom-select-sm, .custom-input-sm {
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid #d1d5db;
  font-size: 0.85rem;
  background-color: #ffffff;
}
.checkbox-group {
  justify-content: flex-end;
}
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
.btn-primary-sm {
  background-color: #2563eb;
  color: #ffffff;
  border: none;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
}
.btn-primary-sm:hover { background-color: #1d4ed8; }
.btn-secondary-sm {
  background-color: #e5e7eb;
  color: #374151;
  border: none;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
}
.btn-secondary-sm:hover { background-color: #d1d5db; }
</style>

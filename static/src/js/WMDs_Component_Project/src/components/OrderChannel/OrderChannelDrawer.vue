<template>
  <div class="order-channel-container">
    <!-- Floating Action Button (Global) -->
    <button 
      class="channel-fab-btn" 
      :class="{'has-critical': criticalCount > 0}"
      @click="toggleDrawer"
      title="Canal de Pedidos y Alertas SLA"
    >
      <i class="fa fa-bullhorn fab-icon"></i>
      <span class="fab-label">Canal SLA</span>
      <span v-if="criticalCount > 0" class="fab-badge">{{ criticalCount }}</span>
    </button>

    <!-- Side Overlay / Drawer Modal -->
    <div v-if="isOpen" class="channel-drawer-overlay" @click.self="closeDrawer">
      <div class="channel-drawer-panel">
        <!-- Drawer Header -->
        <div class="drawer-header">
          <div class="header-title">
            <i class="fa fa-bullhorn text-warning mr-2"></i>
            <span>Canal de Pedidos & Alertas SLA</span>
          </div>
          <button class="btn-close-drawer" @click="closeDrawer">
            <i class="fa fa-times"></i>
          </button>
        </div>

        <!-- Search & Filter Controls -->
        <div class="drawer-controls">
          <div class="search-box">
            <i class="fa fa-search search-icon"></i>
            <input 
              type="text" 
              v-model="searchQuery" 
              @input="onSearchInput"
              @keyup.enter="fetchOrders"
              placeholder="Buscar SO..., Pick..., Guía, Cliente..." 
              class="search-input"
            />
            <button v-if="searchQuery" class="clear-btn" @click="clearSearch">
              <i class="fa fa-times-circle"></i>
            </button>
          </div>

          <!-- Status Filter Chips -->
          <div class="status-chips">
            <button 
              v-for="st in statusOptions" 
              :key="st.value"
              class="chip-btn"
              :class="{ active: activeStatus === st.value, [st.badgeClass]: true }"
              @click="setStatusFilter(st.value)"
            >
              {{ st.label }}
              <span v-if="st.count !== undefined" class="chip-count">({{ st.count }})</span>
            </button>
          </div>

          <!-- Channel Filter Bar -->
          <div class="channel-filter-bar">
            <label><i class="fa fa-filter mr-1"></i>Canal:</label>
            <select v-model="activeChannel" @change="fetchOrders" class="channel-select">
              <option value="all">Todos los Canales</option>
              <option value="Mercado Libre">Mercado Libre</option>
              <option value="Coppel">Coppel</option>
              <option value="TikTok Shop">TikTok Shop</option>
              <option value="Amazon">Amazon</option>
              <option value="Walmart">Walmart</option>
              <option value="Shopify">Shopify</option>
            </select>
            <button class="btn-refresh" @click="fetchOrders" title="Actualizar">
              <i class="fa fa-refresh" :class="{'fa-spin': loading}"></i>
            </button>
          </div>
        </div>

        <!-- Orders List Body -->
        <div class="drawer-body">
          <div v-if="loading" class="loading-state">
            <i class="fa fa-spinner fa-spin fa-2x"></i>
            <p>Cargando información del canal...</p>
          </div>

          <div v-else-if="orders.length === 0" class="empty-state">
            <i class="fa fa-inbox fa-3x text-muted mb-2"></i>
            <p>No se encontraron pedidos con los criterios seleccionados.</p>
          </div>

          <div v-else class="orders-list">
            <div 
              v-for="ord in orders" 
              :key="ord.id" 
              class="order-card"
              :class="{'card-critical': ord.sla_priority_level === 'critical_1h' || ord.sla_priority_level === 'overdue'}"
            >
              <div class="card-header-row">
                <span class="order-so">{{ ord.sale_order_name || ord.name }}</span>
                <span class="channel-badge" :class="getChannelClass(ord.channel)">
                  {{ ord.channel || 'Directo' }}
                </span>
              </div>

              <div class="card-pick-row">
                <span class="pick-name"><i class="fa fa-cube mr-1"></i>{{ ord.name }}</span>
                <span class="badge-state" :class="getStateClass(ord.state)">
                  {{ getStatusLabel(ord.state) }}
                </span>
              </div>

              <!-- SLA Countdown & Priority Badge -->
              <div v-if="ord.sla_priority_label || ord.sla_date" class="sla-row">
                <div class="sla-badge" :class="ord.sla_priority_level || 'normal'">
                  <i class="fa fa-clock-o mr-1"></i>
                  <span>{{ ord.sla_priority_label || 'SLA Programado' }}</span>
                </div>
                <span v-if="ord.sla_date" class="sla-time">
                  Limite: {{ formatSlaTime(ord.sla_date) }}
                </span>
              </div>

              <div v-if="ord.yuju_due_date" class="due-date-row">
                <i class="fa fa-calendar-check-o mr-1 text-info"></i>
                <small>Due Marketplace: <strong>{{ ord.yuju_due_date }}</strong></small>
              </div>

              <div class="card-details-grid">
                <div v-if="ord.partner_name" class="detail-item">
                  <i class="fa fa-user"></i>
                  <span>{{ ord.partner_name }}</span>
                </div>
                <div v-if="ord.carrier || ord.carrier_tracking_ref" class="detail-item">
                  <i class="fa fa-truck"></i>
                  <span>{{ ord.carrier }} ({{ ord.carrier_tracking_ref || 'Sin Guía' }})</span>
                </div>
                <div v-if="ord.operator_name" class="detail-item">
                  <i class="fa fa-user-circle"></i>
                  <span>Mesa: {{ ord.operator_name }}</span>
                </div>
                <div class="detail-item">
                  <i class="fa fa-list-ol"></i>
                  <span>{{ ord.move_lines_count }} Ítems</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Drawer Footer -->
        <div class="drawer-footer">
          <small class="text-muted">
            <i class="fa fa-info-circle mr-1"></i> Monitoreo en tiempo real. Actualización automática cada 60s.
          </small>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { useGeneralStore } from "../../store/index";

export default {
  name: "OrderChannelDrawer",
  data() {
    return {
      store: useGeneralStore(),
      isOpen: false,
      loading: false,
      searchQuery: "",
      searchTimeout: null,
      activeStatus: "all",
      activeChannel: "all",
      orders: [],
      criticalCount: 0,
      criticalItems: [],
      timerId: null,
      audioContext: null
    };
  },
  computed: {
    isOpen: {
      get() {
        return this.store.order_channel_drawer_open;
      },
      set(val) {
        this.store.order_channel_drawer_open = val;
      }
    },
    statusOptions() {
      return [
        { label: "Todos", value: "all", badgeClass: "" },
        { label: "⚠️ < 1h Expiración", value: "critical_1h", badgeClass: "chip-critical", count: this.criticalCount },
        { label: "🚨 Vencidos", value: "overdue", badgeClass: "chip-overdue" },
        { label: "📦 Asignados", value: "assigned", badgeClass: "chip-assigned" },
        { label: "✅ Completados", value: "done", badgeClass: "chip-done" },
      ];
    }
  },
  watch: {
    "store.order_channel_drawer_open"(newVal) {
      if (newVal) {
        this.fetchOrders();
      }
    }
  },
  methods: {
    toggleDrawer() {
      this.isOpen = !this.isOpen;
      if (this.isOpen) {
        this.fetchOrders();
      }
    },
    closeDrawer() {
      this.isOpen = false;
    },
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
      this.loading = true;
      try {
        const res = await this.store.callOdooSilent("order_channel_query", "", {
          query: this.searchQuery,
          status_filter: this.activeStatus,
          channel_filter: this.activeChannel,
          limit: 40
        });

        if (res && res.results) {
          this.orders = res.results;
        } else {
          this.orders = [];
        }
      } catch (e) {
        console.error("Error cargando pedidos en canal:", e);
      } finally {
        this.loading = false;
      }
    },
    async checkExpiringAlerts() {
      try {
        const res = await this.store.callOdooSilent("sla_expiring_alerts", "", {});
        if (res && res.success) {
          const prevCount = this.criticalCount;
          this.criticalCount = res.total_critical || 0;
          this.criticalItems = res.items || [];
          this.store.sla_critical_count = this.criticalCount;

          // Si incrementaron las alertas críticas, mostrar Toast y sonido
          if (this.criticalCount > prevCount && this.criticalCount > 0) {
            this.triggerProactiveAlert(this.criticalCount);
          }
        }
      } catch (e) {
        console.error("Error verificando alertas SLA:", e);
      }
    },

    triggerProactiveAlert(count) {
      // Toast proactivo global
      this.$toast.add({
        severity: "warn",
        summary: "⚠️ ALERTA DE RECOLECCIÓN SLA",
        detail: `¡Tienes ${count} pedido(s) que vencen en menos de 1 hora!`,
        life: 8000
      });

      // Emisión de tono de alerta sintético
      this.playAlertTone();
    },
    playAlertTone() {
      try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(880, ctx.currentTime); // Nota A5
        osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.4);
        gain.gain.setValueAtTime(0.15, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.4);
      } catch (e) {
        // Ignorar si el navegador bloquea audio sin interacción
      }
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
    this.checkExpiringAlerts();
    // Temporizador background cada 60 segundos
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
/* Floating Action Button */
.channel-fab-btn {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 9999;
  background-color: #1e293b;
  color: #ffffff;
  border: 2px solid #3b82f6;
  border-radius: 30px;
  padding: 10px 18px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  font-size: 0.9rem;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  cursor: pointer;
  transition: all 0.2s ease;
}
.channel-fab-btn:hover {
  transform: translateY(-2px);
  background-color: #0f172a;
  border-color: #60a5fa;
}
.channel-fab-btn.has-critical {
  border-color: #ef4444;
  animation: pulse-border 1.5s infinite;
}
.fab-icon {
  font-size: 1.1rem;
  color: #38bdf8;
}
.channel-fab-btn.has-critical .fab-icon {
  color: #f87171;
}
.fab-badge {
  background-color: #ef4444;
  color: #ffffff;
  border-radius: 12px;
  padding: 2px 8px;
  font-size: 0.75rem;
  font-weight: 800;
}

@keyframes pulse-border {
  0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
  50% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
}

/* Drawer Modal Overlay */
.channel-drawer-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  z-index: 10000;
  display: flex;
  justify-content: flex-end;
}
.channel-drawer-panel {
  width: 440px;
  max-width: 92vw;
  height: 100%;
  background-color: #ffffff;
  box-shadow: -4px 0 20px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
}

/* Header */
.drawer-header {
  padding: 16px 20px;
  background-color: #0f172a;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.header-title {
  font-size: 1.05rem;
  font-weight: 700;
  display: flex;
  align-items: center;
}
.btn-close-drawer {
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 1.2rem;
  cursor: pointer;
}
.btn-close-drawer:hover { color: #ffffff; }

/* Controls Section */
.drawer-controls {
  padding: 12px 16px;
  background-color: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}
.search-box {
  position: relative;
  margin-bottom: 10px;
}
.search-icon {
  position: absolute;
  left: 12px;
  top: 10px;
  color: #64748b;
}
.search-input {
  width: 100%;
  padding: 8px 32px 8px 34px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 0.9rem;
}
.clear-btn {
  position: absolute;
  right: 10px;
  top: 8px;
  background: transparent;
  border: none;
  color: #94a3b8;
  cursor: pointer;
}

/* Status Chips */
.status-chips {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 8px;
}
.chip-btn {
  padding: 4px 10px;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 14px;
  border: 1px solid #cbd5e1;
  background-color: #ffffff;
  color: #475569;
  white-space: nowrap;
  cursor: pointer;
}
.chip-btn.active {
  background-color: #2563eb;
  color: #ffffff;
  border-color: #2563eb;
}
.chip-btn.chip-critical.active { background-color: #ef4444; border-color: #ef4444; }
.chip-btn.chip-overdue.active { background-color: #991b1b; border-color: #991b1b; }

/* Channel Filter Bar */
.channel-filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.82rem;
  color: #475569;
}
.channel-select {
  flex: 1;
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid #cbd5e1;
  font-size: 0.82rem;
}
.btn-refresh {
  background: #f1f5f9;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  padding: 4px 8px;
  cursor: pointer;
}

/* Drawer Body & Orders List */
.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
}
.loading-state, .empty-state {
  text-align: center;
  padding: 40px 16px;
  color: #64748b;
}
.orders-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.order-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}
.order-card.card-critical {
  border-left: 4px solid #ef4444;
  background: #fff5f5;
}

.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.order-so {
  font-weight: 800;
  font-size: 0.95rem;
  color: #0f172a;
}
.channel-badge {
  font-size: 0.7rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 10px;
}
.ch-meli { background: #ffe600; color: #2d3277; }
.ch-coppel { background: #0070c0; color: #ffffff; }
.ch-tiktok { background: #000000; color: #ffffff; }
.ch-amazon { background: #ff9900; color: #000000; }
.ch-walmart { background: #0071ce; color: #ffffff; }
.ch-shopify { background: #95bf47; color: #ffffff; }
.ch-default { background: #e2e8f0; color: #334155; }

.card-pick-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.85rem;
  margin-bottom: 8px;
}
.pick-name { font-weight: 600; color: #334155; }
.badge-state {
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 4px;
}
.st-assigned { background: #dbeafe; color: #1e40af; }
.st-done { background: #dcfce7; color: #166534; }
.st-cancel { background: #fee2e2; color: #991b1b; }
.st-waiting { background: #fef3c7; color: #92400e; }
.st-default { background: #f1f5f9; color: #475569; }

/* SLA Badge */
.sla-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.sla-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 700;
}
.sla-badge.critical_1h { background: #ef4444; color: #ffffff; animation: blink-red 1.5s infinite; }
.sla-badge.urgent_2h { background: #f97316; color: #ffffff; }
.sla-badge.warning_6h { background: #eab308; color: #1e293b; }
.sla-badge.notice_24h { background: #3b82f6; color: #ffffff; }
.sla-badge.overdue { background: #991b1b; color: #ffffff; }
.sla-time { font-size: 0.75rem; color: #64748b; font-weight: 600; }

.due-date-row {
  font-size: 0.78rem;
  color: #334155;
  margin-bottom: 6px;
  background: #f0f9ff;
  padding: 3px 6px;
  border-radius: 4px;
}

.card-details-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  font-size: 0.75rem;
  color: #64748b;
  border-top: 1px dashed #e2e8f0;
  padding-top: 6px;
}
.detail-item {
  display: flex;
  align-items: center;
  gap: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Footer */
.drawer-footer {
  padding: 10px 16px;
  background: #f8fafc;
  border-top: 1px solid #e2e8f0;
  text-align: center;
}

@keyframes blink-red {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>

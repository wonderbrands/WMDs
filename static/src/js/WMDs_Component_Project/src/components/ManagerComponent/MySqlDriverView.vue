<template>
  <div class="mysql-driver-view">
    <!-- Header Title Bar -->
    <div class="header-bar">
      <div class="title-group">
        <i class="fa fa-database title-icon"></i>
        <div>
          <h2 class="view-title">MySqlDriver</h2>
          <p class="view-subtitle">Conector de bases de datos MySQL externas para extracción de fechas de SLA (ej. Amazon RDS)</p>
        </div>
      </div>
      <div class="badges-group">
        <span class="developer-badge">
          <i class="fa fa-code mr-1"></i> WMDs Developer Mode
        </span>
      </div>
    </div>

    <!-- Main Content Container -->
    <div class="content-body" v-if="isLoadingConfigs">
      <div class="state-message">
        <i class="fa fa-spinner fa-spin fa-2x mb-2"></i>
        <p>Cargando configuraciones de MySQL...</p>
      </div>
    </div>

    <div class="content-body" v-else>
      <div v-for="cfg in configs" :key="cfg.id" class="config-card">
        <div class="card-header">
          <div class="header-left">
            <i class="fa fa-server card-icon"></i>
            <div>
              <h3 class="config-name">{{ cfg.name }}</h3>
              <span class="marketplace-pill">{{ cfg.marketplace }}</span>
            </div>
          </div>
          <div class="header-actions">
            <button class="btn-secondary-sm" @click="testConnection(cfg)" :disabled="isTesting">
              <i class="fa" :class="isTesting ? 'fa-spinner fa-spin' : 'fa-plug'"></i> Probar Conexión
            </button>
            <button class="btn-primary-sm" @click="saveConfig(cfg)" :disabled="isSaving">
              <i class="fa" :class="isSaving ? 'fa-spinner fa-spin' : 'fa-save'"></i> Guardar
            </button>
            <button class="btn-success-sm" @click="syncSlaNow(cfg)" :disabled="isSyncing">
              <i class="fa" :class="isSyncing ? 'fa-spinner fa-spin' : 'fa-refresh'"></i> Sincronizar SLA Ahora
            </button>
          </div>
        </div>

        <!-- Connection Parameters Form -->
        <div class="form-grid">
          <div class="form-group span-2">
            <label><i class="fa fa-globe mr-1"></i>Host MySQL (RDS / Servidor):</label>
            <input type="text" v-model="cfg.host" placeholder="wonderbrands1.cuwd36ifbz5t.us-east-1.rds.amazonaws.com" class="custom-input" />
          </div>

          <div class="form-group">
            <label><i class="fa fa-hashtag mr-1"></i>Puerto:</label>
            <input type="number" v-model.number="cfg.port" placeholder="3306" class="custom-input" />
          </div>

          <div class="form-group">
            <label><i class="fa fa-user mr-1"></i>Usuario MySQL:</label>
            <input type="text" v-model="cfg.user" placeholder="demian" class="custom-input" />
          </div>

          <div class="form-group">
            <label><i class="fa fa-key mr-1"></i>Contraseña MySQL:</label>
            <div class="password-wrapper">
              <input :type="showPassword ? 'text' : 'password'" v-model="cfg.password" placeholder="••••••••" class="custom-input" />
              <button class="btn-toggle-pass" @click="showPassword = !showPassword">
                <i class="fa" :class="showPassword ? 'fa-eye-slash' : 'fa-eye'"></i>
              </button>
            </div>
          </div>

          <div class="form-group">
            <label><i class="fa fa-database mr-1"></i>Base de Datos:</label>
            <input type="text" v-model="cfg.database" placeholder="somos_reyes" class="custom-input" />
          </div>

          <div class="form-group">
            <label><i class="fa fa-table mr-1"></i>Tabla de Datos:</label>
            <input type="text" v-model="cfg.table_name" placeholder="amazon_orders" class="custom-input" />
          </div>

          <div class="form-group">
            <label><i class="fa fa-id-card-o mr-1"></i>Campo ID Orden (MySQL):</label>
            <input type="text" v-model="cfg.order_id_field" placeholder="AmazonOrderId" class="custom-input" />
          </div>

          <div class="form-group">
            <label><i class="fa fa-calendar mr-1"></i>Campo Fecha SLA (MySQL):</label>
            <input type="text" v-model="cfg.sla_date_field" placeholder="LatestShipDate" class="custom-input" />
          </div>

          <div class="form-group">
            <label><i class="fa fa-tag mr-1"></i>Marketplace Odoo:</label>
            <input type="text" v-model="cfg.marketplace" placeholder="Amazon" class="custom-input" />
          </div>
        </div>

        <!-- Terminal Output / Sync Status Panel -->
        <div class="status-terminal">
          <div class="terminal-header">
            <span><i class="fa fa-terminal mr-1"></i>Registro de Ejecución & Sincronización Automática (Cada 2h)</span>
            <span v-if="cfg.last_sync_date" class="timestamp-badge">
              Última ejecución: {{ cfg.last_sync_date }}
            </span>
          </div>
          <div class="terminal-body" :class="getTerminalClass(cfg.last_sync_status)">
            <p v-if="!cfg.last_sync_status" class="text-muted">Sin sincronizaciones registradas aún. Haz clic en "Probar Conexión" o "Sincronizar SLA Ahora".</p>
            <pre v-else>{{ cfg.last_sync_status }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { useGeneralStore } from "../../store/index";

export default {
  name: "MySqlDriverView",
  data() {
    return {
      store: useGeneralStore(),
      configs: [],
      isLoadingConfigs: true,
      isTesting: false,
      isSaving: false,
      isSyncing: false,
      showPassword: false,
    };
  },
  methods: {
    async fetchConfigs() {
      this.isLoadingConfigs = true;
      try {
        const res = await this.store.callOdooSilent("get_mysql_configs", "", {});
        if (res && res.configs) {
          this.configs = res.configs;
        }
      } catch (e) {
        console.error("Error al obtener configuraciones MySQL:", e);
      } finally {
        this.isLoadingConfigs = false;
      }
    },
    async testConnection(cfg) {
      this.isTesting = true;
      try {
        const res = await this.store.callOdooSilent("test_mysql_connection", "", { id: cfg.id });
        if (res && res.success) {
          cfg.last_sync_status = `[TEST ÉXITO] ${res.message}`;
        } else if (res && res.message) {
          cfg.last_sync_status = `[TEST ERROR] ${res.message}`;
        }
      } catch (e) {
        cfg.last_sync_status = `[ERROR DE CONEXIÓN] ${e.message || e}`;
      } finally {
        this.isTesting = false;
      }
    },
    async saveConfig(cfg) {
      this.isSaving = true;
      try {
        const res = await this.store.callOdooSilent("save_mysql_config", "", { data: cfg });
        if (res && res.success) {
          await this.fetchConfigs();
        }
      } catch (e) {
        console.error("Error al guardar configuración MySQL:", e);
      } finally {
        this.isSaving = false;
      }
    },
    async syncSlaNow(cfg) {
      this.isSyncing = true;
      try {
        const res = await this.store.callOdooSilent("sync_mysql_sla", "", { id: cfg.id });
        if (res && res.success) {
          cfg.last_sync_status = `[SYNC ÉXITO] ${res.message}`;
          if (res.last_sync_date) cfg.last_sync_date = res.last_sync_date;
          await this.fetchConfigs();
        } else if (res && res.message) {
          cfg.last_sync_status = `[SYNC ERROR] ${res.message}`;
        }
      } catch (e) {
        cfg.last_sync_status = `[ERROR SYNC] ${e.message || e}`;
      } finally {
        this.isSyncing = false;
      }
    },
    getTerminalClass(statusText) {
      if (!statusText) return "";
      const s = statusText.toLowerCase();
      if (s.includes("éxito") || s.includes("exitosa") || s.includes("completada")) return "term-success";
      if (s.includes("error") || s.includes("fallo") || s.includes("denegado")) return "term-error";
      return "";
    }
  },
  mounted() {
    this.fetchConfigs();
  }
};
</script>

<style scoped>
.mysql-driver-view {
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
  margin-bottom: 20px;
  width: 100%;
}
.title-group {
  display: flex;
  align-items: center;
  gap: 12px;
}
.title-icon {
  font-size: 1.8rem;
  color: #0284c7;
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
.developer-badge {
  background: #1e293b;
  color: #38bdf8;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: 600;
  display: flex;
  align-items: center;
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

.config-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.03);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8f0;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.card-icon {
  font-size: 1.4rem;
  color: #0284c7;
}
.config-name {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 700;
  color: #0f172a;
}
.marketplace-pill {
  background: #e0f2fe;
  color: #0369a1;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
}

.header-actions {
  display: flex;
  gap: 8px;
}
.btn-primary-sm, .btn-secondary-sm, .btn-success-sm {
  border: none;
  padding: 7px 12px;
  border-radius: 6px;
  font-weight: 600;
  font-size: 0.8rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: opacity 0.2s;
}
.btn-primary-sm { background: #2563eb; color: #ffffff; }
.btn-secondary-sm { background: #64748b; color: #ffffff; }
.btn-success-sm { background: #16a34a; color: #ffffff; }
.btn-primary-sm:hover, .btn-secondary-sm:hover, .btn-success-sm:hover { opacity: 0.9; }

.form-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin-bottom: 18px;
}
.span-2 { grid-column: span 2; }

.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.form-group label {
  font-size: 0.8rem;
  font-weight: 600;
  color: #334155;
}
.custom-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 0.85rem;
  outline: none;
  background: #ffffff;
}
.custom-input:focus {
  border-color: #0284c7;
  box-shadow: 0 0 0 2px rgba(2, 132, 199, 0.15);
}

.password-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}
.btn-toggle-pass {
  position: absolute;
  right: 8px;
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
}

.status-terminal {
  background: #0f172a;
  color: #f8fafc;
  border-radius: 8px;
  overflow: hidden;
  font-family: 'Courier New', Courier, monospace;
}
.terminal-header {
  background: #1e293b;
  padding: 8px 14px;
  font-size: 0.75rem;
  font-weight: 600;
  color: #94a3b8;
  display: flex;
  justify-content: space-between;
}
.terminal-body {
  padding: 12px 14px;
  font-size: 0.8rem;
  min-height: 50px;
}
.terminal-body pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}
.term-success { color: #4ade80; }
.term-error { color: #f87171; }
</style>

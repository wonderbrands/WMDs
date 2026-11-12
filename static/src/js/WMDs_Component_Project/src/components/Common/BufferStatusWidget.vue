<template>
  <div v-if="isVisible" class="buffer-widget-container">
    <!-- Vista colapsada (Pill flotante) -->
    <div 
      v-if="!isExpanded" 
      class="buffer-pill"
      :class="{ 'has-error': stats.error > 0, 'is-syncing': stats.total_active > 0 }"
      @click="expandModal"
      title="Clic para ver detalles del buffer de escaneo"
    >
      <i v-if="stats.error > 0" class="fa fa-exclamation-triangle pill-icon error-icon"></i>
      <i v-else-if="stats.total_active > 0" class="fa fa-refresh fa-spin pill-icon sync-icon"></i>
      <i v-else class="fa fa-database pill-icon idle-icon"></i>

      <span class="pill-text">
        <template v-if="stats.error > 0">
          <strong>{{ stats.error }}</strong> error{{ stats.error > 1 ? 'es' : '' }} en buffer
        </template>
        <template v-else-if="stats.total_active > 0">
          Enviando <strong>{{ stats.total_active }}</strong> en trasfondo...
        </template>
        <template v-else>
          Buffer ({{ stats.synced }} sincronizados)
        </template>
      </span>
      <span class="pill-badge-arrow">▲</span>
    </div>

    <!-- Modal / Tarjeta flotante expandida -->
    <div v-else class="buffer-modal-card">
      <div class="modal-header">
        <div class="header-title">
          <i class="fa fa-database"></i>
          <span>Buffer de Escaneo Local</span>
        </div>
        <div class="header-actions">
          <button class="minimize-icon-btn" @click="minimizeModal" title="Minimizar modal">
            <i class="fa fa-chevron-down"></i>
          </button>
          <button class="close-btn" @click="minimizeModal" title="Cerrar">✕</button>
        </div>
      </div>

      <div class="modal-body">
        <!-- Indicador de estado -->
        <div class="status-banner" :class="{ 'banner-error': stats.error > 0, 'banner-active': stats.total_active > 0, 'banner-ok': stats.error === 0 && stats.total_active === 0 }">
          <template v-if="stats.error > 0">
            <i class="fa fa-exclamation-circle"></i>
            <span>Atención: Fallo en sincronización de escaneos.</span>
          </template>
          <template v-else-if="stats.total_active > 0">
            <i class="fa fa-refresh fa-spin"></i>
            <span>Sincronizando datos con el servidor en segundo plano...</span>
          </template>
          <template v-else>
            <i class="fa fa-check-circle"></i>
            <span>Todos los escaneos locales están sincronizados.</span>
          </template>
        </div>

        <!-- Métricas de la cola -->
        <div class="metrics-grid">
          <div class="metric-item">
            <span class="metric-label">En Cola</span>
            <span class="metric-value pending">{{ stats.pending }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">Enviando</span>
            <span class="metric-value processing">{{ stats.processing }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">Completados</span>
            <span class="metric-value synced">{{ stats.synced }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">Con Error</span>
            <span class="metric-value error">{{ stats.error }}</span>
          </div>
        </div>

        <!-- Caja de error y gestión con opciones de borrado -->
        <div v-if="stats.error > 0" class="error-detail-box">
          <div class="error-box-header">
            <div class="error-title-wrapper">
              <i class="fa fa-exclamation-triangle"></i>
              <strong>Errores en Buffer ({{ stats.error }}):</strong>
            </div>
            <div style="display: flex; gap: 6px;">
              <button 
                class="btn-mini-retry" 
                @click="handleManualRetry"
                :disabled="isRetrying"
                title="Reintentar escaneos con error"
                style="background: #2563eb; color: #fff; border: none; border-radius: 4px; padding: 4px 8px; font-size: 0.75rem; cursor: pointer;"
              >
                <i class="fa fa-repeat" :class="{ 'fa-spin': isRetrying }"></i> Reintentar
              </button>
              <button 
                class="btn-mini-danger" 
                @click="handleClearAllErrors"
                :disabled="isDeleting"
                title="Descartar errores del buffer local"
              >
                <i class="fa fa-trash"></i> Descartar errores
              </button>
            </div>
          </div>

          <!-- Barra de selección masiva -->
          <div class="bulk-select-bar" v-if="errorList.length > 0">
            <label class="select-all-label">
              <input 
                type="checkbox" 
                :checked="isAllSelected" 
                @change="toggleSelectAll" 
              />
              <span>Seleccionar todos ({{ errorList.length }})</span>
            </label>

            <button 
              v-if="selectedErrorIds.length > 0" 
              class="btn-delete-selected" 
              @click="handleDeleteSelectedErrors"
              :disabled="isDeleting"
            >
              <i class="fa fa-trash-o"></i> Borrar seleccionados ({{ selectedErrorIds.length }})
            </button>
          </div>

          <!-- Lista de errores desplazable con checkboxes y borrado individual -->
          <div class="error-items-scroll" v-if="errorList.length > 0">
            <div 
              v-for="errItem in errorList" 
              :key="errItem.id" 
              class="error-row-item"
              :class="{ 'is-selected': selectedErrorIds.includes(errItem.id) }"
            >
              <input 
                type="checkbox" 
                :value="errItem.id" 
                v-model="selectedErrorIds"
                class="error-checkbox" 
              />
              <div class="error-info-col">
                <div class="error-row-header">
                  <span class="error-barcode">{{ errItem.barcode }}</span>
                  <span class="error-type-tag">{{ errItem.type }}</span>
                  <span class="error-time-small">{{ formatTime(errItem.timestamp) }}</span>
                </div>
                <div class="error-msg-text">{{ errItem.errorMsg || 'Fallo desconocido' }}</div>
              </div>
              <button 
                class="btn-row-delete" 
                @click="handleDeleteSingleError(errItem.id, errItem.barcode)"
                :disabled="isDeleting"
                title="Eliminar este error del buffer"
              >
                <i class="fa fa-trash"></i>
              </button>
            </div>
          </div>

          <!-- Fallback si solo está el last_error antes de cargar la lista -->
          <div v-else-if="stats.last_error" class="error-code-snippet">
            <div><strong>Código:</strong> {{ stats.last_error.barcode }}</div>
            <div><strong>Tipo:</strong> {{ stats.last_error.type }}</div>
            <div><strong>Mensaje:</strong> {{ stats.last_error.errorMsg || 'Fallo desconocido' }}</div>
            <div class="error-time"><strong>Hora:</strong> {{ formatTime(stats.last_error.timestamp) }}</div>
          </div>

          <div class="error-box-actions">
            <button class="btn-copy" @click="copyLastError">
              <i class="fa fa-copy"></i> Copiar Reporte para Developer
            </button>
          </div>
        </div>

        <div class="auto-info-text">
          <i class="fa fa-info-circle"></i> Reintento automático cada 5 min. Purga de completados cada 10 min.
        </div>
      </div>

      <!-- Acciones de control manual -->
      <div class="modal-footer">
        <button 
          class="btn-action btn-retry" 
          @click="handleManualRetry" 
          :disabled="isRetrying"
          title="Reintentar inmediatamente los envíos fallidos o pendientes"
        >
          <i class="fa fa-repeat" :class="{ 'fa-spin': isRetrying }"></i>
          Reintentar
        </button>

        <button 
          class="btn-action btn-clear" 
          @click="handleManualClear" 
          :disabled="stats.synced === 0"
          title="Eliminar registros que ya fueron sincronizados con éxito"
        >
          <i class="fa fa-trash"></i>
          Borrar ({{ stats.synced }})
        </button>

        <button 
          class="btn-action btn-minimize" 
          @click="minimizeModal" 
          title="Minimizar modal a la esquina"
        >
          <i class="fa fa-chevron-down"></i>
          Minimizar
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import { scanQueueWorker } from "../../services/scanQueueWorker";
import { useGeneralStore } from "../../store/index";

export default {
  name: "BufferStatusWidget",
  data() {
    return {
      store: useGeneralStore(),
      isExpanded: false,
      isRetrying: false,
      isDeleting: false,
      userManuallyMinimized: false,
      errorList: [],
      selectedErrorIds: []
    };
  },
  computed: {
    stats() {
      return this.store.buffer_stats || {
        pending: 0,
        processing: 0,
        synced: 0,
        error: 0,
        total_active: 0,
        has_data: false,
        last_error: null
      };
    },
    isVisible() {
      return this.stats.has_data || this.stats.total_active > 0 || this.stats.error > 0 || this.stats.synced > 0;
    },
    isAllSelected() {
      return this.errorList.length > 0 && this.selectedErrorIds.length === this.errorList.length;
    }
  },
  mounted() {
    if (this.stats.error > 0) {
      if (!this.userManuallyMinimized) {
        this.isExpanded = true;
      }
      this.loadErrorList();
    }
    window.addEventListener('keydown', this.handleKeyDown);
  },
  beforeUnmount() {
    window.removeEventListener('keydown', this.handleKeyDown);
  },
  watch: {
    "stats.error"(newVal, oldVal) {
      if (newVal > oldVal && !this.userManuallyMinimized) {
        this.isExpanded = true;
      }
      this.loadErrorList();
    },
    isExpanded(newVal) {
      if (newVal && this.stats.error > 0) {
        this.loadErrorList();
      }
    }
  },
  methods: {
    handleKeyDown(e) {
      if (e.key === 'Escape' && this.isExpanded) {
        this.minimizeModal();
      }
    },
    expandModal() {
      this.isExpanded = true;
      this.userManuallyMinimized = false;
      if (this.stats.error > 0) {
        this.loadErrorList();
      }
    },
    minimizeModal() {
      this.isExpanded = false;
      this.userManuallyMinimized = true;
    },
    formatTime(ts) {
      if (!ts) return '';
      return new Date(ts).toLocaleTimeString();
    },
    async loadErrorList() {
      if (this.stats.error === 0) {
        this.errorList = [];
        this.selectedErrorIds = [];
        return;
      }
      try {
        const errors = await scanQueueWorker.getErrorScans();
        this.errorList = errors || [];
        const currentIds = new Set(this.errorList.map(e => e.id));
        this.selectedErrorIds = this.selectedErrorIds.filter(id => currentIds.has(id));
      } catch (err) {
        console.error("Error cargando lista de errores:", err);
      }
    },
    toggleSelectAll(e) {
      if (e.target.checked) {
        this.selectedErrorIds = this.errorList.map(item => item.id);
      } else {
        this.selectedErrorIds = [];
      }
    },
    async handleDeleteSingleError(id, barcode) {
      this.isDeleting = true;
      try {
        await scanQueueWorker.triggerDeleteErrorScan(id);
        await this.loadErrorList();
        if (this.store.toast) {
          this.store.toast.add({
            severity: 'info',
            summary: 'Error Eliminado',
            detail: `Se eliminó el error para ${barcode}.`,
            life: 2500
          });
        }
      } catch (err) {
        console.error("Error eliminando escaneo:", err);
      } finally {
        this.isDeleting = false;
      }
    },
    async handleDeleteSelectedErrors() {
      if (this.selectedErrorIds.length === 0) return;
      this.isDeleting = true;
      const count = this.selectedErrorIds.length;
      try {
        await scanQueueWorker.triggerDeleteSelectedErrors(this.selectedErrorIds);
        this.selectedErrorIds = [];
        await this.loadErrorList();
        if (this.store.toast) {
          this.store.toast.add({
            severity: 'success',
            summary: 'Errores Eliminados',
            detail: `Se eliminaron ${count} errores seleccionados del buffer.`,
            life: 3000
          });
        }
      } catch (err) {
        console.error("Error eliminando errores seleccionados:", err);
      } finally {
        this.isDeleting = false;
      }
    },
    async handleClearAllErrors() {
      if (this.stats.error === 0) return;
      if (!confirm(`¿Deseas eliminar los ${this.stats.error} errores del buffer local?`)) return;
      this.isDeleting = true;
      try {
        const count = await scanQueueWorker.triggerClearAllErrors();
        this.selectedErrorIds = [];
        await this.loadErrorList();
        if (this.store.toast) {
          this.store.toast.add({
            severity: 'success',
            summary: 'Buffer Limpio',
            detail: `Se eliminaron todos los errores (${count}) del buffer local.`,
            life: 3000
          });
        }
      } catch (err) {
        console.error("Error limpiando todos los errores:", err);
      } finally {
        this.isDeleting = false;
      }
    },
    async handleManualRetry() {
      this.isRetrying = true;
      try {
        await scanQueueWorker.triggerManualRetry();
        await this.loadErrorList();
        if (this.store.toast) {
          this.store.toast.add({
            severity: 'info',
            summary: 'Reintento Iniciado',
            detail: 'Procesando buffer de escaneo...',
            life: 3000
          });
        }
      } catch (err) {
        console.error("Error en reintento manual:", err);
      } finally {
        setTimeout(() => {
          this.isRetrying = false;
        }, 1000);
      }
    },
    async handleManualClear() {
      try {
        await scanQueueWorker.triggerManualClearSynced();
        if (this.store.toast) {
          this.store.toast.add({
            severity: 'success',
            summary: 'Buffer Limpio',
            detail: 'Se eliminaron los escaneos completados.',
            life: 3000
          });
        }
      } catch (err) {
        console.error("Error al limpiar completados:", err);
      }
    },
    async copyLastError() {
      if (!this.errorList || this.errorList.length === 0) {
        const err = this.stats.last_error;
        if (!err) return;
        const text = `[WMDS Buffer Error Report]\nCódigo: ${err.barcode}\nTipo: ${err.type}\nStatus: ${err.status}\nError: ${err.errorMsg || 'Sin mensaje'}\nHora: ${this.formatTime(err.timestamp)}\nPayload: ${JSON.stringify(err.payload || {})}`;
        try {
          await navigator.clipboard.writeText(text);
        } catch (e) {
          alert(text);
        }
      } else {
        const reportLines = this.errorList.map((err, i) => 
          `#${i+1} [${err.barcode}] (${err.type}): ${err.errorMsg || 'Sin mensaje'} - ${this.formatTime(err.timestamp)}`
        ).join('\n');
        const text = `[WMDS Buffer Report: ${this.errorList.length} Errores]\n` + reportLines;
        try {
          await navigator.clipboard.writeText(text);
        } catch (e) {
          alert(text);
        }
      }
      if (this.store.toast) {
        this.store.toast.add({
          severity: 'success',
          summary: 'Copiado',
          detail: 'Reporte de errores copiado al portapapeles para el desarrollador.',
          life: 3000
        });
      }
    }
  }
};
</script>

<style scoped>
.buffer-widget-container {
  position: fixed;
  bottom: 16px;
  left: 16px;
  z-index: 9500;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  user-select: none;
}

/* Pill flotante colapsada */
.buffer-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: #1e293b;
  color: #f8fafc;
  border-radius: 9999px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.25s ease;
  border: 1px solid rgba(255, 255, 255, 0.15);
}

.buffer-pill:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.45);
}

.buffer-pill.is-syncing {
  background: #0f172a;
  border-color: #38bdf8;
}

.buffer-pill.has-error {
  background: #7f1d1d;
  color: #fef2f2;
  border-color: #ef4444;
  animation: pulse-border 2s infinite;
}

@keyframes pulse-border {
  0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
  70% { box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }
  100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
}

.pill-icon {
  font-size: 14px;
}
.sync-icon {
  color: #38bdf8;
}
.error-icon {
  color: #fca5a5;
}
.idle-icon {
  color: #a3e635;
}
.pill-badge-arrow {
  font-size: 10px;
  opacity: 0.7;
  margin-left: 4px;
}

/* Modal flotante expandido */
.buffer-modal-card {
  width: 350px;
  max-width: 90vw;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
  border: 1px solid #e2e8f0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  animation: slide-up 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes slide-up {
  from {
    opacity: 0;
    transform: translateY(12px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #0f172a;
  color: #ffffff;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.minimize-icon-btn,
.close-btn {
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 13px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}
.minimize-icon-btn:hover,
.close-btn:hover {
  background: rgba(255, 255, 255, 0.15);
  color: #ffffff;
}

.modal-body {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 400px;
  overflow-y: auto;
}

.status-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
}
.banner-ok {
  background: #f0fdf4;
  color: #166534;
  border: 1px solid #bbf7d0;
}
.banner-active {
  background: #f0f9ff;
  color: #0369a1;
  border: 1px solid #bae6fd;
}
.banner-error {
  background: #fef2f2;
  color: #991b1b;
  border: 1px solid #fecaca;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  background: #f8fafc;
  padding: 8px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.metric-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.metric-label {
  font-size: 10px;
  color: #64748b;
  text-transform: uppercase;
  font-weight: 600;
}

.metric-value {
  font-size: 16px;
  font-weight: 700;
  margin-top: 2px;
}
.metric-value.pending { color: #d97706; }
.metric-value.processing { color: #0284c7; }
.metric-value.synced { color: #16a34a; }
.metric-value.error { color: #dc2626; }

/* Caja de error developer */
.error-detail-box {
  background: #fff1f2;
  border: 1px solid #fecdd3;
  border-radius: 8px;
  padding: 10px;
  font-size: 12px;
}

.error-box-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  color: #9f1239;
  margin-bottom: 6px;
}

.error-title-wrapper {
  display: flex;
  align-items: center;
  gap: 6px;
}

.btn-mini-danger {
  background: #e11d48;
  color: #ffffff;
  border: none;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  padding: 3px 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: background 0.15s ease;
}
.btn-mini-danger:hover:not(:disabled) {
  background: #be123c;
}
.btn-mini-danger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Barra de selección masiva */
.bulk-select-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 6px 0;
  padding: 4px 6px;
  background: #ffe4e6;
  border-radius: 6px;
  font-size: 11px;
}

.select-all-label {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: #9f1239;
  font-weight: 600;
  user-select: none;
}

.btn-delete-selected {
  background: #be123c;
  color: #ffffff;
  border: none;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  padding: 3px 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: background 0.15s ease;
}
.btn-delete-selected:hover:not(:disabled) {
  background: #9f1239;
}
.btn-delete-selected:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Scroll de lista de errores */
.error-items-scroll {
  max-height: 160px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 6px 0;
  padding-right: 2px;
}

.error-row-item {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #ffffff;
  border: 1px solid #fecdd3;
  border-radius: 6px;
  padding: 6px 8px;
  transition: all 0.15s ease;
}
.error-row-item:hover {
  border-color: #fb7185;
  background: #fff5f5;
}
.error-row-item.is-selected {
  background: #ffe4e6;
  border-color: #f43f5e;
}

.error-checkbox {
  width: 14px;
  height: 14px;
  cursor: pointer;
  accent-color: #be123c;
}

.error-info-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.error-row-header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.error-barcode {
  font-weight: 700;
  font-size: 11px;
  color: #0f172a;
}

.error-type-tag {
  background: #f1f5f9;
  color: #475569;
  font-size: 9px;
  font-weight: 600;
  padding: 1px 4px;
  border-radius: 3px;
}

.error-time-small {
  font-size: 9px;
  color: #94a3b8;
  margin-left: auto;
}

.error-msg-text {
  font-size: 10px;
  color: #b91c1c;
  line-height: 1.2;
  word-break: break-word;
}

.btn-row-delete {
  background: transparent;
  border: none;
  color: #94a3b8;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}
.btn-row-delete:hover:not(:disabled) {
  background: #fee2e2;
  color: #dc2626;
}
.btn-row-delete:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.developer-msg {
  color: #881337;
  font-size: 11px;
  margin: 0 0 6px 0;
  line-height: 1.4;
}

.error-code-snippet {
  background: #ffffff;
  border: 1px solid #fecdd3;
  border-radius: 6px;
  padding: 6px 8px;
  font-family: monospace;
  font-size: 11px;
  color: #334155;
  display: flex;
  flex-direction: column;
  gap: 2px;
  word-break: break-all;
}

.error-time {
  font-size: 10px;
  color: #94a3b8;
}

.btn-copy {
  margin-top: 8px;
  width: 100%;
  padding: 6px;
  background: #be123c;
  color: #ffffff;
  border: none;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.btn-copy:hover {
  background: #9f1239;
}

.auto-info-text {
  font-size: 10px;
  color: #64748b;
  text-align: center;
}

/* Footer / Botones */
.modal-footer {
  padding: 10px 14px;
  background: #f8fafc;
  border-top: 1px solid #e2e8f0;
  display: flex;
  gap: 6px;
}

.btn-action {
  flex: 1;
  padding: 8px 8px;
  border-radius: 6px;
  border: none;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  transition: background 0.15s ease;
  white-space: nowrap;
}

.btn-retry {
  background: #0284c7;
  color: #ffffff;
}
.btn-retry:hover:not(:disabled) {
  background: #0369a1;
}

.btn-clear {
  background: #e2e8f0;
  color: #334155;
}
.btn-clear:hover:not(:disabled) {
  background: #cbd5e1;
}

.btn-minimize {
  background: #f1f5f9;
  color: #64748b;
  border: 1px solid #cbd5e1;
}
.btn-minimize:hover {
  background: #e2e8f0;
  color: #1e293b;
}

.btn-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>

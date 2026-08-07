<template>
  <div class="location-unblocking-manager">
    <div class="title_section flex-between">
      <div>
        <h1>Desbloqueo de Ubicaciones</h1>
        <p>Busca posiciones bloqueadas y gestiona su desbloqueo (excepto Cuarentenas y Cíclicos).</p>
      </div>
      <Button label="Descargar Reporte CSV" icon="fa fa-download" @click="downloadCSV" severity="secondary" />
    </div>

    <div class="grid-layout">
      <!-- LEFT SECTION: Search & Selection -->
      <div class="card search-card">
        <h3>Buscador de Ubicaciones Bloqueadas</h3>
        
        <div class="filter-section">
          <div class="filter-group">
            <label class="filter-label">Pasillo (A - ZZ)</label>
            <div class="flex-row gap-small">
              <InputText v-model="filters.aisle_from" maxlength="2" @input="filters.aisle_from = filters.aisle_from.toUpperCase()" class="w-full p-inputtext-sm" />
              <InputText v-model="filters.aisle_to" maxlength="2" @input="filters.aisle_to = filters.aisle_to.toUpperCase()" class="w-full p-inputtext-sm" />
            </div>
          </div>
          <div class="filter-group">
            <label class="filter-label">Posición (1 - 99)</label>
            <div class="flex-row gap-small">
              <InputNumber v-model="filters.position_from" :min="1" :max="99" class="w-full p-inputnumber-sm" />
              <InputNumber v-model="filters.position_to" :min="1" :max="99" class="w-full p-inputnumber-sm" />
            </div>
          </div>
          <div class="filter-group">
            <label class="filter-label">Nivel (1 - 5)</label>
            <div class="flex-row gap-small">
              <InputNumber v-model="filters.level_from" :min="1" :max="5" class="w-full p-inputnumber-sm" />
              <InputNumber v-model="filters.level_to" :min="1" :max="5" class="w-full p-inputnumber-sm" />
            </div>
          </div>
          <div class="filter-group">
            <label class="filter-label">Frente (1 - 2)</label>
            <div class="flex-row gap-small">
              <InputNumber v-model="filters.front_from" :min="1" :max="2" class="w-full p-inputnumber-sm" />
              <InputNumber v-model="filters.front_to" :min="1" :max="2" class="w-full p-inputnumber-sm" />
            </div>
          </div>
          <div class="filter-actions mt-2">
            <Button label="Buscar" icon="fa fa-search" @click="performSearch" :loading="store.loading" class="w-full" />
          </div>
        </div>

        <DataTable 
          v-if="searchResults && searchResults.length > 0"
          v-model:selection="selectedLocations"
          :value="searchResults" 
          paginator 
          :rows="15" 
          class="p-datatable-sm custom-border mt-2" 
          dataKey="id"
          @row-click="onRowClick"
        >
          <Column selectionMode="multiple" headerStyle="width: 3rem"></Column>
          <Column field="complete_name" header="Ubicación">
            <template #body="slotProps">
              <span class="font-bold cursor-pointer">{{ slotProps.data.complete_name }}</span>
            </template>
          </Column>
          <Column header="Motivo" headerStyle="width: 12rem">
            <template #body="slotProps">
              <div class="flex flex-column gap-1">
                <span class="badge badge-danger">
                  {{ getReasonLabel(slotProps.data.block_reason_type) }}
                </span>
                <span class="text-xs text-muted block" v-if="slotProps.data.oversized_from">
                  Sobredimensión de: {{ slotProps.data.oversized_from }}
                </span>
              </div>
            </template>
          </Column>
        </DataTable>
        <div class="no-results" v-else-if="searched">
          No se encontraron ubicaciones bloqueadas para el rango especificado.
        </div>
      </div>

      <!-- RIGHT SECTION: Configuration & Management -->
      <div class="card detail-card" v-if="selectedLocationIds.length > 0 || activeLocation">
        <!-- MASSIVE UNBLOCKING VIEW -->
        <div v-if="selectedLocationIds.length > 0">
          <div class="flex-between header-border">
            <h2>Desbloqueo Masivo ({{ selectedLocationIds.length }} Ubicaciones)</h2>
            <Button icon="fa fa-times" severity="secondary" text rounded @click="clearSelection" />
          </div>

          <div class="location-details">
            <div class="selected-locations-preview">
              <span class="text-xs text-muted font-bold block mb-1">Ubicaciones a desbloquear:</span>
              <div class="tags-container">
                <span v-for="id in selectedLocationIds" :key="id" class="loc-tag">
                  {{ getLocNameById(id) }}
                  <i class="fa fa-times cursor-pointer remove-tag-icon" @click="removeSelectedId(id)"></i>
                </span>
              </div>
            </div>

            <div class="available-status-box">
              <h4 class="text-success mb-3"><i class="fa fa-unlock"></i> Confirmar Desbloqueo Masivo</h4>
              <p class="text-sm text-muted">Se procederá a desbloquear y liberar todas las ubicaciones seleccionadas listadas arriba.</p>

              <div class="action-btn-row">
                <Button 
                  label="Desbloquear Posiciones Seleccionadas" 
                  icon="fa fa-unlock" 
                  severity="success" 
                  class="w-full mt-4" 
                  @click="unblockLocation" 
                  :loading="store.loading" 
                />
              </div>
            </div>
          </div>
        </div>

        <!-- ORIGINAL SINGLE LOCATION UNBLOCK VIEW -->
        <div v-else-if="activeLocation">
          <div class="flex-between header-border">
            <h2>Detalles de la Posición: {{ activeLocation.name }}</h2>
            <Button icon="fa fa-times" severity="secondary" text rounded @click="activeLocation = null" />
          </div>

          <div class="location-details">
            <p><strong>Ubicación Completa:</strong> {{ activeLocation.complete_name }}</p>
            
            <div class="blocked-status-box">
              <div class="status-header">
                <i class="fa fa-lock status-icon"></i>
                <div>
                  <h4 class="text-danger">Ubicación actualmente bloqueada</h4>
                  <p class="status-meta" v-if="activeLocation.block_user || activeLocation.block_date">
                    Bloqueada <span v-if="activeLocation.block_user">por <strong>{{ activeLocation.block_user }}</strong></span> <span v-if="activeLocation.block_date">el {{ activeLocation.block_date }}</span>
                  </p>
                </div>
              </div>

              <div class="details-grid">
                <div><strong>Tipo de bloqueo:</strong> {{ getReasonLabel(activeLocation.block_reason_type) }}</div>
                <div><strong>Comentario:</strong> {{ activeLocation.block_reason || '-' }}</div>
                <div v-if="activeLocation.block_expiration_date">
                  <strong>Fecha Expiración:</strong> {{ activeLocation.block_expiration_date }}
                  <span v-if="activeLocation.is_block_expired" class="text-danger font-bold"> (VENCIDO)</span>
                </div>
                <div v-if="activeLocation.oversized_from">
                  <strong>Sobredimensionada desde:</strong> {{ activeLocation.oversized_from }}
                </div>
              </div>

              <div class="action-btn-row">
                <Button 
                  label="Desbloquear Posición" 
                  icon="fa fa-unlock" 
                  severity="success" 
                  class="w-full mt-3" 
                  @click="unblockLocation" 
                  :loading="store.loading" 
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="card detail-card flex-center text-muted" v-else>
        <div class="text-center">
          <i class="fa fa-unlock select-prompt-icon"></i>
          <h3>Selecciona una ubicación bloqueada</h3>
          <p>Haz clic en una de las posiciones de la lista para ver sus detalles y proceder a su desbloqueo.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { useGeneralStore } from "../../store/index";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import InputNumber from "primevue/inputnumber";
import DataTable from "primevue/datatable";
import Column from "primevue/column";

export default {
  name: "LocationUnblocking",
  components: {
    Button,
    InputText,
    InputNumber,
    DataTable,
    Column
  },
  data() {
    return {
      store: useGeneralStore(),
      filters: {
        aisle_from: "A",
        aisle_to: "Z",
        position_from: 1,
        position_to: 99,
        level_from: 1,
        level_to: 5,
        front_from: 1,
        front_to: 2
      },
      searchResults: [],
      searched: false,
      activeLocation: null,
      selectedLocations: [],
      selectedLocationIds: [],
      reasonOptions: [
        { label: "No Apta", value: "no_apto" },
        { label: "Dañada", value: "danado" },
        { label: "Onsite", value: "onsite" },
        { label: "Sobredimensionada", value: "sobredimensionada" },
        { label: "Dupla", value: "dupla" },
        { label: "Materiales", value: "materiales" }
      ]
    };
  },
  watch: {
    selectedLocations(newVal) {
      this.selectedLocationIds = newVal.map(loc => loc.id);
    }
  },
  methods: {
    getReasonLabel(val) {
      const match = this.reasonOptions.find(opt => opt.value === val);
      if (match) return match.label;
      if (val === 'ciclico') return 'Cíclico';
      if (val === 'cuarentena') return 'Cuarentena';
      return val || '';
    },
    async performSearch() {
      const res = await this.store.callOdoo("location_blocking_search", "", {
        ...this.filters,
        only_blocked: true
      });

      if (res && !res.error) {
        // Filter out quarantine and cyclic locations
        this.searchResults = res.filter(loc => {
          const isQuarantine = (loc.complete_name && loc.complete_name.toLowerCase().includes('cuarentena')) ||
                               (loc.name && loc.name.toLowerCase().includes('cuarentena')) ||
                               loc.block_reason_type === 'cuarentena';
          const isCyclic = loc.block_reason_type === 'ciclico';
          return loc.is_blocked && !isQuarantine && !isCyclic;
        });
        this.searched = true;
        this.clearSelection();
      }
    },
    selectLocation(loc) {
      this.activeLocation = loc;
      this.selectedLocations = [];
      this.selectedLocationIds = [];
    },
    onRowClick(event) {
      this.selectLocation(event.data);
    },
    getLocNameById(id) {
      const loc = this.searchResults.find(l => l.id === id);
      return loc ? loc.name : '';
    },
    removeSelectedId(id) {
      this.selectedLocations = this.selectedLocations.filter(loc => loc.id !== id);
      this.selectedLocationIds = this.selectedLocationIds.filter(x => x !== id);
    },
    clearSelection() {
      this.selectedLocations = [];
      this.selectedLocationIds = [];
    },
    async unblockLocation() {
      if (this.selectedLocationIds.length > 0) {
        // Massive unblocking
        this.store.loading = true;
        let successCount = 0;
        let failCount = 0;
        for (const locId of this.selectedLocationIds) {
          const res = await this.store.callOdoo("location_blocking_unblock", "", {
            location_id: locId
          });
          if (res && !res.error && res.status === 'ok') {
            successCount++;
          } else {
            failCount++;
          }
        }
        this.store.loading = false;
        
        if (successCount > 0) {
          this.store.toast.add({
            severity: "success",
            summary: "Desbloqueo Completado",
            detail: `${successCount} posiciones liberadas correctamente.` + (failCount > 0 ? ` ${failCount} fallaron.` : ''),
            life: 3000
          });
        } else if (failCount > 0) {
          this.store.toast.add({
            severity: "error",
            summary: "Error al Desbloquear",
            detail: "No se pudieron liberar las posiciones seleccionadas.",
            life: 5000
          });
        }
        this.clearSelection();
        await this.performSearch();
      } else if (this.activeLocation) {
        // Single unblocking
        const isQuarantine = (this.activeLocation.complete_name && this.activeLocation.complete_name.toLowerCase().includes('cuarentena')) ||
                             (this.activeLocation.name && this.activeLocation.name.toLowerCase().includes('cuarentena')) ||
                             this.activeLocation.block_reason_type === 'cuarentena';
        const isCyclic = this.activeLocation.block_reason_type === 'ciclico';

        if (isQuarantine || isCyclic) {
          this.store.toast.add({
            severity: "error",
            summary: "Acción no permitida",
            detail: "No se permite desbloquear ubicaciones de cuarentena o cíclicas desde esta pantalla.",
            life: 5000
          });
          return;
        }
        
        const res = await this.store.callOdoo("location_blocking_unblock", "", {
          location_id: this.activeLocation.id
        });

        if (res && !res.error && res.status === 'ok') {
          this.store.toast.add({
            severity: "success",
            summary: "Desbloqueo Completado",
            detail: "La posición ha sido liberada correctamente.",
            life: 3000
          });
          this.activeLocation = null;
          await this.performSearch();
        } else if (res && res.message) {
          this.store.toast.add({
            severity: "error",
            summary: "Error al Desbloquear",
            detail: res.message,
            life: 5000
          });
        }
      }
    },
    downloadCSV() {
      window.open('/web/blocked_locations_csv', '_blank');
    }
  }
};
</script>

<style scoped>
.location-unblocking-manager {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.title_section {
  margin-bottom: 1.5rem;
}

.title_section h1 {
  font-size: 1.8rem;
  color: #111827;
  font-weight: 700;
  margin: 0;
}

.title_section p {
  color: #6b7280;
  margin-top: 0.25rem;
}

.grid-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  flex-grow: 1;
  min-height: 0;
}

.card {
  background: white;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.search-card {
  overflow-y: auto;
}

.detail-card {
  overflow-y: auto;
}

.flex-between {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.flex-center {
  display: flex;
  justify-content: center;
  align-items: center;
}

.header-border {
  border-bottom: 1px solid #f3f4f6;
  padding-bottom: 0.75rem;
  margin-bottom: 1.25rem;
}

.filter-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 1rem;
  margin-bottom: 1.25rem;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.filter-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: #374151;
}

.flex-row {
  display: flex;
  gap: 0.5rem;
  width: 100%;
}

.gap-small {
  gap: 0.5rem;
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  overflow-y: auto;
  flex-grow: 1;
}

.result-item {
  border: 1px solid #f3f4f6;
  background-color: #f9fafb;
  border-radius: 8px;
  padding: 0.75rem 1rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.result-item:hover {
  background-color: #f3f4f6;
  border-color: #d1d5db;
}

.active-item {
  background-color: #fef9c3 !important;
  border-color: #facc15 !important;
}

.blocked-item {
  border-left: 4px solid #ef4444;
}

.loc-subinfo {
  font-size: 0.8rem;
  color: #6b7280;
  margin-top: 0.25rem;
}

.badge {
  display: inline-block;
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 4px;
}

.badge-danger {
  background-color: #fee2e2;
  color: #991b1b;
}

.no-results {
  text-align: center;
  color: #9ca3af;
  margin-top: 2rem;
}

.select-prompt-icon {
  font-size: 3rem;
  color: #d1d5db;
  margin-bottom: 1rem;
}

.location-details {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.blocked-status-box {
  background-color: #fff5f5;
  border: 1px solid #fee2e2;
  border-radius: 8px;
  padding: 1.25rem;
  margin-top: 0.5rem;
}

.status-header {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  margin-bottom: 1rem;
}

.status-icon {
  font-size: 1.5rem;
  color: #ef4444;
  margin-top: 0.15rem;
}

.status-meta {
  font-size: 0.85rem;
  color: #6b7280;
  margin: 0;
}

.details-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.5rem;
  font-size: 0.9rem;
  color: #374151;
  background: white;
  padding: 0.75rem;
  border-radius: 6px;
  border: 1px solid #f3f4f6;
}

.action-btn-row {
  margin-top: 1rem;
}

.w-full {
  width: 100%;
}

.mt-2 {
  margin-top: 0.5rem;
}

.mt-3 {
  margin-top: 0.75rem;
}

.text-danger {
  color: #dc2626;
}

.font-bold {
  font-weight: 700;
}

/* Estilos para desbloqueo masivo */
.selected-locations-preview {
  background-color: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 0.75rem;
  margin-bottom: 1rem;
}

.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.loc-tag {
  background-color: #eff6ff;
  color: #1e40af;
  border: 1px solid #bfdbfe;
  padding: 0.25rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.8rem;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.remove-tag-icon {
  font-size: 0.75rem;
  opacity: 0.6;
}

.remove-tag-icon:hover {
  opacity: 1;
}

.available-status-box {
  background-color: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
  padding: 1.25rem;
  margin-top: 0.5rem;
}

.text-success {
  color: #16a34a;
}

@media screen and (max-width: 768px) {
  .grid-layout {
    grid-template-columns: 1fr;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    overflow-y: auto;
    height: auto;
  }
  
  .card {
    padding: 1rem;
    height: auto;
    max-height: none;
    overflow-y: visible;
  }
  
  .title_section {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.75rem;
  }
  
  .title_section button {
    width: 100%;
  }

  .flex-row {
    flex-wrap: wrap;
  }
}
</style>

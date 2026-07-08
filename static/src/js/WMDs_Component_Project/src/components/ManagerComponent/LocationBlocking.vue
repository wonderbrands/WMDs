<template>
  <div class="location-blocking-manager">
    <div class="title_section flex-between">
      <div>
        <h1>Bloqueo de Ubicaciones</h1>
        <p>Busca posiciones y gestiona sus estados de bloqueo, motivos y adyacencias.</p>
      </div>
      <Button label="Descargar Reporte CSV" icon="fa fa-download" @click="downloadCSV" severity="secondary" />
    </div>

    <div class="grid-layout">
      <!-- LEFT SECTION: Search & Selection -->
      <div class="card search-card">
        <h3>Buscador de Ubicaciones</h3>
        
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
          <div class="filter-group">
            <label class="filter-label">Mostrar:</label>
            <Select 
              v-model="showFilterType" 
              :options="showFilterOptions" 
              optionLabel="label" 
              optionValue="value" 
              class="w-full p-select-sm" 
            />
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
          :rowSelectable="canSelectRow"
        >
          <Column selectionMode="multiple" headerStyle="width: 3rem"></Column>
          <Column field="complete_name" header="Ubicación">
            <template #body="slotProps">
              <span class="font-bold cursor-pointer">{{ slotProps.data.complete_name }}</span>
            </template>
          </Column>
          <Column header="Estado" headerStyle="width: 8rem">
            <template #body="slotProps">
              <span 
                v-if="isLocationAvailableForBlocking(slotProps.data) && isLocationEmpty(slotProps.data)"
                class="badge badge-success"
              >
                Disponible
              </span>
              <span 
                v-else-if="isLocationAvailableForBlocking(slotProps.data) && !isLocationEmpty(slotProps.data)"
                class="badge badge-info"
                title="Contiene producto. Solo se puede usar como origen para bloqueo por sobredimensionado."
                style="cursor: help;"
              >
                Ocupada (Apta Sobredim.)
              </span>
              <span 
                v-else
                class="badge badge-danger"
                :title="'No disponible para bloqueo: ' + getNotAvailableReason(slotProps.data)"
                style="cursor: help;"
              >
                No disponible
              </span>
            </template>
          </Column>
        </DataTable>
        <div class="no-results" v-else-if="searched">
          No se encontraron ubicaciones para el rango especificado.
        </div>
      </div>

      <!-- RIGHT SECTION: Configuration & Management -->
      <div class="card detail-card" v-if="selectedLocationIds.length > 0 || activeLocation">
        
        <!-- MASSIVE BLOCKING VIEW -->
        <div v-if="selectedLocationIds.length > 0 && (!blockReasonType || blockReasonType !== 'sobredimensionada')">
          <div class="flex-between header-border">
            <h2>Bloqueo Masivo ({{ selectedLocationIds.length }} Ubicaciones)</h2>
            <Button icon="fa fa-times" severity="secondary" text rounded @click="clearSelection" />
          </div>

          <div class="location-details">
            <div class="selected-locations-preview">
              <span class="text-xs text-muted font-bold block mb-1">Ubicaciones a bloquear:</span>
              <div class="tags-container">
                <span v-for="id in selectedLocationIds" :key="id" class="loc-tag">
                  {{ getLocNameById(id) }}
                  <i class="fa fa-times cursor-pointer remove-tag-icon" @click="removeSelectedId(id)"></i>
                </span>
              </div>
            </div>

            <!-- ALERT IF MASSIVE BLOCKING IS DISABLED -->
            <div v-if="isMassiveBlockingDisabled" class="info-alert error-alert" style="margin-top: 1rem; margin-bottom: 0;">
              <i class="fa fa-exclamation-triangle"></i>
              <span>No se puede realizar el bloqueo masivo porque una o más de las ubicaciones seleccionadas contienen producto y solo pueden ser bloqueadas por sobredimensionamiento de forma individual.</span>
            </div>

            <div v-else class="available-status-box">
              <h4 class="text-success mb-3"><i class="fa fa-check-circle"></i> Configurar Bloqueo Masivo</h4>
              
              <div class="form-group">
                <label class="form-label">Motivo de Bloqueo:</label>
                <Select 
                  v-model="blockReasonType" 
                  :options="massiveReasonOptions" 
                  optionLabel="label" 
                  optionValue="value" 
                  class="w-full" 
                />
              </div>

              <div v-if="blockReasonType && blockReasonType !== 'sobredimensionada'">
                <div class="form-group">
                  <label class="form-label">Comentario / Motivo de bloqueo:</label>
                  <textarea 
                    v-model="comment" 
                    rows="3" 
                    class="p-inputtext p-component w-full" 
                    placeholder="Detalles sobre el bloqueo..."
                  ></textarea>
                </div>

                <div class="form-group">
                  <label class="form-label">Fecha de Expiración:</label>
                  <input 
                    type="date" 
                    v-model="expirationDate" 
                    class="p-inputtext p-component w-full" 
                  />
                </div>
              </div>

              <div class="action-btn-row">
                <Button 
                  label="Confirmar Bloqueo de Posiciones" 
                  icon="fa fa-lock" 
                  severity="danger" 
                  class="w-full mt-4" 
                  @click="blockLocation" 
                  :disabled="!blockReasonType"
                  :loading="store.loading" 
                />
              </div>
            </div>
          </div>
        </div>

        <!-- ERROR STATE: SOBREDIMENSIONADO WITH MULTIPLE SELECTED -->
        <div v-else-if="selectedLocationIds.length > 0 && blockReasonType === 'sobredimensionada'">
          <div class="flex-between header-border">
            <h2>Bloqueo por Sobredimensionado</h2>
            <Button icon="fa fa-times" severity="secondary" text rounded @click="clearSelection" />
          </div>
          <div class="location-details">
            <div class="info-alert error-alert">
              <i class="fa fa-exclamation-triangle"></i>
              <span>El bloqueo por sobredimensionado debe aplicarse a una única ubicación de origen para poder calcular sus adyacencias. Por favor, selecciona solo una ubicación o cambia el motivo de bloqueo.</span>
            </div>
            
            <div class="form-group mt-3">
              <label class="form-label">Cambiar Motivo de Bloqueo:</label>
              <Select 
                v-model="blockReasonType" 
                :options="reasonOptions" 
                optionLabel="label" 
                optionValue="value" 
                class="w-full" 
              />
            </div>
          </div>
        </div>

        <!-- ORIGINAL SINGLE LOCATION BLOCK VIEW -->
        <div v-else-if="activeLocation">
          <div class="flex-between header-border">
            <h2>Detalles de la Posición: {{ activeLocation.name }}</h2>
            <Button icon="fa fa-times" severity="secondary" text rounded @click="activeLocation = null" />
          </div>

          <div class="location-details">
            <p><strong>Ubicación Completa:</strong> {{ activeLocation.complete_name }}</p>
            
            <!-- STATE 1: ALREADY BLOCKED -->
            <div v-if="activeLocation.is_blocked" class="blocked-status-box">
              <div class="status-header">
                <i class="fa fa-lock status-icon"></i>
                <div>
                  <h4 class="text-danger">Ubicación actualmente bloqueada</h4>
                  <p class="status-meta">
                    Bloqueada por <strong>{{ activeLocation.block_user }}</strong> el {{ activeLocation.block_date }}
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

            <!-- STATE 2: AVAILABLE (ALLOW BLOCKING) -->
            <div v-else-if="isLocationAvailableForBlocking(activeLocation)" class="available-status-box">
              <h4 class="text-success mb-3"><i class="fa fa-check-circle"></i> Ubicación disponible para bloqueo</h4>
              
              <div class="form-group">
                <label class="form-label">Motivo de Bloqueo:</label>
                <Select 
                  v-model="blockReasonType" 
                  :options="availableReasonOptions" 
                  optionLabel="label" 
                  optionValue="value" 
                  class="w-full" 
                />
              </div>

              <!-- Fields for standard blocks -->
              <div v-if="blockReasonType && blockReasonType !== 'sobredimensionada'">
                <div class="form-group">
                  <label class="form-label">Comentario / Motivo de bloqueo:</label>
                  <textarea 
                    v-model="comment" 
                    rows="3" 
                    class="p-inputtext p-component w-full" 
                    placeholder="Detalles sobre el bloqueo de la posición..."
                  ></textarea>
                </div>

                <div class="form-group">
                  <label class="form-label">Fecha de Expiración:</label>
                  <input 
                    type="date" 
                    v-model="expirationDate" 
                    class="p-inputtext p-component w-full" 
                  />
                </div>
              </div>

              <!-- Fields for oversized blocks (suggest adjacencies) -->
              <div v-else-if="blockReasonType === 'sobredimensionada'" class="oversized-section">
                <div class="info-alert">
                  <i class="fa fa-info-circle"></i>
                  <span>El bloqueo por sobredimensionado marcará esta posición como el origen del bloqueo y te permite bloquear sus adyacencias inmediatas.</span>
                </div>

                <div class="adjacency-container">
                  <div class="flex-between mb-2">
                    <h4 class="text-dark">Sugerencias de Adyacencia:</h4>
                    <div class="flex gap-small">
                      <Button 
                        v-if="adjacencies && adjacencies.length > 0"
                        label="Seleccionar Todos" 
                        icon="fa fa-check-square-o" 
                        severity="secondary" 
                        text 
                        size="small" 
                        @click="selectAllAdjacents" 
                      />
                      <Button 
                        label="Actualizar" 
                        icon="fa fa-refresh" 
                        severity="secondary" 
                        text 
                        size="small" 
                        @click="fetchAdjacencies" 
                        :loading="loadingAdjacencies"
                      />
                    </div>
                  </div>

                  <div v-if="loadingAdjacencies" class="loading-box">
                    <i class="fa fa-spinner fa-spin"></i> Buscando adyacencias disponibles...
                  </div>

                  <div v-else-if="adjacencies && adjacencies.length > 0" class="adjacency-list">
                    <div 
                      v-for="adj in adjacentsGrouped" 
                      :key="adj.id"
                      class="adjacency-item"
                      :class="{'opacity-50': adj.is_blocked || adj.has_product}"
                    >
                      <label class="flex items-center gap-small cursor-pointer w-full" :style="(adj.is_blocked || adj.has_product) ? 'cursor: not-allowed' : ''">
                        <Checkbox 
                          v-model="selectedAdjacents" 
                          :value="adj.id" 
                          :disabled="adj.is_blocked || adj.has_product"
                        />
                        <div class="adj-info flex-grow">
                          <span class="font-bold">{{ adj.name }}</span>
                          <span class="adj-direction">({{ adj.directionLabel }})</span>
                          
                          <!-- Warn/Info box -->
                          <span v-if="adj.is_blocked" class="text-danger font-bold text-xs block">
                            <i class="fa fa-ban"></i> No disponible: Ya está bloqueada
                          </span>
                          <span v-else-if="adj.has_product" class="text-warning font-bold text-xs block">
                            <i class="fa fa-cubes"></i> No disponible: Contiene producto
                          </span>
                          <span v-else class="text-success font-bold text-xs block">
                            <i class="fa fa-check"></i> Disponible (vacía)
                          </span>
                        </div>
                      </label>
                    </div>
                  </div>

                  <div v-else class="no-adj-box">
                    No se encontraron ubicaciones adyacentes.
                  </div>

                  <!-- Custom Location Search to add manually -->
                  <div class="custom-location-addition mt-3 border-t pt-3">
                    <h4 class="text-dark font-bold mb-2">Agregar posiciones adicionales a bloquear:</h4>
                    <div class="flex gap-small">
                      <InputText 
                        v-model="customSearchTerm" 
                        placeholder="Buscar por código (ej. B-P04-F1-N2)..." 
                        class="flex-grow"
                        @keyup.enter="searchCustomLocation"
                      />
                      <Button label="Buscar" icon="fa fa-plus" @click="searchCustomLocation" severity="secondary" size="small" :loading="searchingCustom" />
                    </div>
                    
                    <!-- Custom Search Results dropdown -->
                    <div v-if="customSearchResults && customSearchResults.length > 0" class="custom-search-results-box mt-2">
                      <div 
                        v-for="cand in customSearchResults" 
                        :key="cand.id" 
                        class="custom-search-item"
                        @click="addCustomLocation(cand)"
                      >
                        <div class="flex-between">
                          <span class="font-bold">{{ cand.complete_name }}</span>
                          <span 
                            class="badge"
                            :class="cand.is_blocked ? 'badge-danger' : (cand.has_product ? 'badge-warn' : 'badge-success')"
                          >
                            {{ cand.is_blocked ? 'Bloqueada' : (cand.has_product ? 'Con producto' : 'Disponible') }}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div v-else-if="customSearched && customSearchResults.length === 0" class="text-muted text-xs mt-1">
                      No se encontraron ubicaciones disponibles.
                    </div>

                    <!-- Selected Custom Locations List -->
                    <div v-if="customSelectedLocations && customSelectedLocations.length > 0" class="custom-selected-list mt-3">
                      <h5 class="font-bold text-dark mb-2">Ubicaciones adicionales seleccionadas:</h5>
                      <div 
                        v-for="loc in customSelectedLocations" 
                        :key="loc.id"
                        class="custom-selected-item flex-between"
                      >
                        <span>{{ loc.complete_name }}</span>
                        <Button icon="fa fa-trash" severity="danger" text rounded size="small" @click="removeCustomLocation(loc.id)" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div class="action-btn-row">
                <Button 
                  label="Confirmar Bloqueo de Posición" 
                  icon="fa fa-lock" 
                  severity="danger" 
                  class="w-full mt-4" 
                  @click="blockLocation" 
                  :disabled="!blockReasonType"
                  :loading="store.loading" 
                />
              </div>
            </div>

            <!-- STATE 3: NOT AVAILABLE FOR BLOCKING (BUT NOT BLOCKED) -->
            <div v-else class="not-available-status-box">
              <h4 class="text-danger mb-3"><i class="fa fa-ban"></i> Ubicación no disponible para bloqueo</h4>
              <div class="info-alert error-alert" style="margin-bottom: 0;">
                <i class="fa fa-exclamation-triangle"></i>
                <span>Esta ubicación no puede ser bloqueada por la siguiente razón: <strong>{{ getNotAvailableReason(activeLocation) }}</strong>.</span>
              </div>
            </div>
          </div>
        </div>

      </div>

      <div class="card detail-card flex-center text-muted" v-else>
        <div class="text-center">
          <i class="fa fa-location-arrow select-prompt-icon"></i>
          <h3>Selecciona una ubicación</h3>
          <p>Usa los filtros de la izquierda para buscar ubicaciones, o selecciona varias con los checks para realizar un bloqueo masivo.</p>
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
import Select from "primevue/select";
import Checkbox from "primevue/checkbox";
import DataTable from "primevue/datatable";
import Column from "primevue/column";

export default {
  name: "LocationBlocking",
  components: {
    Button,
    InputText,
    InputNumber,
    Select,
    Checkbox,
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

      // Massive blocking fields
      selectedLocations: [],
      selectedLocationIds: [],
      selectAllSearch: false,

      // Block form fields
      blockReasonType: null,
      comment: "",
      expirationDate: "",
      
      // Adjacencies
      adjacencies: [],
      selectedAdjacents: [],
      loadingAdjacencies: false,

      // Manual/Custom addition for oversized
      customSearchTerm: "",
      customSearchResults: [],
      customSelectedLocations: [],
      searchingCustom: false,
      customSearched: false,

      // Reason Select Options
      reasonOptions: [
        { label: "No Apta", value: "no_apto" },
        { label: "Dañada", value: "danado" },
        { label: "Onsite", value: "onsite" },
        { label: "Sobredimensionada", value: "sobredimensionada" }
      ],
      showFilterType: 'available',
      showFilterOptions: [
        { label: "Disponibles para bloqueo", value: "available" },
        { label: "Todas las ubicaciones", value: "all" }
      ]
    };
  },
  computed: {
    massiveReasonOptions() {
      return this.reasonOptions.filter(opt => opt.value !== 'sobredimensionada');
    },
    availableReasonOptions() {
      if (this.activeLocation && (this.activeLocation.is_empty_location === false || this.activeLocation.has_product)) {
        return this.reasonOptions.filter(opt => opt.value === 'sobredimensionada');
      }
      return this.reasonOptions;
    },
    isMassiveBlockingDisabled() {
      if (this.selectedLocations.length === 0) return false;
      return this.selectedLocations.some(loc => loc.is_empty_location === false || loc.has_product);
    },
    adjacentsGrouped() {
      return this.adjacencies.map(adj => {
        let labels = [];
        
        // Build position label
        if (adj.pos_offset < 0) {
          labels.push(`Izquierda ${Math.abs(adj.pos_offset)}`);
        } else if (adj.pos_offset > 0) {
          labels.push(`Derecha ${Math.abs(adj.pos_offset)}`);
        }
        
        // Build frente label
        if (adj.frente_offset < 0) {
          labels.push("Detrás");
        } else if (adj.frente_offset > 0) {
          labels.push("En frente");
        }

        // Build nivel label
        if (adj.nivel_offset < 0) {
          labels.push(`Nivel inferior ${Math.abs(adj.nivel_offset)}`);
        } else if (adj.nivel_offset > 0) {
          labels.push(`Nivel superior ${Math.abs(adj.nivel_offset)}`);
        }

        return {
          ...adj,
          directionLabel: labels.join(", ") || "Adyacente"
        };
      });
    }
  },
  watch: {
    blockReasonType(newVal) {
      if (newVal === 'sobredimensionada') {
        this.fetchAdjacencies();
      } else {
        this.adjacencies = [];
        this.selectedAdjacents = [];
      }
    },
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
    isLocationAvailableForBlocking(loc) {
      const isQuarantine = (loc.complete_name && loc.complete_name.toLowerCase().includes('cuarentena')) ||
                           (loc.name && loc.name.toLowerCase().includes('cuarentena')) ||
                           loc.block_reason_type === 'cuarentena';
      return !loc.is_blocked && !isQuarantine;
    },
    isLocationEmpty(loc) {
      return loc.is_empty_location !== false;
    },
    getNotAvailableReason(loc) {
      const reasons = [];
      if (loc.is_blocked) {
        reasons.push("Ya está bloqueada");
      }
      const isQuarantine = (loc.complete_name && loc.complete_name.toLowerCase().includes('cuarentena')) ||
                           (loc.name && loc.name.toLowerCase().includes('cuarentena')) ||
                           loc.block_reason_type === 'cuarentena';
      if (isQuarantine) {
        reasons.push("Es de cuarentena");
      }
      return reasons.join(", ") || "No disponible";
    },
    canSelectRow(event) {
      const loc = event.data;
      return this.isLocationAvailableForBlocking(loc) && this.isLocationEmpty(loc);
    },
    async performSearch() {
      const res = await this.store.callOdoo("location_blocking_search", "", {
        ...this.filters,
        only_blocked: false
      });

      if (res && !res.error) {
        if (this.showFilterType === 'available') {
          this.searchResults = res.filter(loc => this.isLocationAvailableForBlocking(loc));
        } else {
          this.searchResults = res;
        }
        this.searched = true;
        this.clearSelection();
      }
    },
    selectLocation(loc) {
      this.activeLocation = loc;
      // Clear massive selection as we are selecting a single active location details
      this.selectedLocations = [];
      this.selectedLocationIds = [];
      this.selectAllSearch = false;

      // Reset form fields
      if (loc && (loc.is_empty_location === false || loc.has_product)) {
        this.blockReasonType = 'sobredimensionada';
      } else {
        this.blockReasonType = null;
      }
      this.comment = "";
      this.expirationDate = "";
      this.adjacencies = [];
      this.selectedAdjacents = [];
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
      if (this.selectedLocationIds.length === 0) {
        this.selectAllSearch = false;
      }
    },
    clearSelection() {
      this.selectedLocations = [];
      this.selectedLocationIds = [];
      this.selectAllSearch = false;
    },
    selectAllAdjacents() {
      const availableIds = this.adjacentsGrouped
        .filter(adj => !adj.is_blocked && !adj.has_product)
        .map(adj => adj.id);
      
      const merged = new Set([...this.selectedAdjacents, ...availableIds]);
      this.selectedAdjacents = Array.from(merged);
    },
    async fetchAdjacencies() {
      if (!this.activeLocation) return;
      this.loadingAdjacencies = true;
      try {
        const res = await this.store.callOdoo("location_blocking_get_adjacent", "", {
          location_id: this.activeLocation.id
        });
        if (res && !res.error) {
          this.adjacencies = res;
        }
      } finally {
        this.loadingAdjacencies = false;
      }
    },
    async searchCustomLocation() {
      if (!this.customSearchTerm.trim()) return;
      this.searchingCustom = true;
      this.customSearched = false;
      try {
        const res = await this.store.callOdoo("location_blocking_search", "", {
          term: this.customSearchTerm,
          only_blocked: false
        });
        if (res && !res.error) {
          this.customSearchResults = res.filter(loc => {
            const isQuarantine = (loc.complete_name && loc.complete_name.toLowerCase().includes('cuarentena')) ||
                                 (loc.name && loc.name.toLowerCase().includes('cuarentena')) ||
                                 loc.block_reason_type === 'cuarentena';
            const isEmpty = loc.is_empty_location !== false;
            return loc.id !== this.activeLocation.id && 
                   !loc.is_blocked &&
                   !isQuarantine &&
                   isEmpty &&
                   !this.selectedAdjacents.includes(loc.id) &&
                   !this.customSelectedLocations.some(l => l.id === loc.id);
          });
          this.customSearched = true;
        }
      } finally {
        this.searchingCustom = false;
      }
    },
    addCustomLocation(loc) {
      if (loc.is_blocked) {
        this.store.toast.add({
          severity: "error",
          summary: "Ubicación Bloqueada",
          detail: `La ubicación ${loc.name} ya está bloqueada y no se puede seleccionar.`,
          life: 4000
        });
        return;
      }
      if (loc.has_product || loc.is_empty_location === false) {
        this.store.toast.add({
          severity: "error",
          summary: "Ubicación con Producto",
          detail: `La ubicación ${loc.name} contiene producto. Debe vaciarla antes de bloquearla por sobredimensionado.`,
          life: 4000
        });
        return;
      }
      this.customSelectedLocations.push(loc);
      this.customSearchTerm = "";
      this.customSearchResults = [];
      this.customSearched = false;
    },
    removeCustomLocation(id) {
      this.customSelectedLocations = this.customSelectedLocations.filter(l => l.id !== id);
    },
    async blockLocation() {
      if (!this.activeLocation && this.selectedLocationIds.length === 0) return;
      if (!this.blockReasonType) return;
      
      if (this.selectedLocationIds.length > 0 && this.isMassiveBlockingDisabled) {
        this.store.toast.add({
          severity: "error",
          summary: "Error de Validación",
          detail: "No se puede realizar el bloqueo masivo porque una o más de las ubicaciones seleccionadas contienen producto.",
          life: 5000
        });
        return;
      }
      
      let locationIds = [];
      if (this.blockReasonType === 'sobredimensionada') {
        if (!this.activeLocation) return;
        const customIds = this.customSelectedLocations.map(l => l.id);
        locationIds = [...this.selectedAdjacents, ...customIds];
      } else {
        locationIds = this.selectedLocationIds.length > 0 ? this.selectedLocationIds : [this.activeLocation.id];
      }

      if (this.blockReasonType === 'sobredimensionada' && locationIds.length === 0) {
        this.store.toast.add({
          severity: "error",
          summary: "Faltan ubicaciones",
          detail: "Debes seleccionar al menos una ubicación adyacente o adicional para bloquear por sobredimensionado.",
          life: 4000
        });
        return;
      }

      const params = {
        location_ids: locationIds,
        block_reason_type: this.blockReasonType,
        comment: this.comment,
        ticket: null,
        expiration_date: this.expirationDate || null,
        original_location_id: this.blockReasonType === 'sobredimensionada' ? this.activeLocation.id : null
      };

      const res = await this.store.callOdoo("location_blocking_block", "", params);
      if (res && !res.error && res.status === 'ok') {
        this.store.toast.add({
          severity: "success",
          summary: "Bloqueo Exitoso",
          detail: "Las posiciones han sido bloqueadas correctamente.",
          life: 3000
        });
        this.clearSelection();
        this.activeLocation = null;
        await this.performSearch();
      } else if (res && res.message) {
        this.store.toast.add({
          severity: "error",
          summary: "Error de Validación",
          detail: res.message,
          life: 5000
        });
      }
    },
    async unblockLocation() {
      if (!this.activeLocation) return;
      
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
        await this.refreshActiveLocation();
        await this.performSearch();
      } else if (res && res.message) {
        this.store.toast.add({
          severity: "error",
          summary: "Error al Desbloquear",
          detail: res.message,
          life: 5000
        });
      }
    },
    async refreshActiveLocation() {
      if (!this.activeLocation) return;
      const res = await this.store.callOdoo("location_blocking_search", "", {
        term: this.activeLocation.complete_name,
        only_blocked: false
      });
      if (res && res.length > 0) {
        const match = res.find(l => l.id === this.activeLocation.id);
        if (match) {
          this.activeLocation = match;
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
.location-blocking-manager {
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

.badge-success {
  background-color: #d1fae5;
  color: #065f46;
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

.available-status-box {
  background-color: #f0fdf4;
  border: 1px solid #d1fae5;
  border-radius: 8px;
  padding: 1.25rem;
  margin-top: 0.5rem;
}

.not-available-status-box {
  background-color: #fffaf0;
  border: 1px solid #ffedd5;
  border-radius: 8px;
  padding: 1.25rem;
  margin-top: 0.5rem;
}

.form-group {
  margin-bottom: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.form-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: #374151;
}

.text-danger {
  color: #dc2626;
}

.text-success {
  color: #16a34a;
}

.text-dark {
  color: #1f2937;
  margin: 0;
}

.info-alert {
  background-color: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  padding: 0.75rem;
  font-size: 0.85rem;
  color: #1e40af;
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
  margin-bottom: 1.25rem;
}

.error-alert {
  background-color: #fff5f5;
  border-color: #fee2e2;
  color: #991b1b;
}

.adjacency-container {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 1rem;
}

.loading-box {
  text-align: center;
  color: #4b5563;
  padding: 1rem 0;
}

.adjacency-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 200px;
  overflow-y: auto;
  padding: 0.25rem;
}

.adjacency-item {
  border-bottom: 1px solid #f3f4f6;
  padding-bottom: 0.5rem;
  display: flex;
  align-items: center;
}

.adjacency-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.adj-direction {
  font-size: 0.8rem;
  color: #6b7280;
  margin-left: 0.5rem;
}

.no-adj-box {
  text-align: center;
  color: #9ca3af;
  padding: 1rem 0;
  font-size: 0.9rem;
}

.border-t {
  border-top: 1px solid #e5e7eb;
}
.pt-3 {
  padding-top: 0.75rem;
}
.mt-2 {
  margin-top: 0.5rem;
}
.mt-3 {
  margin-top: 0.75rem;
}
.mt-4 {
  margin-top: 1rem;
}
.block {
  display: block;
}
.text-xs {
  font-size: 0.75rem;
}
.opacity-50 {
  opacity: 0.65;
}
.text-warning {
  color: #d97706;
}
.badge-warn {
  background-color: #fef3c7;
  color: #92400e;
}
.custom-search-results-box {
  border: 1px solid #d1d5db;
  border-radius: 6px;
  max-height: 150px;
  overflow-y: auto;
  background: white;
}
.custom-search-item {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid #f3f4f6;
  cursor: pointer;
}
.custom-search-item:hover {
  background-color: #f9fafb;
}
.custom-search-item:last-child {
  border-bottom: none;
}
.custom-selected-list {
  background: #f9fafb;
  border: 1px dashed #d1d5db;
  border-radius: 8px;
  padding: 0.75rem;
}
.custom-selected-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #e5e7eb;
  padding: 0.25rem 0;
  font-size: 0.9rem;
}
.custom-selected-item:last-child {
  border-bottom: none;
}

/* Tag styles for massive blocking */
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
</style>

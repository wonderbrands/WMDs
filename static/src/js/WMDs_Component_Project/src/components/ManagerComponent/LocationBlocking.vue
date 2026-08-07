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
                v-else-if="slotProps.data.oversized_to"
                class="badge text-white"
                style="background-color: #805ad5; cursor: help;"
                :title="'Sobredimensionando a: ' + slotProps.data.oversized_to"
              >
                Sobredimensionando a...
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
        <div v-if="selectedLocationIds.length > 1 && (!blockReasonType || blockReasonType !== 'sobredimensionada')">
          <div class="flex-between header-border">
            <h2>Bloqueo Masivo ({{ selectedLocationIds.length }} Ubicaciones)</h2>
            <Button icon="fa fa-times" severity="secondary" text rounded @click="clearSelection" />
          </div>

          <div class="location-details">
            <div class="selected-locations-preview">
              <span class="text-xs text-muted font-bold block mb-1">Ubicaciones a bloquear:</span>
              <div class="tags-container">
                <span 
                  v-for="id in selectedLocationIds" 
                  :key="id" 
                  class="loc-tag"
                  :class="{'loc-tag-warning': !isLocationEmptyById(id)}"
                  :title="!isLocationEmptyById(id) ? 'Esta ubicación contiene producto' : ''"
                >
                  {{ getLocNameById(id) }}
                  <span v-if="!isLocationEmptyById(id)" class="text-xs font-bold" style="margin-left: 2px;">(Con producto)</span>
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
        <div v-else-if="selectedLocationIds.length > 1 && blockReasonType === 'sobredimensionada'">
          <div class="flex-between header-border">
            <h2>Bloqueo por Sobredimensionado</h2>
            <Button icon="fa fa-times" severity="secondary" text rounded @click="clearSelection" />
          </div>
          <div class="location-details">
            <div class="selected-locations-preview">
              <span class="text-xs text-muted font-bold block mb-1">Ubicaciones a bloquear:</span>
              <div class="tags-container">
                <span 
                  v-for="id in selectedLocationIds" 
                  :key="id" 
                  class="loc-tag"
                  :class="{'loc-tag-warning': !isLocationEmptyById(id)}"
                  :title="!isLocationEmptyById(id) ? 'Esta ubicación contiene producto' : ''"
                >
                  {{ getLocNameById(id) }}
                  <span v-if="!isLocationEmptyById(id)" class="text-xs font-bold" style="margin-left: 2px;">(Con producto)</span>
                  <i class="fa fa-times cursor-pointer remove-tag-icon" @click="removeSelectedId(id)"></i>
                </span>
              </div>
            </div>

            <div class="info-alert error-alert mt-3">
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
        <div v-else-if="selectedLocationIds.length === 1 || activeLocation">
          <div class="flex-between header-border">
            <h2>Detalles de la Posición: {{ activeLocation.name }}</h2>
            <Button icon="fa fa-times" severity="secondary" text rounded @click="clearSelection(); activeLocation = null" />
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

            <!-- STATE 4: CURRENTLY OVERSIZING OTHERS -->
            <div v-else-if="activeLocation.oversized_to" class="blocked-status-box" style="border-left-color: #805ad5;">
              <div class="status-header">
                <i class="fa fa-arrows-alt status-icon" style="color: #805ad5;"></i>
                <div>
                  <h4 style="color: #805ad5;">Posición Sobredimensionando a Otras</h4>
                  <p class="status-meta">
                    Esta ubicación está ocupando el espacio de: <strong>{{ activeLocation.oversized_to }}</strong>.
                  </p>
                </div>
              </div>

              <div class="info-alert error-alert" style="margin-top: 1rem; margin-bottom: 1rem;">
                <i class="fa fa-info-circle"></i>
                <span>Para poder aplicar un nuevo bloqueo o sobredimensionar a otras posiciones, debes primero liberar la sobredimensión actual.</span>
              </div>

              <div class="action-btn-row">
                <Button 
                  label="Cancelar Sobredimensión" 
                  icon="fa fa-unlock" 
                  class="w-full mt-2" 
                  style="background-color: #805ad5; border-color: #805ad5; color: white;"
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

              <!-- Fields for oversized blocks (suggest adjacencies in 3D grid) -->
              <div v-else-if="blockReasonType === 'sobredimensionada'" class="oversized-section">
                <div class="info-alert">
                  <i class="fa fa-info-circle"></i>
                  <span>El bloqueo por sobredimensionado marcará esta posición como el origen del bloqueo y te permite seleccionar ubicaciones adyacentes en la cuadrícula 3D para bloquearlas.</span>
                </div>

                <div class="adjacency-container">
                  <div class="flex-between mb-2 flex-wrap gap-small">
                    <h4 class="text-dark font-bold">Sugerencias de Adyacencia:</h4>
                    <div class="flex gap-small flex-wrap">
                      <Button 
                        v-if="adjacencies && adjacencies.length > 0"
                        :label="show3DSelector ? 'Ver Listado' : 'Ver Vista 3D'" 
                        :icon="show3DSelector ? 'fa fa-list' : 'fa fa-cubes'"
                        severity="secondary" 
                        text 
                        size="small" 
                        @click="show3DSelector = !show3DSelector" 
                      />
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
                    <i class="fa fa-spinner fa-spin"></i> Cargando adyacencias...
                  </div>

                  <div v-else-if="adjacencies && adjacencies.length > 0">
                    <!-- Vista 3D del Rack -->
                    <div v-if="show3DSelector" class="grid-3d-visualizer">
                      <!-- Preview Title and Expand Button -->
                      <div class="flex justify-between items-center mb-2">
                        <span class="text-xs text-muted font-bold">Vista Previa del Rack 3D:</span>
                        <Button 
                          label="Ampliar Vista 3D" 
                          icon="fa fa-expand" 
                          severity="primary" 
                          size="small" 
                          outlined
                          @click="show3DModal = true" 
                          title="Ver en pantalla completa"
                        />
                      </div>

                      <!-- 3D Scene (Compact preview, no dragging or scrolling, just a beautiful static preview) -->
                      <div class="rack-3d-scene" style="height: 240px;">
                        <div 
                          class="rack-3d-group"
                          style="transform: rotateX(60deg) rotateY(0deg) rotateZ(-45deg) scale3d(0.7, 0.7, 0.7);"
                        >
                          <div 
                            v-for="slot in grid3DSlots" 
                            :key="`preview-${slot.x}-${slot.y}-${slot.z}`" 
                            class="rack-cell-3d"
                            :style="{
                              transform: `translate3d(calc(${slot.x} * var(--cube-spacing-x)), calc(${slot.y} * var(--cube-spacing-y)), calc(${slot.z} * var(--cube-spacing-z)))`
                            }"
                          >
                            <div 
                              v-if="slot.loc" 
                              class="iso-cube-wrapper"
                              :class="getCubeClass(slot.loc)"
                              @click="show3DModal = true"
                            >
                              <div class="iso-cube">
                                <!-- No text label inside cubes in compact preview -->
                                <div class="cube-face top-face"></div>
                                <div class="cube-face front-face"></div>
                                <div class="cube-face side-face"></div>
                              </div>
                            </div>
                            <div v-else class="empty-iso-slot">
                              <div class="empty-slot-outline"></div>
                            </div>
                          </div>
                        </div>
                      </div>

                      <!-- Compact Legend -->
                      <div class="legend-box flex-wrap gap-small mt-3">
                        <span class="legend-item"><span class="dot source-dot"></span> Origen (Ocupado)</span>
                        <span class="legend-item"><span class="dot available-dot"></span> Disponible (ubicación vacía)</span>
                        <span class="legend-item"><span class="dot selected-dot"></span> Seleccionado</span>
                        <span class="legend-item"><span class="dot blocked-dot"></span> Bloqueado</span>
                        <span class="legend-item"><span class="dot product-dot"></span> Con Producto</span>
                      </div>
                    </div>

                    <!-- Vista de Listado para Adyacencias -->
                    <div v-else class="adjacency-list">
                      <div v-for="adj in adjacentsGrouped" :key="adj.id" class="adjacency-item flex justify-between items-center py-2 border-b">
                        <div class="flex items-center gap-small">
                          <Checkbox 
                            :binary="true"
                            :modelValue="selectedAdjacents.includes(adj.id)"
                            @update:modelValue="toggleAdjacentSelection(adj.id)"
                            :disabled="adj.is_blocked || adj.has_product"
                          />
                          <span :class="{'text-muted line-through font-normal': adj.is_blocked || adj.has_product, 'font-bold': !adj.is_blocked && !adj.has_product}">
                            {{ adj.name }}
                          </span>
                          <span class="adj-direction text-xs">({{ adj.directionLabel }})</span>
                        </div>
                        <div>
                          <span v-if="adj.is_blocked" class="badge badge-danger text-xs">Bloqueada</span>
                          <span v-else-if="adj.has_product" class="badge badge-warn text-xs">Con Producto</span>
                          <span v-else-if="selectedAdjacents.includes(adj.id)" class="badge badge-success text-xs">Seleccionada</span>
                          <span v-else class="badge badge-secondary text-xs">Disponible</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div v-else class="no-adj-box">
                    No se encontraron ubicaciones adyacentes.
                  </div>

                  <!-- Custom Location Search to add manually -->
                  <div class="custom-location-addition mt-3 border-t pt-3">
                    <h4 class="text-dark font-bold mb-2">Agregar posiciones adicionales a bloquear:</h4>
                    
                    <!-- Compact Range Filters Grid -->
                    <div class="custom-range-filters grid grid-cols-2 gap-small mb-3">
                      <div class="filter-group">
                        <label class="filter-label text-xs">Pasillo (De - A)</label>
                        <div class="flex gap-xs">
                          <InputText v-model="customFilters.aisle_from" maxlength="2" @input="customFilters.aisle_from = customFilters.aisle_from.toUpperCase()" class="w-full p-inputtext-sm" />
                          <InputText v-model="customFilters.aisle_to" maxlength="2" @input="customFilters.aisle_to = customFilters.aisle_to.toUpperCase()" class="w-full p-inputtext-sm" />
                        </div>
                      </div>
                      
                      <div class="filter-group">
                        <label class="filter-label text-xs">Posición (De - A)</label>
                        <div class="flex gap-xs">
                          <InputNumber v-model="customFilters.position_from" :min="1" :max="99" class="w-full p-inputnumber-sm" />
                          <InputNumber v-model="customFilters.position_to" :min="1" :max="99" class="w-full p-inputnumber-sm" />
                        </div>
                      </div>

                      <div class="filter-group">
                        <label class="filter-label text-xs">Nivel (De - A)</label>
                        <div class="flex gap-xs">
                          <InputNumber v-model="customFilters.level_from" :min="1" :max="5" class="w-full p-inputnumber-sm" />
                          <InputNumber v-model="customFilters.level_to" :min="1" :max="5" class="w-full p-inputnumber-sm" />
                        </div>
                      </div>

                      <div class="filter-group">
                        <label class="filter-label text-xs">Frente (De - A)</label>
                        <div class="flex gap-xs">
                          <InputNumber v-model="customFilters.front_from" :min="1" :max="2" class="w-full p-inputnumber-sm" />
                          <InputNumber v-model="customFilters.front_to" :min="1" :max="2" class="w-full p-inputnumber-sm" />
                        </div>
                      </div>
                    </div>

                    <div class="flex justify-end gap-small mb-3">
                      <Button 
                        label="Buscar por Rangos" 
                        icon="fa fa-search" 
                        @click="searchCustomLocation" 
                        severity="secondary" 
                        size="small" 
                        :loading="searchingCustom" 
                        class="w-full"
                      />
                    </div>
                    
                    <!-- Custom Search Results dropdown -->
                    <div v-if="customSearchResults && customSearchResults.length > 0" class="custom-search-results-box mt-2">
                      <div class="flex justify-between items-center mb-2 px-2">
                        <span class="text-xs text-muted font-bold">Resultados: {{ customSearchResults.length }} encontrados</span>
                        <Button 
                          label="Agregar todas" 
                          icon="fa fa-plus-square-o" 
                          severity="secondary" 
                          size="small" 
                          text 
                          @click="addAllCustomLocations" 
                        />
                      </div>
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
                      No se encontraron ubicaciones disponibles en este rango.
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

    <!-- Modal Dialog for 3D Visualizer -->
    <Dialog 
      v-model:visible="show3DModal" 
      modal 
      header="Visualizador de Rack 3D Interactiva" 
      :style="{ width: '90vw', maxWidth: '1100px' }"
      :breakpoints="{ '960px': '95vw' }"
    >
      <div class="modal-layout">
        <!-- Left: 3D Scene with full drag-zoom controls -->
        <div class="modal-scene-container">
          <!-- Controls -->
          <div class="flex justify-between items-center mb-3">
            <span class="text-xs text-muted font-bold">Usa el mouse para arrastrar/rotar y hacer scroll para hacer zoom:</span>
            <div class="flex gap-xs items-center">
              <Button icon="fa fa-search-plus" severity="secondary" text size="small" @click="zoomLevel = Math.min(2.5, zoomLevel + 0.1)" title="Acercar" />
              <Button icon="fa fa-search-minus" severity="secondary" text size="small" @click="zoomLevel = Math.max(0.5, zoomLevel - 0.1)" title="Alejar" />
              <span class="text-muted mx-1">|</span>
              <Button icon="fa fa-rotate-left" severity="secondary" text size="small" @click="rotationAngle -= 15" title="Rotar a la izquierda" />
              <Button icon="fa fa-undo" severity="secondary" text size="small" @click="resetView" title="Restablecer vista" />
              <Button icon="fa fa-rotate-right" severity="secondary" text size="small" @click="rotationAngle += 15" title="Rotar a la derecha" />
            </div>
          </div>

          <!-- 3D Scene (in-modal) -->
          <div 
            class="rack-3d-scene in-modal"
            @wheel.prevent="handleZoom"
            @mousedown="startDrag"
            @mousemove="onDrag"
            @mouseup="stopDrag"
            @mouseleave="stopDrag"
            @touchstart="startDragTouch"
            @touchmove="onDragTouch"
            @touchend="stopDrag"
          >
            <div 
              class="rack-3d-group in-modal"
              :style="{
                transform: `rotateX(${tiltAngle}deg) rotateY(0deg) rotateZ(${rotationAngle}deg) scale3d(${zoomLevel}, ${zoomLevel}, ${zoomLevel})`
              }"
            >
              <div 
                v-for="slot in grid3DSlots" 
                :key="`modal-${slot.x}-${slot.y}-${slot.z}`" 
                class="rack-cell-3d in-modal"
                :style="{
                  transform: `translate3d(calc(${slot.x} * var(--cube-spacing-x)), calc(${slot.y} * var(--cube-spacing-y)), calc(${slot.z} * var(--cube-spacing-z)))`
                }"
              >
                <div 
                  v-if="slot.loc" 
                  class="iso-cube-wrapper in-modal"
                  :class="getCubeClass(slot.loc)"
                  @click="onCubeClick(slot.loc)"
                  @mouseenter="hoveredLocation = slot.loc"
                  @mouseleave="hoveredLocation = null"
                >
                  <div class="iso-cube in-modal">
                    <div class="cube-face top-face in-modal">
                      <span class="cube-inner-label in-modal">{{ getShortName(slot.loc.name) }}</span>
                    </div>
                    <div class="cube-face front-face in-modal"></div>
                    <div class="cube-face side-face in-modal"></div>
                  </div>
                </div>
                <div v-else class="empty-iso-slot in-modal">
                  <div class="empty-slot-outline in-modal"></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Right: Sidebar details and selection status -->
        <div class="modal-sidebar-container">
          <div class="hover-info-panel p-3 border rounded bg-light">
            <h5 class="font-bold text-dark mb-2">Posición Apuntada:</h5>
            <div class="info-content min-height-80">
              <div v-if="hoveredLocation">
                <div class="text-sm font-bold">{{ hoveredLocation.complete_name }}</div>
                <div class="badge mt-1" :class="getBadgeClass(hoveredLocation)">
                  {{ getStatusText(hoveredLocation) }}
                </div>
              </div>
              <div v-else class="text-muted text-xs">Pasa el cursor sobre un cubo para ver los detalles.</div>
            </div>
          </div>

          <!-- Legend -->
          <div class="legend-panel p-3 border rounded bg-light mt-3">
            <h5 class="font-bold text-dark mb-2">Leyenda de Estados:</h5>
            <div class="flex-column gap-small">
              <div class="legend-item"><span class="dot source-dot"></span> Origen (Ocupado)</div>
              <div class="legend-item"><span class="dot available-dot"></span> Disponible (ubicación vacía)</div>
              <div class="legend-item"><span class="dot selected-dot"></span> Seleccionado para bloqueo</div>
              <div class="legend-item"><span class="dot blocked-dot"></span> Bloqueado</div>
              <div class="legend-item"><span class="dot product-dot"></span> Ocupada con producto</div>
            </div>
          </div>

          <!-- Selected Adjacents summary -->
          <div class="selection-summary-panel p-3 border rounded bg-light mt-3 flex-column">
            <h5 class="font-bold text-dark mb-2">Posiciones a bloquear ({{ selectedAdjacents.length }}):</h5>
            <div class="summary-list overflow-y-auto max-height-200">
              <div v-for="id in selectedAdjacents" :key="id" class="text-xs py-1 border-b flex-between">
                <span>{{ getLocNameById(id) }}</span>
                <Button icon="fa fa-times" severity="danger" text size="small" @click="toggleAdjacentSelection(id)" />
              </div>
              <div v-if="selectedAdjacents.length === 0" class="text-muted text-xs">Ninguna posición seleccionada. Haz clic en los cubos disponibles (grises) para agregarlas.</div>
            </div>
          </div>
        </div>
      </div>
    </Dialog>
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
import Dialog from "primevue/dialog";

export default {
  name: "LocationBlocking",
  components: {
    Button,
    InputText,
    InputNumber,
    Select,
    Checkbox,
    DataTable,
    Column,
    Dialog
  },
  data() {
    return {
      store: useGeneralStore(),
      show3DModal: false,
      isMobile: false,
      show3DSelector: true,
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
      hoveredLocation: null,
      rotationAngle: -45,
      tiltAngle: 60,
      zoomLevel: 1.2,
      isDragging: false,
      startX: 0,
      startY: 0,
      startAngle: 0,
      startTilt: 60,

      // Manual/Custom addition for oversized
      customFilters: {
        aisle_from: "A",
        aisle_to: "Z",
        position_from: 1,
        position_to: 99,
        level_from: 1,
        level_to: 5,
        front_from: 1,
        front_to: 2
      },
      customSearchResults: [],
      customSelectedLocations: [],
      searchingCustom: false,
      customSearched: false,

      // Reason Select Options
      reasonOptions: [
        { label: "No Apta", value: "no_apto" },
        { label: "Dañada", value: "danado" },
        { label: "Onsite", value: "onsite" },
        { label: "Sobredimensionada", value: "sobredimensionada" },
        { label: "Dupla", value: "dupla" },
        { label: "Materiales", value: "materiales" }
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
    },
    grid3DMap() {
      const map = {};
      for (let z = -1; z <= 1; z++) {
        map[z] = {};
        for (let y = 2; y >= -2; y--) {
          map[z][y] = {};
          for (let x = -2; x <= 2; x++) {
            map[z][y][x] = null;
          }
        }
      }
      if (this.activeLocation) {
        map[0][0][0] = {
          id: this.activeLocation.id,
          name: this.activeLocation.name,
          complete_name: this.activeLocation.complete_name,
          is_source: true,
          is_blocked: this.activeLocation.is_blocked,
          has_product: this.activeLocation.is_empty_location === false || this.activeLocation.has_product
        };
      }
      this.adjacencies.forEach(adj => {
        const x = adj.pos_offset;
        const y = adj.nivel_offset;
        const z = adj.frente_offset;
        if (x >= -2 && x <= 2 && y >= -2 && y <= 2 && z >= -1 && z <= 1) {
          map[z][y][x] = {
            ...adj,
            is_source: false
          };
        }
      });
      return map;
    },
    activeFrentes() {
      const frentes = [];
      const hasBack = this.adjacencies.some(adj => adj.frente_offset === -1);
      if (hasBack) {
        frentes.push({ label: "Frente Posterior (Detrás)", val: -1 });
      }
      frentes.push({ label: "Mismo Frente (Centro)", val: 0 });
      const hasFront = this.adjacencies.some(adj => adj.frente_offset === 1);
      if (hasFront) {
        frentes.push({ label: "Frente Anterior (Adelante)", val: 1 });
      }
      return frentes;
    },
    grid3DSlots() {
      const slots = [];
      const activeZOffsets = this.activeFrentes.map(f => f.val);
      const sortedYOffsets = [...activeZOffsets].sort((a, b) => a - b);
      
      for (let y of sortedYOffsets) {
        for (let x = -2; x <= 2; x++) {
          for (let z = -2; z <= 2; z++) {
            let loc = null;
            if (x === 0 && y === 0 && z === 0 && this.activeLocation) {
              loc = {
                id: this.activeLocation.id,
                name: this.activeLocation.name,
                complete_name: this.activeLocation.complete_name,
                is_source: true,
                is_blocked: this.activeLocation.is_blocked,
                has_product: this.activeLocation.is_empty_location === false || this.activeLocation.has_product
              };
            } else {
              const match = this.adjacencies.find(adj => adj.pos_offset === x && adj.frente_offset === y && adj.nivel_offset === z);
              if (match) {
                loc = {
                  ...match,
                  is_source: false
                };
              }
            }
            slots.push({
              x,
              y,
              z,
              loc
            });
          }
        }
      }
      return slots;
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
      if (newVal.length === 1) {
        const loc = newVal[0];
        if (!this.activeLocation || this.activeLocation.id !== loc.id) {
          this.activeLocation = loc;
          if (loc && (loc.is_empty_location === false || loc.has_product)) {
            this.blockReasonType = 'sobredimensionada';
          } else {
            this.blockReasonType = null;
          }
          this.comment = "";
          this.expirationDate = "";
          this.adjacencies = [];
          this.selectedAdjacents = [];
          this.customSelectedLocations = [];
          if (this.blockReasonType === 'sobredimensionada') {
            this.fetchAdjacencies();
          }
        }
      } else {
        this.activeLocation = null;
        if (this.blockReasonType === 'sobredimensionada') {
          this.blockReasonType = null;
        }
      }
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
      return !loc.is_blocked && !isQuarantine && !loc.oversized_to;
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
      if (loc.oversized_to) {
        reasons.push(`Sobredimensionando a ${loc.oversized_to}`);
      }
      return reasons.join(", ") || "No disponible";
    },
    canSelectRow(event) {
      const loc = event.data;
      return this.isLocationAvailableForBlocking(loc);
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
      const clickedLoc = event.data;
      if (clickedLoc.is_blocked) {
        this.selectedLocations = [];
        this.activeLocation = clickedLoc;
        return;
      }
      this.activeLocation = null;
      const index = this.selectedLocations.findIndex(loc => loc.id === clickedLoc.id);
      if (index > -1) {
        this.selectedLocations = this.selectedLocations.filter(loc => loc.id !== clickedLoc.id);
      } else {
        this.selectedLocations = [...this.selectedLocations, clickedLoc];
      }
    },
    getCubeClass(loc) {
      if (!loc) return '';
      if (loc.is_source) return 'source';
      if (loc.is_blocked) return 'blocked';
      if (loc.has_product) return 'has-product';
      const isSelected = this.selectedAdjacents.includes(loc.id);
      return isSelected ? 'available selected' : 'available';
    },
    onCubeClick(loc) {
      if (!loc || loc.is_source || loc.is_blocked || loc.has_product) return;
      const index = this.selectedAdjacents.indexOf(loc.id);
      if (index > -1) {
        this.selectedAdjacents.splice(index, 1);
      } else {
        this.selectedAdjacents.push(loc.id);
      }
    },
    getShortName(name) {
      if (!name) return '';
      const parts = name.split('-');
      if (parts.length === 4) {
        return `${parts[1]}-${parts[2]}-${parts[3]}`;
      }
      return name;
    },
    getBadgeClass(loc) {
      if (loc.is_source) return 'badge-info';
      if (loc.is_blocked) return 'badge-danger';
      if (loc.has_product) return 'badge-warn';
      const isSelected = this.selectedAdjacents.includes(loc.id);
      return isSelected ? 'badge-success' : 'badge-secondary';
    },
    getStatusText(loc) {
      if (loc.is_source) return 'Origen (Ocupada)';
      if (loc.is_blocked) return 'Bloqueada';
      if (loc.has_product) return 'Ocupada con producto';
      const isSelected = this.selectedAdjacents.includes(loc.id);
      return isSelected ? 'Seleccionada para bloqueo' : 'Disponible (ubicación vacía)';
    },
    getLocNameById(id) {
      if (this.activeLocation && this.activeLocation.id === id) {
        return this.activeLocation.name;
      }
      const locSearch = this.searchResults.find(l => l.id === id);
      if (locSearch) return locSearch.name;
      const locAdj = this.adjacencies.find(l => l.id === id);
      if (locAdj) return locAdj.name;
      const locCustom = this.customSelectedLocations.find(l => l.id === id);
      if (locCustom) return locCustom.name;
      return '';
    },
    isLocationEmptyById(id) {
      if (this.activeLocation && this.activeLocation.id === id) {
        return this.activeLocation.is_empty_location !== false;
      }
      const locSearch = this.searchResults.find(l => l.id === id);
      if (locSearch) return locSearch.is_empty_location !== false;
      const locAdj = this.adjacencies.find(l => l.id === id);
      if (locAdj) return locAdj.is_empty_location !== false;
      const locCustom = this.customSelectedLocations.find(l => l.id === id);
      if (locCustom) return locCustom.is_empty_location !== false;
      return true;
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
    handleZoom(event) {
      const zoomFactor = event.deltaY < 0 ? 0.08 : -0.08;
      this.zoomLevel = Math.min(Math.max(0.5, this.zoomLevel + zoomFactor), 2.5);
    },
    startDrag(event) {
      if (event.button !== 0) return;
      this.isDragging = true;
      this.startX = event.clientX;
      this.startY = event.clientY;
      this.startAngle = this.rotationAngle;
      this.startTilt = this.tiltAngle;
    },
    onDrag(event) {
      if (!this.isDragging) return;
      const deltaX = event.clientX - this.startX;
      const deltaY = event.clientY - this.startY;
      this.rotationAngle = this.startAngle + (deltaX * 0.6);
      this.tiltAngle = Math.min(Math.max(20, this.startTilt - (deltaY * 0.5)), 85);
    },
    stopDrag() {
      this.isDragging = false;
    },
    startDragTouch(event) {
      if (event.touches.length !== 1) return;
      this.isDragging = true;
      this.startX = event.touches[0].clientX;
      this.startY = event.touches[0].clientY;
      this.startAngle = this.rotationAngle;
      this.startTilt = this.tiltAngle;
    },
    onDragTouch(event) {
      if (!this.isDragging || event.touches.length !== 1) return;
      const deltaX = event.touches[0].clientX - this.startX;
      const deltaY = event.touches[0].clientY - this.startY;
      this.rotationAngle = this.startAngle + (deltaX * 0.6);
      this.tiltAngle = Math.min(Math.max(20, this.startTilt - (deltaY * 0.5)), 85);
    },
    resetView() {
      this.rotationAngle = -45;
      this.tiltAngle = 60;
      this.zoomLevel = 1.2;
    },
    toggleAdjacentSelection(id) {
      const index = this.selectedAdjacents.indexOf(id);
      if (index > -1) {
        this.selectedAdjacents.splice(index, 1);
      } else {
        this.selectedAdjacents.push(id);
      }
    },
    async searchCustomLocation() {
      this.searchingCustom = true;
      this.customSearched = false;
      try {
        const res = await this.store.callOdoo("location_blocking_search", "", {
          ...this.customFilters,
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
    addAllCustomLocations() {
      const validLocs = this.customSearchResults.filter(loc => {
        const isBlocked = loc.is_blocked;
        const hasProduct = loc.has_product || loc.is_empty_location === false;
        return !isBlocked && !hasProduct;
      });
      validLocs.forEach(loc => {
        if (!this.customSelectedLocations.some(l => l.id === loc.id)) {
          this.customSelectedLocations.push(loc);
        }
      });
      this.customSearchResults = [];
      this.customSearched = false;
      this.store.toast.add({
        severity: "success",
        summary: "Ubicaciones Agregadas",
        detail: `Se agregaron ${validLocs.length} posiciones adicionales válidas.`,
        life: 3000
      });
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
      this.customSearchResults = [];
      this.customSearched = false;
    },
    removeCustomLocation(id) {
      this.customSelectedLocations = this.customSelectedLocations.filter(l => l.id !== id);
    },
    async blockLocation() {
      if (!this.activeLocation && this.selectedLocationIds.length === 0) return;
      if (!this.blockReasonType) return;
      
      if (this.selectedLocationIds.length > 1 && this.isMassiveBlockingDisabled) {
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
    },
    checkMobile() {
      const wasMobile = this.isMobile;
      this.isMobile = window.innerWidth <= 768;
      if (wasMobile !== this.isMobile) {
        this.show3DSelector = !this.isMobile;
      }
    }
  },
  mounted() {
    this.isMobile = window.innerWidth <= 768;
    this.show3DSelector = !this.isMobile;
    window.addEventListener('resize', this.checkMobile);
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.checkMobile);
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
.loc-tag-warning {
  background-color: #fffbeb;
  color: #b45309;
  border: 1px solid #fde68a;
}
.remove-tag-icon {
  font-size: 0.75rem;
  opacity: 0.6;
}
.remove-tag-icon:hover {
  opacity: 1;
}

/* 3D Visualizer styles */
.grid-3d-visualizer {
  display: flex;
  flex-direction: column;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 1.25rem;
  margin-top: 1rem;
}

.rack-3d-scene {
  position: relative;
  width: 100%;
  height: 240px;
  perspective: 1200px;
  transform-style: preserve-3d;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
  background: radial-gradient(circle, rgba(248,250,252,1) 0%, rgba(226,232,240,0.3) 100%);
  border-radius: 12px;
  border: 1px solid #edf2f7;
  box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.03);
}

.rack-3d-group {
  --cube-spacing-x: 34px;
  --cube-spacing-y: 26px;
  --cube-spacing-z: 22px;
  position: relative;
  width: 100%;
  height: 100%;
  transform-style: preserve-3d;
  transition: transform 0.5s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.rack-cell-3d {
  position: absolute;
  width: 22px;
  height: 22px;
  left: 50%;
  top: 50%;
  margin-left: -11px;
  margin-top: -11px;
  transform-style: preserve-3d;
}

/* 3D Cube faces styling */
.iso-cube-wrapper {
  position: absolute;
  width: 100%;
  height: 100%;
  transform-style: preserve-3d;
  cursor: pointer;
  /* Glassmorphism translucent look to see behind */
  opacity: 0.88;
  transition: opacity 0.2s ease;
}

.iso-cube-wrapper:hover {
  opacity: 1.0;
}

.iso-cube {
  position: relative;
  width: 100%;
  height: 100%;
  transform-style: preserve-3d;
  transition: transform 0.2s ease;
}

.iso-cube-wrapper:hover:not(.blocked):not(.has-product):not(.source) .iso-cube {
  transform: translateZ(6px);
}

.cube-face {
  position: absolute;
  width: 100%;
  height: 100%;
  border: 1px solid rgba(255, 255, 255, 0.45);
  box-sizing: border-box;
}

.top-face {
  transform: translateZ(8px);
  background-color: var(--cube-top);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: inset 0 0 6px rgba(255, 255, 255, 0.3);
}

.cube-inner-label {
  display: none; /* Hide labels in compact preview */
}

.front-face {
  transform: rotateX(-90deg) translateZ(4px) translateY(4px);
  height: 8px;
  background-color: var(--cube-front);
}

.side-face {
  transform: rotateY(90deg) translateZ(4px) translateX(4px);
  width: 8px;
  background-color: var(--cube-side);
}

/* Modal specfic visualizer overrides */
.modal-layout {
  display: flex;
  gap: 1.5rem;
  align-items: flex-start;
  min-height: 520px;
}

.modal-scene-container {
  flex: 1;
  min-width: 0;
}

.modal-sidebar-container {
  width: 320px;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.min-height-80 {
  min-height: 80px;
}

.max-height-200 {
  max-height: 200px;
}

.overflow-y-auto {
  overflow-y: auto;
}

.rack-3d-scene.in-modal {
  height: 500px;
  cursor: grab;
  user-select: none;
}

.rack-3d-scene.in-modal:active {
  cursor: grabbing;
}

.rack-3d-group.in-modal {
  --cube-spacing-x: 58px;
  --cube-spacing-y: 44px;
  --cube-spacing-z: 42px;
}

.rack-cell-3d.in-modal {
  width: 44px;
  height: 44px;
  margin-left: -22px;
  margin-top: -22px;
}

.cube-face.top-face.in-modal {
  transform: translateZ(18px);
  box-shadow: inset 0 0 8px rgba(255, 255, 255, 0.35);
}

.cube-inner-label.in-modal {
  display: inline-block;
  font-size: 0.6rem;
  font-weight: 800;
}

.cube-face.front-face.in-modal {
  transform: rotateX(-90deg) translateZ(9px) translateY(9px);
  height: 18px;
}

.cube-face.side-face.in-modal {
  transform: rotateY(90deg) translateZ(9px) translateX(9px);
  width: 18px;
}

/* Cube Colors */
.iso-cube-wrapper.source {
  --cube-top: #ecc94b;
  --cube-front: #d69e2e;
  --cube-side: #b7791f;
  --cube-text-color: #744210;
  cursor: default;
}

.iso-cube-wrapper.available {
  --cube-top: #cbd5e0;
  --cube-front: #a0aec0;
  --cube-side: #718096;
  --cube-text-color: #2d3748;
}

.iso-cube-wrapper.available.selected {
  --cube-top: #48bb78;
  --cube-front: #38a169;
  --cube-side: #2f855a;
  --cube-text-color: white;
  filter: drop-shadow(0 0 6px rgba(72, 187, 120, 0.6));
}

.iso-cube-wrapper.blocked {
  --cube-top: #fc8181;
  --cube-front: #e53e3e;
  --cube-side: #c53030;
  --cube-text-color: white;
  cursor: not-allowed;
}

.iso-cube-wrapper.has-product {
  --cube-top: #ed8936;
  --cube-front: #dd6b20;
  --cube-side: #c05621;
  --cube-text-color: white;
  cursor: not-allowed;
}

/* Empty slots */
.empty-iso-slot {
  position: absolute;
  width: 100%;
  height: 100%;
  transform-style: preserve-3d;
}

.empty-slot-outline {
  width: 100%;
  height: 100%;
  border: 1px dashed #cbd5e0;
  background: rgba(226, 232, 240, 0.2);
  transform: translateZ(0);
}

/* Legend and footer styling */
.hover-info-box {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px 12px;
  min-height: 38px;
  display: flex;
  align-items: center;
}

.legend-box {
  display: flex;
  gap: 12px;
  justify-content: center;
  background: #edf2f7;
  border-radius: 8px;
  padding: 8px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  color: #4a5568;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.source-dot { background-color: #ecc94b; }
.available-dot { background-color: #cbd5e0; }
.selected-dot { background-color: #48bb78; }
.blocked-dot { background-color: #fc8181; }
.product-dot { background-color: #ed8936; }

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

  .modal-layout {
    flex-direction: column;
    height: auto;
  }

  .modal-sidebar-container {
    width: 100%;
    margin-top: 1rem;
  }
  
  .rack-3d-scene.in-modal {
    height: 300px;
  }
}
</style>

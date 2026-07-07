<template>
  <div class="import_helper_overlay">
    <div class="import_helper_container">
      
      <!-- Header -->
      <header class="helper_header">
        <h2>Importar Archivo de Picks</h2>
        <Button icon="fa fa-times" severity="danger" rounded text @click="$emit('close')" />
      </header>

      <!-- Step 1: Upload File -->
      <section v-if="currentStep === 1" class="step_section upload_step">
        <div class="upload_card">
          <div class="upload_icon">
            <i class="fa fa-cloud-upload"></i>
          </div>
          <h3>Sube tu archivo XLSX o CSV</h3>
          <p class="file_limits">Formatos soportados: <strong>.csv, .xlsx, .xls</strong> (máx. 1 GB)</p>
          
          <div class="file_input_container">
            <input type="file" ref="fileInput" accept=".csv, .xlsx, .xls" @change="onFileChange" class="hidden_file_input" id="picks_file_upload" />
            <label for="picks_file_upload" class="file_label_btn">
              {{ selectedFile ? selectedFile.name : 'Seleccionar archivo...' }}
            </label>
          </div>

          <div class="option_row mt-4">
            <label class="checkbox_label">
              <input type="checkbox" v-model="hasHeader" />
              <span>El archivo contiene encabezados de columnas</span>
            </label>
          </div>

          <div class="action_buttons mt-6">
            <Button label="Subir y Validar" severity="success" icon="fa fa-arrow-right" :disabled="!selectedFile || store.loading" @click="uploadFile" />
          </div>
        </div>
      </section>

      <!-- Step 2: Mapping Configuration (Spreadsheet Preview Style) -->
      <section v-if="currentStep === 2" class="step_section mapping_step">
        <div class="info_banner mb-4">
          <i class="fa fa-info-circle mr-2"></i>
          <span>Asigna las columnas correspondientes seleccionando los campos obligatorios y opcionales sobre cada columna en la previsualización del archivo.</span>
        </div>

        <div class="mapping_preview_container">
          <table class="preview_table">
            <thead>
              <!-- Dropdown selectors row -->
              <tr class="selectors_row">
                <th v-for="(h, colIdx) in headers" :key="'sel-' + colIdx" class="selector_cell">
                  <Select 
                    :modelValue="getColumnMapping(colIdx)" 
                    @update:modelValue="(val) => setColumnMapping(colIdx, val)"
                    :options="mappingFieldOptions" 
                    optionLabel="label" 
                    optionValue="value" 
                    placeholder="[No mapeado]"
                    class="w-full mapping_dropdown"
                  />
                </th>
              </tr>
              <!-- Column headers name row -->
              <tr class="headers_row">
                <th v-for="(h, colIdx) in headers" :key="'head-' + colIdx">
                  <span class="column_index">Columna {{ colIdx + 1 }}</span>
                  <span class="column_header_name" :title="h">{{ h }}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, rowIdx) in previewRows" :key="'prev-' + rowIdx">
                <td v-for="(val, colIdx) in row.original_row" :key="'cell-' + colIdx">
                  {{ val }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Required fields indicators -->
        <div class="required_fields_status mt-4">
          <div class="status_indicator" :class="{ 'ok': mapping.SO !== null }">
            <i class="fa" :class="mapping.SO !== null ? 'fa-check-circle' : 'fa-exclamation-circle'"></i>
            <span>SO (Obligatorio)</span>
          </div>
          <div class="status_indicator" :class="{ 'ok': mapping.Oleada !== null }">
            <i class="fa" :class="mapping.Oleada !== null ? 'fa-check-circle' : 'fa-exclamation-circle'"></i>
            <span>Oleada (Obligatorio)</span>
          </div>
        </div>

        <div class="action_buttons mt-6">
          <Button label="Atrás" severity="secondary" icon="fa fa-arrow-left" @click="currentStep = 1" />
          <Button label="Validar Mapeo" severity="success" icon="fa fa-check" :disabled="!isMappingValid" @click="validateWithMapping" />
        </div>
      </section>

      <!-- Step 3: Interactive Manager/Helper View -->
      <section v-if="currentStep === 3" class="step_section manager_step">
        
        <!-- Interactive Filter Tabs -->
        <div class="filter_tabs_bar mb-4">
          <button class="filter_tab" :class="{ 'active': selectedStatusFilter === 'all' }" @click="selectedStatusFilter = 'all'">
            <span class="tab_lbl">Todos</span>
            <span class="tab_val bg-all">{{ allRowsCount }}</span>
          </button>
          
          <button class="filter_tab" :class="{ 'active': selectedStatusFilter === 'error' }" @click="selectedStatusFilter = 'error'">
            <span class="tab_lbl">Con Errores</span>
            <span class="tab_val bg-danger">{{ errorRowsCount }}</span>
          </button>
          
          <button class="filter_tab" :class="{ 'active': selectedStatusFilter === 'warning' }" @click="selectedStatusFilter = 'warning'">
            <span class="tab_lbl">Con Advertencias</span>
            <span class="tab_val bg-warning">{{ warningRowsCount }}</span>
          </button>
          
          <button class="filter_tab" :class="{ 'active': selectedStatusFilter === 'excluded' }" @click="selectedStatusFilter = 'excluded'">
            <span class="tab_lbl">Excluidas</span>
            <span class="tab_val bg-secondary">{{ excludedRowsCount }}</span>
          </button>
          
          <button class="filter_tab" :class="{ 'active': selectedStatusFilter === 'ok' }" @click="selectedStatusFilter = 'ok'">
            <span class="tab_lbl">Correctas (OK)</span>
            <span class="tab_val bg-success">{{ okRowsCount }}</span>
          </button>
        </div>

        <!-- Spreadsheet Table Grouped by Wave -->
        <div class="table_scroll_container">
          <table class="spreadsheet_table">
            <thead>
              <tr>
                <th style="width: 60px;">Excluir</th>
                <th style="width: 80px;">Estado</th>
                <th>SO *</th>
                <th>Pick Asignado</th>
                <th>Posición</th>
                <th>SKU</th>
                <th>Unidades</th>
                <th>OrdenPick</th>
                <th style="width: 140px;">Acciones</th>
              </tr>
            </thead>
            <tbody v-for="wave in groupedRowsByWave" :key="wave.name">
              <!-- Wave Header Row -->
              <tr class="wave_group_header">
                <td colspan="9">
                  <div class="wave_header_content">
                    <div class="wave_header_left" @click="toggleWaveCollapse(wave.name)">
                      <i class="fa mr-2" :class="collapsedWaves[wave.name] ? 'fa-chevron-right' : 'fa-chevron-down'"></i>
                      <span class="wave_title">Ola/Oleada: <strong>{{ wave.name }}</strong> ({{ wave.activeCount }} filas filtradas)</span>
                      
                      <!-- Status Indicator in header -->
                      <span v-if="wave.hasErrors" class="badge badge-danger ml-2">CON ERRORES</span>
                      <span v-else-if="wave.hasWarnings" class="badge badge-warning ml-2">ADVERTENCIAS</span>
                      <span v-else class="badge badge-success">OK</span>
                    </div>
                    
                    <div class="wave_header_right" @click.stop>
                      <label class="mr-2 text-xs font-bold text-slate-600">Operador Ola:</label>
                      <Select 
                        :modelValue="wave.picker" 
                        @update:modelValue="(val) => onWaveOperatorChange(wave.name, val)"
                        :options="operators" 
                        optionLabel="name" 
                        optionValue="name" 
                        filter 
                        :showClear="true"
                        placeholder="Asignar operador..." 
                        class="wave_header_select"
                        :class="{ 'border-red': !wave.picker && wave.name !== 'Sin Ola' && wave.activeCount > 0 }"
                      />
                      <span v-if="!wave.picker && wave.name !== 'Sin Ola' && wave.activeCount > 0" class="text-danger text-xs ml-2 font-bold">
                        <i class="fa fa-exclamation-triangle"></i> Operador Requerido
                      </span>
                    </div>
                  </div>
                </td>
              </tr>

              <!-- Wave Rows (only shown if not collapsed) -->
              <template v-if="!collapsedWaves[wave.name]">
                <tr v-for="row in wave.rows" :key="row.index" 
                    :class="{ 'row_excluded': row.excluded, 'row_selected': activeRowDetails && activeRowDetails.index === row.index }"
                    @click="selectRow(row)">
                  
                  <!-- Exclude Checkbox -->
                  <td class="text-center" @click.stop>
                    <input type="checkbox" v-model="row.excluded" @change="onRowEdit(row)" />
                  </td>

                  <!-- Status Badge -->
                  <td class="text-center">
                    <span v-if="row.excluded" class="badge badge-secondary">EXCL</span>
                    <span v-else-if="row.errors.length > 0" class="badge badge-danger" :title="getRowErrorsText(row)">
                      ERROR ({{ row.errors.length }})
                    </span>
                    <span v-else-if="row.warnings.length > 0" class="badge badge-warning" :title="getRowWarningsText(row)">
                      ADVERT ({{ row.warnings.length }})
                    </span>
                    <span v-else class="badge badge-success">OK</span>
                  </td>

                  <!-- SO -->
                  <td>
                    <span class="text-xs text-slate-800">{{ row.data.SO }}</span>
                  </td>

                  <!-- Pick Asignado (Non-editable) -->
                  <td>
                    <span class="text-xs font-bold text-blue-600">{{ row.picking_name || 'Sin Pick' }}</span>
                  </td>

                  <!-- PosicionN1 -->
                  <td>
                    <span class="text-xs text-slate-800">{{ row.data.PosicionN1 }}</span>
                    <span v-if="row.not_in_excel" class="badge badge-secondary ml-2" style="font-size: 0.65rem; padding: 0.1rem 0.25rem; display: inline-block;">No en Excel</span>
                    <div v-else-if="row.odoo_data && row.odoo_data.location_name && row.odoo_data.location_name !== row.data.PosicionN1" class="text-muted" style="font-size: 0.7rem; margin-top: 0.1rem;">
                      Odoo: {{ row.odoo_data.location_name }}
                    </div>
                  </td>

                  <!-- SKU -->
                  <td>
                    <span class="text-xs text-slate-800">{{ row.data.SKU }}</span>
                  </td>

                  <!-- Unidades -->
                  <td>
                    <span class="text-xs text-slate-800 text-right block">{{ row.data.Unidades }}</span>
                    <div v-if="!row.not_in_excel && row.odoo_data && row.odoo_data.quantity !== undefined && parseFloat(row.odoo_data.quantity) !== parseFloat(row.data.Unidades)" class="text-muted text-right" style="font-size: 0.7rem; margin-top: 0.1rem;">
                      Odoo: {{ row.odoo_data.quantity }}
                    </div>
                  </td>

                  <!-- OrdenPick -->
                  <td>
                    <span class="text-xs text-slate-800 text-right block">{{ row.data.OrdenPick }}</span>
                  </td>

                  <!-- Actions -->
                  <td class="text-center" @click.stop>
                    <Button 
                      v-if="row.picking_id && (hasWarningCode(row, 'no_stock') || hasWarningCode(row, 'not_assigned'))"
                      label="Odoo Reservar" 
                      severity="warning" 
                      icon="fa fa-refresh" 
                      size="small" 
                      @click="forceOdooReservation(row)" 
                      :disabled="row.excluded || store.loading" 
                      class="p-button-xs" 
                      title="Desreservar y volver a reservar usando algoritmo estándar de Odoo"
                    />
                    <span v-else class="text-muted text-xs">-</span>
                  </td>

                </tr>
              </template>
            </tbody>
          </table>
        </div>

        <!-- Row Validation Errors/Warnings Details banner -->
        <div class="alert_details mt-4" v-if="activeRowDetails">
          <h5>Detalles de Fila {{ activeRowDetails.index + 1 }} {{ activeRowDetails.data.SO ? '(' + activeRowDetails.data.SO + ')' : '' }}:</h5>
          <ul v-if="activeRowDetails.errors.length > 0 || activeRowDetails.warnings.length > 0">
            <li v-for="err in activeRowDetails.errors" :key="err.message" class="text-danger">
              <i class="fa fa-exclamation-triangle mr-1"></i> <strong>[{{ err.field }}]:</strong> {{ err.message }}
            </li>
            <li v-for="warn in activeRowDetails.warnings" :key="warn.message" class="text-warning">
              <i class="fa fa-info-circle mr-1"></i> <strong>[{{ warn.field }}]:</strong> {{ warn.message }}
            </li>
          </ul>
          <div v-else class="text-success text-sm font-semibold">
            <i class="fa fa-check-circle mr-1"></i> Esta fila no tiene errores ni advertencias.
          </div>
        </div>

        <!-- Actions Footer -->
        <div class="action_buttons mt-6">
          <Button label="Reemplazar archivo" severity="danger" icon="fa fa-upload" outlined @click="resetImport" />
          <Button label="Volver a Validar" severity="info" icon="fa fa-refresh" :loading="store.loading" @click="revalidateRows" />
          <Button label="Crear Planes de Pickeo" severity="success" icon="fa fa-check-double" :disabled="store.loading" @click="processImport" />
        </div>
      </section>

    </div>
  </div>
</template>

<script>
import Button from 'primevue/button';
import InputText from 'primevue/inputtext';
import Select from 'primevue/select';
import { useGeneralStore } from '../../store';

export default {
  name: "ImportPicksHelper",
  components: {
    Button,
    InputText,
    Select
  },
  data() {
    return {
      store: useGeneralStore(),
      currentStep: 1,
      selectedFile: null,
      hasHeader: true,
      headers: [],
      mapping: {
        SO: null,
        Oleada: null,
        Picker: null,
        picker_id: null,
        PosicionN1: null,
        posicion_N1_id: null,
        SKU: null,
        Unidades: null,
        OrdenPick: null
      },
      requiredFields: [
        { key: 'SO', label: 'Sale Order (SO)', required: true },
        { key: 'Oleada', label: 'Oleada (Ola)', required: true },
        { key: 'Picker', label: 'Picker (Operador)', required: false },
        { key: 'picker_id', label: 'ID Picker (Operador)', required: false },
        { key: 'PosicionN1', label: 'Posición N1', required: false },
        { key: 'posicion_N1_id', label: 'ID Posición N1', required: false },
        { key: 'SKU', label: 'SKU (Producto)', required: false },
        { key: 'Unidades', label: 'Unidades', required: false },
        { key: 'OrdenPick', label: 'Orden Pick', required: false }
      ],
      rows: [],
      operators: [],
      editedRows: new Set(),
      selectedRow: null,
      collapsedWaves: {},
      selectedStatusFilter: 'all',
      mappingFieldOptions: [
        { label: '[No mapeado]', value: null },
        { label: 'SO (Pedido) * Obligatorio', value: 'SO' },
        { label: 'Oleada (Ola) * Obligatorio', value: 'Oleada' },
        { label: 'Picker (Operador)', value: 'Picker' },
        { label: 'ID Picker (Operador)', value: 'picker_id' },
        { label: 'Posición N1', value: 'PosicionN1' },
        { label: 'ID Posición N1', value: 'posicion_N1_id' },
        { label: 'SKU (Producto)', value: 'SKU' },
        { label: 'Unidades', value: 'Unidades' },
        { label: 'Orden Pick', value: 'OrdenPick' }
      ]
    };
  },
  computed: {
    fileHeadersOptions() {
      return this.headers.map((h, i) => ({ label: h || `Columna ${i + 1}`, value: i }));
    },
    isMappingValid() {
      return this.mapping.SO !== null && this.mapping.Oleada !== null;
    },
    allRowsCount() {
      return this.rows.length;
    },
    errorRowsCount() {
      return this.rows.filter(r => !r.excluded && r.errors.length > 0).length;
    },
    warningRowsCount() {
      return this.rows.filter(r => !r.excluded && r.errors.length === 0 && r.warnings.length > 0).length;
    },
    excludedRowsCount() {
      return this.rows.filter(r => r.excluded).length;
    },
    okRowsCount() {
      return this.rows.filter(r => !r.excluded && r.errors.length === 0 && r.warnings.length === 0).length;
    },
    previewRows() {
      return this.rows.slice(0, 5);
    },
    groupedRowsByWave() {
      const groups = {};
      this.rows.forEach(row => {
        const wave = row.data.Oleada || 'Sin Ola';
        if (!groups[wave]) {
          groups[wave] = {
            name: wave,
            rows: [],
            picker: ''
          };
        }
        groups[wave].rows.push(row);
        if (!groups[wave].picker && row.data.Picker) {
          groups[wave].picker = row.data.Picker;
        }
      });

      const result = [];
      Object.keys(groups).forEach(key => {
        const group = groups[key];
        
        let filteredRows = group.rows;
        if (this.selectedStatusFilter === 'error') {
          filteredRows = group.rows.filter(r => !r.excluded && r.errors.length > 0);
        } else if (this.selectedStatusFilter === 'warning') {
          filteredRows = group.rows.filter(r => !r.excluded && r.errors.length === 0 && r.warnings.length > 0);
        } else if (this.selectedStatusFilter === 'excluded') {
          filteredRows = group.rows.filter(r => r.excluded);
        } else if (this.selectedStatusFilter === 'ok') {
          filteredRows = group.rows.filter(r => !r.excluded && r.errors.length === 0 && r.warnings.length === 0);
        }

        if (filteredRows.length > 0) {
          const activeRows = filteredRows.filter(r => !r.excluded);
          const hasErrors = activeRows.some(r => r.errors.length > 0);
          const hasWarnings = activeRows.some(r => r.errors.length === 0 && r.warnings.length > 0);
          
          result.push({
            name: key,
            rows: filteredRows,
            picker: group.picker,
            activeCount: activeRows.length,
            hasErrors,
            hasWarnings
          });
        }
      });

      return result;
    },
    hasErrors() {
      if (this.rows.some(r => !r.excluded && r.errors.length > 0)) return true;
      return this.groupedRowsByWave.some(w => !w.picker && w.name !== 'Sin Ola' && w.activeCount > 0);
    },
    activeRowDetails() {
      if (this.selectedRow) {
        const current = this.rows.find(r => r.index === this.selectedRow.index);
        if (current) return current;
      }
      return this.rows.find(r => !r.excluded && (r.errors.length > 0 || r.warnings.length > 0)) || null;
    }
  },
  methods: {
    onFileChange(event) {
      const file = event.target.files[0];
      if (file) {
        const ext = file.name.split('.').pop().toLowerCase();
        if (!['csv', 'xlsx', 'xls'].includes(ext)) {
          this.store.toast.add({
            severity: 'error',
            summary: 'Archivo Inválido',
            detail: 'Debe seleccionar un archivo CSV o XLSX.',
            life: 5000
          });
          this.selectedFile = null;
          return;
        }
        if (file.size > 1024 * 1024 * 1024) {
          this.store.toast.add({
            severity: 'error',
            summary: 'Archivo Demasiado Grande',
            detail: 'El tamaño máximo del archivo es de 1 GB.',
            life: 5000
          });
          this.selectedFile = null;
          return;
        }
        this.selectedFile = file;
      }
    },
    async uploadFile() {
      if (!this.selectedFile) return;
      const res = await this.store.uploadPicksFile(this.selectedFile, this.hasHeader);
      if (res.error) {
        this.store.toast.add({
          severity: 'error',
          summary: 'Error al Subir',
          detail: res.error_msg || 'Ocurrió un error al subir el archivo.',
          life: 5000
        });
        return;
      }

      this.headers = res.headers || [];
      this.rows = res.rows || [];
      this.selectedRow = null;
      this.collapsedWaves = {};
      this.selectedStatusFilter = 'all';
      
      if (res.mapping && res.mapping.SO !== undefined && res.mapping.Oleada !== undefined) {
        this.mapping = {
          SO: res.mapping.SO,
          Oleada: res.mapping.Oleada,
          Picker: res.mapping.Picker ?? null,
          picker_id: res.mapping.picker_id ?? null,
          PosicionN1: res.mapping.PosicionN1 ?? null,
          posicion_N1_id: res.mapping.posicion_N1_id ?? null,
          SKU: res.mapping.SKU ?? null,
          Unidades: res.mapping.Unidades ?? null,
          OrdenPick: res.mapping.OrdenPick ?? null
        };
        this.currentStep = 3;
      } else {
        this.mapping = {
          SO: res.mapping?.SO ?? null,
          Oleada: res.mapping?.Oleada ?? null,
          Picker: res.mapping?.Picker ?? null,
          picker_id: res.mapping?.picker_id ?? null,
          PosicionN1: res.mapping?.PosicionN1 ?? null,
          posicion_N1_id: res.mapping?.posicion_N1_id ?? null,
          SKU: res.mapping?.SKU ?? null,
          Unidades: res.mapping?.Unidades ?? null,
          OrdenPick: res.mapping?.OrdenPick ?? null
        };
        this.currentStep = 2;
      }
    },
    async validateWithMapping() {
      const res = await this.store.uploadPicksFile(this.selectedFile, this.hasHeader, this.mapping);
      if (res.error) {
        this.store.toast.add({
          severity: 'error',
          summary: 'Error de Validación',
          detail: res.error_msg || 'Error al validar el archivo.',
          life: 5000
        });
        return;
      }
      this.rows = res.rows || [];
      this.selectedRow = null;
      this.collapsedWaves = {};
      this.selectedStatusFilter = 'all';
      this.currentStep = 3;
    },
    async revalidateRows() {
      const res = await this.store.callOdoo('import_picks_validate_rows', '', { rows: this.rows });
      if (res.error) {
        this.store.toast.add({
          severity: 'error',
          summary: 'Error al Validar',
          detail: res.error_msg || 'No se pudieron validar los registros.',
          life: 5000
        });
        return;
      }
      this.rows = res.rows || [];
      this.store.toast.add({
        severity: 'info',
        summary: 'Validación Completada',
        detail: 'Los registros han sido re-validados contra Odoo.',
        life: 3000
      });
    },
    async forceOdooReservation(row) {
      if (!row.picking_id) return;
      const params = {
        picking_id: row.picking_id,
        sku: row.data.SKU,
        posicion: row.data.PosicionN1,
        unidades: row.data.Unidades
      };
      const res = await this.store.callOdoo('unreserve_and_reserve', '', params);
      if (res.error) {
        this.store.toast.add({
          severity: 'error',
          summary: 'Error Odoo',
          detail: res.error_msg || 'No se pudo realizar la re-reserva.',
          life: 5000
        });
        return;
      }
      
      if (res.reservations && row.data.SKU) {
        const actualLoc = res.reservations[row.data.SKU];
        if (actualLoc) {
          row.data.PosicionN1 = actualLoc;
          this.onRowEdit(row);
        }
      }

      this.store.toast.add({
        severity: 'success',
        summary: 'Reserva Restablecida',
        detail: `Reserva re-computada con el algoritmo estándar de Odoo. Estado actual: ${res.picking_state}`,
        life: 4000
      });
      await this.revalidateRows();
    },
    onRowEdit(row) {
      this.editedRows.add(row.index);
    },
    onWaveOperatorChange(waveName, newOperatorName) {
      this.rows.forEach(row => {
        const rowWave = row.data.Oleada || 'Sin Ola';
        if (rowWave === waveName) {
          row.data.Picker = newOperatorName;
          this.onRowEdit(row);
        }
      });
    },
    toggleWaveCollapse(waveName) {
      const isCollapsed = this.collapsedWaves[waveName] ?? false;
      this.collapsedWaves = {
        ...this.collapsedWaves,
        [waveName]: !isCollapsed
      };
    },
    getColumnMapping(colIdx) {
      for (const [field, idx] of Object.entries(this.mapping)) {
        if (idx === colIdx) return field;
      }
      return null;
    },
    setColumnMapping(colIdx, field) {
      for (const [k, v] of Object.entries(this.mapping)) {
        if (k === field) {
          this.mapping[k] = null;
        }
      }
      for (const [k, v] of Object.entries(this.mapping)) {
        if (v === colIdx) {
          this.mapping[k] = null;
        }
      }
      if (field) {
        this.mapping[field] = colIdx;
      }
    },
    selectRow(row) {
      this.selectedRow = row;
    },
    resetImport() {
      this.selectedFile = null;
      if (this.$refs.fileInput) {
        this.$refs.fileInput.value = '';
      }
      this.rows = [];
      this.headers = [];
      this.mapping = {
        SO: null,
        Oleada: null,
        Picker: null,
        picker_id: null,
        PosicionN1: null,
        posicion_N1_id: null,
        SKU: null,
        Unidades: null,
        OrdenPick: null
      };
      this.selectedRow = null;
      this.collapsedWaves = {};
      this.selectedStatusFilter = 'all';
      this.currentStep = 1;
    },
    getRowErrorsText(row) {
      return row.errors.map(e => e.message).join('\n');
    },
    getRowWarningsText(row) {
      return row.warnings.map(w => w.message).join('\n');
    },
    hasWarningCode(row, code) {
      return row.warnings.some(w => w.code === code);
    },
    async processImport() {
      const res = await this.store.callOdoo('import_picks_process', '', { rows: this.rows, headers: this.headers });
      if (res.error) {
        this.store.toast.add({
          severity: 'error',
          summary: 'Error al Procesar',
          detail: res.error_msg || 'Error del sistema durante el procesamiento.',
          life: 5000
        });
        return;
      }

      if (res.xlsx_file) {
        try {
          const byteCharacters = atob(res.xlsx_file);
          const byteNumbers = new Array(byteCharacters.length);
          for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
          }
          const byteArray = new Uint8Array(byteNumbers);
          const blob = new Blob([byteArray], {type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});
          const link = document.createElement('a');
          link.href = window.URL.createObjectURL(blob);
          link.download = res.filename || 'retroalimentacion_picks.xlsx';
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        } catch (e) {
          console.error("Error al descargar excel de retroalimentación:", e);
        }
      }

      if (res.had_errors) {
        this.store.toast.add({
          severity: 'warn',
          summary: 'Importación con Advertencias',
          detail: 'Se crearon planes de pickeo para los registros válidos. Se descargó el Excel de retroalimentación con los detalles de los errores.',
          life: 8000
        });
      } else {
        this.store.toast.add({
          severity: 'success',
          summary: 'Importación Exitosa',
          detail: res.message || 'Se han creado y confirmado los planes de pickeo.',
          life: 6000
        });
      }

      this.$emit('success');
    }
  },
  async mounted() {
    const res = await this.store.callOdoo("operadores", "*");
    this.operators = res || [];
  }
};
</script>

<style scoped>
.import_helper_overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(15, 23, 42, 0.7);
  backdrop-filter: blur(8px);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 500;
}

.import_helper_container {
  background: white;
  width: 95%;
  max-width: 1400px;
  height: 85%;
  max-height: 90vh;
  border-radius: 16px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 1.5rem;
}

.helper_header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 1rem;
  margin-bottom: 1.5rem;
}

.helper_header h2 {
  font-size: 1.5rem;
  font-weight: 800;
  color: #0f172a;
  margin: 0;
}

.step_section {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Step 1: Upload Card */
.upload_step {
  align-items: center;
  justify-content: center;
}

.upload_card {
  border: 2px dashed #cbd5e1;
  border-radius: 12px;
  padding: 3rem;
  text-align: center;
  width: 100%;
  max-width: 600px;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.upload_icon {
  font-size: 3.5rem;
  color: #64748b;
  margin-bottom: 1rem;
}

.file_limits {
  font-size: 0.85rem;
  color: #64748b;
  margin-top: 0.5rem;
}

.file_input_container {
  margin-top: 1.5rem;
}

.hidden_file_input {
  display: none;
}

.file_label_btn {
  display: inline-block;
  padding: 0.75rem 1.5rem;
  background: #1e293b;
  color: white;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  transition: background 0.2s;
}

.file_label_btn:hover {
  background: #0f172a;
}

.checkbox_label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  color: #334155;
  font-size: 0.95rem;
}

/* Step 2: Spreadsheet Preview Mapping */
.mapping_preview_container {
  flex: 1;
  overflow: auto;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  box-shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.06);
}

.preview_table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.preview_table th {
  background: #f8fafc;
  padding: 0.75rem;
  border-bottom: 2px solid #cbd5e1;
  border-right: 1px solid #e2e8f0;
  text-align: left;
}

.preview_table td {
  padding: 0.75rem;
  border-bottom: 1px solid #e2e8f0;
  border-right: 1px solid #e2e8f0;
  background: white;
  color: #475569;
  white-space: nowrap;
}

.selector_cell {
  background: #f1f5f9 !important;
  padding: 0.5rem !important;
  border-bottom: 1px solid #cbd5e1 !important;
}

.mapping_dropdown :deep(.p-select) {
  font-size: 0.8rem;
  padding: 0.15rem 0.35rem;
}

.column_index {
  display: block;
  font-size: 0.7rem;
  color: #64748b;
  text-transform: uppercase;
  font-weight: 700;
}

.column_header_name {
  display: block;
  font-weight: 800;
  color: #0f172a;
  margin-top: 0.15rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 180px;
}

.required_fields_status {
  display: flex;
  gap: 1.5rem;
}

.status_indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: #94a3b8;
  font-weight: bold;
}

.status_indicator.ok {
  color: #10b981;
}

.status_indicator i {
  font-size: 1.1rem;
}

/* Step 3: Interactive Filter Tabs Bar */
.filter_tabs_bar {
  display: flex;
  gap: 0.75rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 0.5rem;
}

.filter_tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.6rem 0.8rem;
  border: 1px solid transparent;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.8rem;
  font-weight: 700;
  color: #64748b;
  transition: all 0.2s ease;
}

.filter_tab:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.filter_tab.active {
  background: white;
  border-color: #cbd5e1;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  color: #0f172a;
}

.tab_val {
  padding: 0.15rem 0.45rem;
  font-size: 0.75rem;
  font-weight: 800;
  border-radius: 6px;
}

.bg-all { background: #e2e8f0; color: #334155; }
.bg-danger { background: #ef4444; color: #ffffff; }
.bg-warning { background: #f59e0b; color: #ffffff; }
.bg-secondary { background: #64748b; color: #ffffff; }
.bg-success { background: #10b981; color: #ffffff; }

/* Wave Group Headers */
.wave_group_header td {
  background: #f1f5f9 !important;
  padding: 0.5rem 1rem !important;
  border-bottom: 2px solid #cbd5e1;
  border-top: 2px solid #cbd5e1;
}

.wave_header_content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.wave_header_left {
  display: flex;
  align-items: center;
  cursor: pointer;
  user-select: none;
  flex: 1;
}

.wave_title {
  font-weight: 800;
  color: #1e293b;
  font-size: 0.95rem;
}

.wave_header_right {
  display: flex;
  align-items: center;
}

.wave_header_select {
  width: 220px;
  font-size: 0.8rem;
}

.wave_header_select.border-red :deep(.p-select) {
  border-color: #ef4444 !important;
  box-shadow: 0 0 0 1px #fee2e2 !important;
}

/* Spreadsheet Table */
.table_scroll_container {
  flex: 1;
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-top: 1rem;
  box-shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.06);
}

.spreadsheet_table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.spreadsheet_table th {
  background: #f1f5f9;
  position: sticky;
  top: 0;
  z-index: 10;
  padding: 0.75rem;
  text-align: left;
  font-weight: 700;
  color: #334155;
  border-bottom: 2px solid #cbd5e1;
  border-right: 1px solid #e2e8f0;
}

.spreadsheet_table td {
  padding: 0.5rem;
  border-bottom: 1px solid #e2e8f0;
  border-right: 1px solid #e2e8f0;
  vertical-align: middle;
  background: white;
}

.spreadsheet_table tbody tr {
  cursor: pointer;
  transition: background 0.15s;
}

.spreadsheet_table tbody tr:hover td {
  background: #f8fafc;
}

.spreadsheet_table tr.row_excluded td {
  background: #f1f5f9;
  opacity: 0.65;
}

.spreadsheet_table tr.row_selected td {
  background: #eff6ff !important;
  border-top: 1px solid #93c5fd;
  border-bottom: 1px solid #93c5fd;
}

.table_input {
  width: 100%;
  padding: 0.35rem 0.5rem;
  font-size: 0.85rem;
  border-radius: 4px;
  border: 1px solid #cbd5e1;
}

.table_input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 1px #3b82f6;
}

.table_select {
  width: 100%;
  font-size: 0.85rem;
}

.badge {
  display: inline-block;
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
  font-weight: bold;
  border-radius: 4px;
  text-transform: uppercase;
}

.badge-success { background: #dcfce7; color: #166534; }
.badge-danger { background: #fee2e2; color: #991b1b; }
.badge-warning { background: #fef9c3; color: #854d0e; }
.badge-secondary { background: #f1f5f9; color: #475569; }

.alert_details {
  background: #fffbeb;
  border: 1px solid #fde047;
  padding: 1rem;
  border-radius: 8px;
}

.alert_details h5 {
  margin: 0 0 0.5rem 0;
  font-size: 0.9rem;
  color: #854d0e;
  font-weight: 700;
}

.alert_details ul {
  margin: 0;
  padding-left: 1.25rem;
  font-size: 0.85rem;
}

.alert_details li {
  margin-bottom: 0.25rem;
}

.action_buttons {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
}

.p-button-xs {
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
}

.text-right {
  text-align: right;
}

.text-center {
  text-align: center;
}

.text-muted {
  color: #94a3b8;
}

.text-xs {
  font-size: 0.75rem;
}

.mt-4 { margin-top: 1rem; }
.mt-6 { margin-top: 1.5rem; }
.mb-4 { margin-bottom: 1rem; }
.mr-2 { margin-right: 0.5rem; }
.mr-1 { margin-right: 0.25rem; }
.ml-2 { margin-left: 0.5rem; }
.w-full { width: 100%; }
</style>

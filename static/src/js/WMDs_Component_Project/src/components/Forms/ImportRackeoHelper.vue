<template>
  <div class="import_rackeo_container">
    
    <!-- Header -->
    <header class="helper_header">
      <div class="header_title_group">
        <h2>Importar Archivo de Rackeo (STOR)</h2>
        <p class="header_subtitle">Carga masiva de rackeo para integrar mercancía desde Recepción (WH/IN) a ubicaciones de Stock</p>
      </div>
      <Button v-if="isModal" icon="fa fa-times" severity="danger" rounded text @click="$emit('close')" />
    </header>

    <!-- Step 1: Upload File -->
    <section v-if="currentStep === 1" class="step_section upload_step">
      <div class="upload_card">
        <div class="upload_icon">
          <i class="fa fa-cloud-upload"></i>
        </div>
        <h3>Sube tu archivo XLSX o CSV de Rackeo</h3>
        <p class="file_limits">Columnas esperadas: <strong>PO, SKU, UBICACIÓN, PZS</strong> (formatos .csv, .xlsx, .xls)</p>
        
        <div class="file_input_container">
          <input type="file" ref="fileInput" accept=".csv, .xlsx, .xls" @change="onFileChange" class="hidden_file_input" id="rackeo_file_upload" />
          <label for="rackeo_file_upload" class="file_label_btn">
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

    <!-- Step 2: Mapping Configuration -->
    <section v-if="currentStep === 2" class="step_section mapping_step">
      <div class="info_banner mb-4">
        <i class="fa fa-info-circle mr-2"></i>
        <span>Asigna las columnas correspondientes (PO, SKU, UBICACIÓN, PZS) sobre la previsualización del archivo.</span>
      </div>

      <div class="mapping_preview_container">
        <table class="preview_table">
          <thead>
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
        <div class="status_indicator" :class="{ 'ok': mapping.PO !== null }">
          <i class="fa" :class="mapping.PO !== null ? 'fa-check-circle' : 'fa-exclamation-circle'"></i>
          <span>PO (Obligatorio)</span>
        </div>
        <div class="status_indicator" :class="{ 'ok': mapping.SKU !== null }">
          <i class="fa" :class="mapping.SKU !== null ? 'fa-check-circle' : 'fa-exclamation-circle'"></i>
          <span>SKU (Obligatorio)</span>
        </div>
        <div class="status_indicator" :class="{ 'ok': mapping.UBICACION !== null }">
          <i class="fa" :class="mapping.UBICACION !== null ? 'fa-check-circle' : 'fa-exclamation-circle'"></i>
          <span>UBICACIÓN (Obligatorio)</span>
        </div>
        <div class="status_indicator" :class="{ 'ok': mapping.PZS !== null }">
          <i class="fa" :class="mapping.PZS !== null ? 'fa-check-circle' : 'fa-exclamation-circle'"></i>
          <span>PZS (Obligatorio)</span>
        </div>
      </div>

      <div class="action_buttons mt-6">
        <Button label="Atrás" severity="secondary" icon="fa fa-arrow-left" @click="currentStep = 1" />
        <Button label="Validar Mapeo" severity="success" icon="fa fa-check" :disabled="!isMappingValid" @click="validateWithMapping" />
      </div>
    </section>

    <!-- Step 3: Interactive Table View -->
    <section v-if="currentStep === 3" class="step_section manager_step">
      
      <!-- Filter Tabs -->
      <div class="filter_tabs_bar mb-4">
        <button class="filter_tab" :class="{ 'active': selectedStatusFilter === 'all' }" @click="selectedStatusFilter = 'all'">
          <span class="tab_lbl">Todos</span>
          <span class="tab_val bg-all">{{ allRowsCount }}</span>
        </button>
        
        <button class="filter_tab" :class="{ 'active': selectedStatusFilter === 'error' }" @click="selectedStatusFilter = 'error'">
          <span class="tab_lbl">Con Errores</span>
          <span class="tab_val bg-danger">{{ errorRowsCount }}</span>
        </button>
        
        <button class="filter_tab" :class="{ 'active': selectedStatusFilter === 'excluded' }" @click="selectedStatusFilter = 'excluded'">
          <span class="tab_lbl">Excluidos</span>
          <span class="tab_val bg-secondary">{{ excludedRowsCount }}</span>
        </button>
        
        <button class="filter_tab" :class="{ 'active': selectedStatusFilter === 'ok' }" @click="selectedStatusFilter = 'ok'">
          <span class="tab_lbl">Correctos (OK)</span>
          <span class="tab_val bg-success">{{ okRowsCount }}</span>
        </button>
      </div>

      <!-- Table Grouped by PO -->
      <div class="table_scroll_container">
        <table class="spreadsheet_table">
          <thead>
            <tr>
              <th style="width: 60px;">Excluir</th>
              <th style="width: 90px;">Estado</th>
              <th>PO (Orden de Compra) *</th>
              <th>SKU (Producto) *</th>
              <th>Ubicación Destino *</th>
              <th style="width: 100px; text-align: right;">Pzs (Cantidad) *</th>
              <th>Detalle de Validación</th>
            </tr>
          </thead>
          <tbody v-for="poGroup in groupedRowsByPO" :key="poGroup.name">
            <!-- PO Group Header -->
            <tr class="po_group_header">
              <td colspan="7">
                <div class="po_header_content" @click="togglePOCollapse(poGroup.name)">
                  <div class="po_header_left">
                    <i class="fa mr-2" :class="collapsedPOs[poGroup.name] ? 'fa-chevron-right' : 'fa-chevron-down'"></i>
                    <span class="po_title">Orden de Compra: <strong>{{ poGroup.name }}</strong> ({{ poGroup.activeCount }} líneas | {{ poGroup.totalPzs }} pzs)</span>
                    
                    <span v-if="poGroup.hasErrors" class="badge badge-danger ml-2">CON ERRORES</span>
                    <span v-else class="badge badge-success ml-2">OK LISTO PARA RACKEO</span>
                  </div>
                </div>
              </td>
            </tr>

            <!-- PO Rows -->
            <template v-if="!collapsedPOs[poGroup.name]">
              <tr v-for="row in poGroup.rows" :key="row.index" 
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
                  <span v-else class="badge badge-success">OK</span>
                </td>

                <!-- PO -->
                <td>
                  <span class="text-xs font-bold text-slate-800">{{ row.data.PO }}</span>
                </td>

                <!-- SKU -->
                <td>
                  <span class="text-xs text-slate-800 font-mono">{{ row.data.SKU }}</span>
                </td>

                <!-- UBICACION -->
                <td>
                  <span class="text-xs text-blue-700 font-semibold">{{ row.data.UBICACION }}</span>
                </td>

                <!-- PZS -->
                <td class="text-right">
                  <span class="text-xs font-bold text-slate-800">{{ row.data.PZS }}</span>
                </td>

                <!-- Detail / Errors -->
                <td>
                  <div v-if="row.errors.length > 0" class="text-danger text-xs">
                    <span v-for="(err, eIdx) in row.errors" :key="eIdx">
                      <i class="fa fa-exclamation-triangle mr-1"></i> {{ err.message }}
                    </span>
                  </div>
                  <div v-else-if="row.excluded" class="text-muted text-xs">
                    Fila excluida
                  </div>
                  <div v-else class="text-success text-xs font-medium">
                    <i class="fa fa-check-circle mr-1"></i> Ubicación y stock disponible en WH/Recepcion
                  </div>
                </td>

              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- Alert / Detail Banner -->
      <div class="alert_details mt-4" v-if="activeRowDetails">
        <h5>Detalles de Fila {{ activeRowDetails.index + 1 }} ({{ activeRowDetails.data.PO }} - {{ activeRowDetails.data.SKU }}):</h5>
        <ul v-if="activeRowDetails.errors.length > 0">
          <li v-for="err in activeRowDetails.errors" :key="err.message" class="text-danger">
            <i class="fa fa-exclamation-triangle mr-1"></i> <strong>[{{ err.field }}]:</strong> {{ err.message }}
          </li>
        </ul>
        <div v-else class="text-success text-sm font-semibold">
          <i class="fa fa-check-circle mr-1"></i> Fila validada correctamente.
        </div>
      </div>

      <!-- Action Footer -->
      <div class="action_buttons mt-6">
        <Button label="Reemplazar archivo" severity="danger" icon="fa fa-upload" outlined @click="resetImport" />
        <Button label="Volver a Validar" severity="info" icon="fa fa-refresh" :loading="store.loading" @click="revalidateRows" />
        <Button label="Crear y Validar Rackeos (STOR)" severity="success" icon="fa fa-check-double" :disabled="store.loading || okRowsCount === 0" @click="processImport" />
      </div>
    </section>

  </div>
</template>

<script>
import Button from 'primevue/button';
import Select from 'primevue/select';
import { useGeneralStore } from '../../store';

export default {
  name: "ImportRackeoHelper",
  props: {
    isModal: {
      type: Boolean,
      default: false
    }
  },
  components: {
    Button,
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
        PO: null,
        SKU: null,
        UBICACION: null,
        PZS: null
      },
      rows: [],
      selectedRow: null,
      collapsedPOs: {},
      selectedStatusFilter: 'all',
      mappingFieldOptions: [
        { label: '[No mapeado]', value: null },
        { label: 'PO (Orden de Compra) * Obligatorio', value: 'PO' },
        { label: 'SKU (Producto) * Obligatorio', value: 'SKU' },
        { label: 'UBICACIÓN (Destino) * Obligatorio', value: 'UBICACION' },
        { label: 'PZS (Cantidad) * Obligatorio', value: 'PZS' }
      ]
    };
  },
  computed: {
    isMappingValid() {
      return this.mapping.PO !== null && this.mapping.SKU !== null && this.mapping.UBICACION !== null && this.mapping.PZS !== null;
    },
    allRowsCount() {
      return this.rows.length;
    },
    errorRowsCount() {
      return this.rows.filter(r => !r.excluded && r.errors && r.errors.length > 0).length;
    },
    excludedRowsCount() {
      return this.rows.filter(r => r.excluded).length;
    },
    okRowsCount() {
      return this.rows.filter(r => !r.excluded && (!r.errors || r.errors.length === 0)).length;
    },
    previewRows() {
      return this.rows.slice(0, 5);
    },
    groupedRowsByPO() {
      const groups = {};
      this.rows.forEach(row => {
        const po = row.data.PO || 'Sin PO';
        if (!groups[po]) {
          groups[po] = {
            name: po,
            rows: [],
            totalPzs: 0
          };
        }
        groups[po].rows.push(row);
      });

      const result = [];
      Object.keys(groups).forEach(key => {
        const group = groups[key];
        
        let filteredRows = group.rows;
        if (this.selectedStatusFilter === 'error') {
          filteredRows = group.rows.filter(r => !r.excluded && r.errors && r.errors.length > 0);
        } else if (this.selectedStatusFilter === 'excluded') {
          filteredRows = group.rows.filter(r => r.excluded);
        } else if (this.selectedStatusFilter === 'ok') {
          filteredRows = group.rows.filter(r => !r.excluded && (!r.errors || r.errors.length === 0));
        }

        if (filteredRows.length > 0) {
          const activeRows = filteredRows.filter(r => !r.excluded);
          const hasErrors = activeRows.some(r => r.errors && r.errors.length > 0);
          const totalPzs = activeRows.reduce((acc, r) => acc + (parseFloat(r.data.PZS) || 0), 0);
          
          result.push({
            name: key,
            rows: filteredRows,
            activeCount: activeRows.length,
            totalPzs,
            hasErrors
          });
        }
      });

      return result;
    },
    activeRowDetails() {
      if (this.selectedRow) {
        const current = this.rows.find(r => r.index === this.selectedRow.index);
        if (current) return current;
      }
      return this.rows.find(r => !r.excluded && r.errors && r.errors.length > 0) || null;
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
        this.selectedFile = file;
      }
    },
    async uploadFile() {
      if (!this.selectedFile) return;
      const res = await this.store.uploadRackeoFile(this.selectedFile, this.hasHeader);
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
      this.collapsedPOs = {};
      this.selectedStatusFilter = 'all';
      
      if (res.mapping && res.mapping.PO !== undefined && res.mapping.SKU !== undefined && res.mapping.UBICACION !== undefined && res.mapping.PZS !== undefined) {
        this.mapping = {
          PO: res.mapping.PO,
          SKU: res.mapping.SKU,
          UBICACION: res.mapping.UBICACION,
          PZS: res.mapping.PZS
        };
        this.currentStep = 3;
      } else {
        this.mapping = {
          PO: res.mapping?.PO ?? null,
          SKU: res.mapping?.SKU ?? null,
          UBICACION: res.mapping?.UBICACION ?? null,
          PZS: res.mapping?.PZS ?? null
        };
        this.currentStep = 2;
      }
    },
    async validateWithMapping() {
      const res = await this.store.uploadRackeoFile(this.selectedFile, this.hasHeader, this.mapping);
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
      this.collapsedPOs = {};
      this.selectedStatusFilter = 'all';
      this.currentStep = 3;
    },
    async revalidateRows() {
      const res = await this.store.callOdoo('import_rackeo_validate_rows', '', { rows: this.rows });
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
    onRowEdit(row) {
      // row edited
    },
    togglePOCollapse(poName) {
      const isCollapsed = this.collapsedPOs[poName] ?? false;
      this.collapsedPOs = {
        ...this.collapsedPOs,
        [poName]: !isCollapsed
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
        PO: null,
        SKU: null,
        UBICACION: null,
        PZS: null
      };
      this.selectedRow = null;
      this.collapsedPOs = {};
      this.selectedStatusFilter = 'all';
      this.currentStep = 1;
    },
    getRowErrorsText(row) {
      return (row.errors || []).map(e => e.message).join('\n');
    },
    async processImport() {
      const res = await this.store.callOdoo('import_rackeo_process', '', { rows: this.rows, headers: this.headers, column_mapping: this.mapping });
      if (res.error) {
        this.store.toast.add({
          severity: 'error',
          summary: 'Error al Procesar Rackeo',
          detail: res.error_msg || 'Error del servidor durante el procesamiento.',
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
          link.download = res.filename || 'retroalimentacion_rackeo.xlsx';
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        } catch (e) {
          console.error("Error al descargar excel de retroalimentación:", e);
        }
      }

      if (res.created_stors && res.created_stors.length > 0) {
        const storNames = res.created_stors.map(s => s.stor_name).join(', ');
        this.store.toast.add({
          severity: 'success',
          summary: 'Rackeo Validado Exitosamente',
          detail: `Se crearon y validaron los siguientes STOR: ${storNames}`,
          life: 8000
        });
      }

      if (res.had_errors) {
        this.store.toast.add({
          severity: 'warn',
          summary: 'Procesamiento Parcial',
          detail: 'Algunas líneas no pudieron procesarse. Consulte el Excel de retroalimentación descargado.',
          life: 8000
        });
      }

      this.$emit('success');
    }
  }
};
</script>

<style scoped>
.import_rackeo_container {
  background: white;
  width: 100%;
  height: 100%;
  max-width: 1400px;
  border-radius: 16px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
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

.header_subtitle {
  font-size: 0.85rem;
  color: #64748b;
  margin: 0.25rem 0 0 0;
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
  margin-bottom: 1.5rem;
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
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.file_label_btn:hover {
  background: #0f172a;
}

.checkbox_label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  color: #334155;
  cursor: pointer;
}

/* Step 2: Mapping */
.info_banner {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1e40af;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
}

.mapping_preview_container {
  flex: 1;
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.preview_table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.preview_table th, .preview_table td {
  border: 1px solid #e2e8f0;
  padding: 0.5rem 0.75rem;
  text-align: left;
}

.selectors_row th {
  background: #f8fafc;
  padding: 0.5rem;
}

.headers_row th {
  background: #0f172a;
  color: white;
  display: table-cell;
}

.column_index {
  display: block;
  font-size: 0.7rem;
  color: #94a3b8;
}

.column_header_name {
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 150px;
  display: inline-block;
}

.required_fields_status {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.status_indicator {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: #ef4444;
  background: #fee2e2;
  padding: 0.4rem 0.8rem;
  border-radius: 6px;
}

.status_indicator.ok {
  color: #16a34a;
  background: #dcfce7;
}

/* Step 3: Manager Table */
.filter_tabs_bar {
  display: flex;
  gap: 0.5rem;
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 0.5rem;
}

.filter_tab {
  background: none;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  color: #64748b;
  transition: all 0.2s;
}

.filter_tab:hover {
  background: #f1f5f9;
}

.filter_tab.active {
  background: #0f172a;
  color: white;
}

.tab_val {
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.75rem;
}

.bg-all { background: #64748b; color: white; }
.bg-danger { background: #ef4444; color: white; }
.bg-secondary { background: #94a3b8; color: white; }
.bg-success { background: #22c55e; color: white; }

.table_scroll_container {
  flex: 1;
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.spreadsheet_table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.spreadsheet_table thead th {
  position: sticky;
  top: 0;
  background: #1e293b;
  color: white;
  padding: 0.6rem 0.75rem;
  text-align: left;
  z-index: 2;
}

.spreadsheet_table tbody td {
  border-bottom: 1px solid #f1f5f9;
  padding: 0.5rem 0.75rem;
}

.po_group_header td {
  background: #f8fafc;
  border-top: 2px solid #cbd5e1;
  border-bottom: 1px solid #cbd5e1;
  padding: 0.6rem 0.75rem;
}

.po_header_content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
}

.po_title {
  font-size: 0.95rem;
  color: #1e293b;
}

.badge {
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 700;
  display: inline-block;
}

.badge-danger { background: #fee2e2; color: #dc2626; }
.badge-success { background: #dcfce7; color: #16a34a; }
.badge-secondary { background: #f1f5f9; color: #64748b; }

.row_excluded {
  opacity: 0.5;
  background: #f8fafc;
}

.row_selected {
  background: #eff6ff !important;
}

.alert_details {
  background: #f8fafc;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 0.75rem 1rem;
}

.alert_details h5 {
  margin: 0 0 0.5rem 0;
  font-size: 0.9rem;
  color: #0f172a;
}

.alert_details ul {
  margin: 0;
  padding-left: 1.2rem;
  font-size: 0.85rem;
}

.action_buttons {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.mt-4 { margin-top: 1rem; }
.mt-6 { margin-top: 1.5rem; }
.mb-4 { margin-bottom: 1rem; }
.mr-1 { margin-right: 0.25rem; }
.mr-2 { margin-right: 0.5rem; }
.ml-2 { margin-left: 0.5rem; }
.text-center { text-align: center; }
.text-right { text-align: right; }
.text-danger { color: #dc2626; }
.text-success { color: #16a34a; }
.text-muted { color: #94a3b8; }
.font-mono { font-family: monospace; }
</style>

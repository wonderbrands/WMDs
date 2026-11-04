<template>
  <div class="list_view">
    <div class="title_section">
      <div class="flex-between">
        <div>
          <h1>{{ store.main_manager_screen.title }}</h1>
          <p>{{ store.main_manager_screen.description }}</p>
        </div>
        <div class="flex-row gap-small">
          <Button icon="fa fa-refresh" severity="secondary" rounded text @click="fetchFilteredData" :loading="store.loading" title="Actualizar lista" />
          <div v-if="store.main_manager_screen.create_by_aggregate" class="flex-row gap-small">
            <Button 
              v-if="store.main_manager_screen.value === 'batch_pick'"
              label="Importar archivo" 
              icon="fa fa-upload" 
              severity="info" 
              @click="showImportHelper = true" 
              class="mr-2"
            />
            <Button 
            :label="store.main_manager_screen.create_by_aggregate.button_string" 
            @click="onRowClick($event, store.main_manager_screen)"/> 
          </div>
          <div v-else-if="store.main_manager_screen.cycle_count" class="flex-row gap-small">
            <Button 
              label="Descargar Reportes" 
              icon="fa fa-file-excel-o" 
              severity="success" 
              class="mr-2"
              @click="openBulkExportDialog" 
              :loading="isDownloadingBulk"
            />
            <Button 
            :label="store.main_manager_screen.cycle_count.button_string" 
            @click="cycleCountCreate($event, store.main_manager_screen)"/> 
          </div>
          <div v-else-if="store.main_manager_screen.create_new">
            <Button 
            :label="store.main_manager_screen.create_new.button_string" 
            @click="onRowClick({data: {}}, store.main_manager_screen)"/> 
          </div>
        </div>
      </div>
    </div>
    <div class="table_wrapper">
      <DataTable
        v-if="server_data"
        lazy
        stripedRows
        paginator
        filterDisplay="row"
        :value="server_data.data"
        :totalRecords="server_data.total_count"
        :rows="pagination.rows"
        :first="pagination.first"
        :sortField="filters.sort_by"
        :sortOrder="filters.sort_order === 'asc' ? 1 : filters.sort_order === 'desc' ? -1 : null"
        @page="onPage"
        @sort="onSort"
        @row-click="onRowClick($event, store.main_manager_screen)"
      >
      <Column
          v-for="col of server_data.map_cols"
          :key="col.field"
          :field="col.field"
          :header="col.name"
          :sortable="col.sortable !== false"
          :showFilterMenu="false"
        >
          <template #filter>
            <Select
              v-if="col.type === 'selectable' && col.filterable !== false"
              v-model="filters[col.field]"
              :options="col.options"
              optionLabel="label"
              optionValue="value"
              :showClear="true"
              placeholder="Filtrar..."
              class="p-column-filter"
              @change="onFilterChange"
            />

            <InputText
              v-else-if="col.filterable !== false"
              v-model="filters[col.field]"
              type="text"
              placeholder="Buscar..."
              class="p-column-filter"
              @input="onFilterChange"
            />
            
            <div v-else style="height: 38px;"></div>
          </template>

          <template #body="slotProps">
            <span v-if="col.field === 'sla_priority_label' && slotProps.data['sla_priority_label']">
              <Tag :severity="getSlaSeverity(slotProps.data['sla_priority_level'])" 
                   :class="{'p-tag-blink': slotProps.data['sla_priority_level'] === 'critical_1h'}">
                <i class="fa fa-clock-o mr-1"></i>{{ slotProps.data['sla_priority_label'] }}
              </Tag>
            </span>

            <Tag v-else-if="col.type === 'selectable'" 
                 :severity="getSeverity(slotProps.data[col.field])" 
                 :value="getLabel(slotProps.data[col.field])" />

            <span v-else-if="col.type === 'one2many'">
              {{ slotProps.data[col.field]?.name || '' }}
            </span>
             <span v-else-if="col.type === 'date' || col.field.includes('date')">
              {{ store.formatDate(slotProps.data[col.field]) }}
            </span>
            <span v-else>
              {{ slotProps.data[col.field] }}
            </span>
          </template>
        </Column>
      </DataTable>
    </div>
    <ImportPicksHelper v-if="showImportHelper" @close="showImportHelper = false" @success="onImportSuccess" />

    <!-- Modal Exportación Masiva de Conteos Cíclicos -->
    <Dialog 
      v-model:visible="bulkDialog.visible" 
      modal 
      header="Descargar Reportes de Conteos Cíclicos" 
      :style="{ width: '520px' }" 
      :breakpoints="{ '640px': '95vw' }"
    >
      <div class="p-fluid flex-column gap-normal" style="padding: 10px 0;">
        <div class="mb-3" style="margin-bottom: 1rem;">
          <label class="font-bold block mb-2" style="font-size: 0.95rem; color: #1e293b; display: block; margin-bottom: 0.5rem;">Modo de Exportación</label>
          <div class="flex-row gap-normal align-center" style="display: flex; gap: 1.5rem; align-items: center;">
            <div class="flex-row align-center gap-small" style="display: flex; align-items: center; cursor: pointer; gap: 0.4rem;" @click="bulkDialog.mode = 'range'">
              <input type="radio" id="mode_range" value="range" v-model="bulkDialog.mode" style="cursor: pointer;" />
              <label for="mode_range" style="cursor: pointer; margin: 0; font-weight: 500;">Por Rango de Fechas (X a Z)</label>
            </div>
            <div class="flex-row align-center gap-small" style="display: flex; align-items: center; cursor: pointer; gap: 0.4rem;" @click="bulkDialog.mode = 'all'">
              <input type="radio" id="mode_all" value="all" v-model="bulkDialog.mode" style="cursor: pointer;" />
              <label for="mode_all" style="cursor: pointer; margin: 0; font-weight: 500;">Todos los Conteos</label>
            </div>
          </div>
        </div>

        <div v-if="bulkDialog.mode === 'range'" class="flex-row gap-normal mb-3" style="display: flex; gap: 1rem; margin-bottom: 1rem;">
          <div style="flex: 1;">
            <label class="font-bold block mb-1" style="font-size: 0.9rem; display: block; margin-bottom: 0.25rem;">Fecha Desde</label>
            <InputText type="date" v-model="bulkDialog.date_from" style="width: 100%;" />
          </div>
          <div style="flex: 1;">
            <label class="font-bold block mb-1" style="font-size: 0.9rem; display: block; margin-bottom: 0.25rem;">Fecha Hasta</label>
            <InputText type="date" v-model="bulkDialog.date_to" style="width: 100%;" />
          </div>
        </div>

        <div class="mb-3" style="margin-bottom: 1rem;">
          <label class="font-bold block mb-1" style="font-size: 0.9rem; display: block; margin-bottom: 0.25rem;">Filtrar por Estado</label>
          <Select 
            v-model="bulkDialog.state" 
            :options="bulkStateOptions" 
            optionLabel="label" 
            optionValue="value" 
            placeholder="Seleccione estado..." 
            style="width: 100%;"
          />
        </div>

        <div style="font-size: 0.85rem; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; line-height: 1.4; color: #475569;">
          <i class="fa fa-info-circle mr-1" style="color: #0284c7;"></i>
          El libro Excel incluirá la <strong>Hoja Resumen</strong> de todos los ciclos y la <strong>Matriz Detallada Consolidada</strong> con teóricos, conteos finales, discrepancias y ajustes de inventario.
        </div>
      </div>

      <template #footer>
        <div class="flex-row justify-end gap-small" style="display: flex; width: 100%; justify-content: flex-end; gap: 0.5rem;">
          <Button label="Cancelar" icon="fa fa-times" text severity="secondary" @click="bulkDialog.visible = false" />
          <Button 
            label="Descargar Excel" 
            icon="fa fa-download" 
            severity="success" 
            :loading="isDownloadingBulk" 
            @click="executeBulkExport" 
          />
        </div>
      </template>
    </Dialog>
  </div>
</template>

<script>
import { useGeneralStore } from "../../store";
import DataTable from "primevue/datatable";
import ImportPicksHelper from "../Forms/ImportPicksHelper.vue";
import Column from "primevue/column";
import InputText from "primevue/inputtext";
import Select from "primevue/select";
import Button from "primevue/button";
import Tag from "primevue/tag";
import Dialog from "primevue/dialog";

export default {
  name: "ListView",

  components: {
    DataTable,
    Column,
    InputText,
    Select, 
    Button,
    Tag,
    Dialog,
    ImportPicksHelper
  },

  data() {
    return {
      store: useGeneralStore(),

      server_data: null,
      showImportHelper: false,

      filters: {
        sort_by: null,
        sort_order: null
      },

      pagination: {
        page: 1,   
        rows: 30, 
        first: 0  
      },

      debounceTimeout: null,

      isDownloadingBulk: false,
      bulkDialog: {
        visible: false,
        mode: 'range',
        date_from: '',
        date_to: '',
        state: 'all'
      },
      bulkStateOptions: [
        { label: 'Todos los estados', value: 'all' },
        { label: 'Solo Finalizados', value: 'finalized' },
        { label: 'En Progreso', value: 'in_progress' },
        { label: 'Borrador', value: 'created' }
      ]
    };
  },

  methods: {
    getSeverity(val) {
      if (val && typeof val === 'object' && val.severity) return val.severity;
      return 'secondary';
    },
    getLabel(val) {
      if (val && typeof val === 'object' && val.label) return val.label;
      return val || '';
    },
    cycleCountCreate(event, modal){
      event.data = event.data || {};
      
      const payload = {
          form_type: "new"
      };

      event.data.cycle_count = modal.cycle_count;
      event.data = {...event.data, ...payload};
      
      const modalContext = modal.form_context_key || modal.value;
      this.store.openModal(modalContext, event);
    },
    onImportSuccess() {
      this.showImportHelper = false;
      this.fetchFilteredData();
    },
    getSlaSeverity(level) {
      switch (level) {
        case 'critical_1h':
        case 'overdue':
          return 'danger';
        case 'urgent_2h':
        case 'warning_6h':
          return 'warn';
        case 'notice_24h':
          return 'info';
        default:
          return 'secondary';
      }
    },
    onRowClick(event, modal) {
      const data = (event && event.data) ? event.data : {};
      if(modal.create_by_aggregate && !data.id){
        const newEvent = { ...event, data: { ...data, create_by_aggregate: modal.create_by_aggregate, form_type: "new" } };
        this.store.openModal(modal.value, newEvent);
      } else {
        const modalContext = modal.form_context_key || modal.value;
        const newEvent = { ...event, data: { ...data, map_cols: this.server_data?.map_cols } };
        this.store.openModal(modalContext, newEvent);
      }
    },

    /* -------------------- SORT -------------------- */
    onSort(event) {
      this.filters.sort_by = event.sortField;
      this.filters.sort_order = event.sortOrder === 1 ? "asc" : "desc";
      this.resetPagination();
      this.fetchFilteredData();
    },

    /* -------------------- PAGE -------------------- */
    onPage(event) {
      this.pagination.first = event.first;
      this.pagination.rows = event.rows;
      this.pagination.page = event.page + 1; // 0-based → 1-based
      this.fetchFilteredData();
    },

    /* -------------------- FILTER -------------------- */
    onFilterChange() {
      this.resetPagination();

      if (this.debounceTimeout) {
        clearTimeout(this.debounceTimeout);
      }

      this.debounceTimeout = setTimeout(() => {
        this.fetchFilteredData();
      }, 500);
    },

    resetPagination() {
      this.pagination.page = 1;
      this.pagination.first = 0;
    },

    /* -------------------- DEFAULT FILTERS -------------------- */
    initializeFilters() {
      if (!this.server_data?.map_cols) return;

      const hasUserFilters = Object.entries(this.filters).some(
        ([key, value]) =>
          !["sort_by", "sort_order"].includes(key) &&
          value !== null &&
          value !== undefined &&
          value !== ""
      );

      if (hasUserFilters) return;

      const defaults = {};

      this.server_data.map_cols.forEach(col => {
        let defaultValue = null;

        if (col.type === "selectable" && col.options) {
          const def = col.options.find(opt => opt.default === true);
          if (def) defaultValue = def.value;
        }

        defaults[col.field] = defaultValue;
      });

      this.filters = {
        ...defaults,
        sort_by: this.filters.sort_by,
        sort_order: this.filters.sort_order
      };
    },

    /* -------------------- FETCH -------------------- */
    async fetchFilteredData() {
      const params = {
        ...this.filters,
        page: this.pagination.page,
        per_page: this.pagination.rows
      };

      console.log(params)
      this.server_data = await this.store.callOdoo(
        this.store.main_manager_screen.value,
        "",
        params
      );
    },

    /* -------------------- INIT -------------------- */
    async getData(context) {

      const params = {
        page: this.pagination.page,
        per_page: this.pagination.rows
      };
      console.log(params)

      this.server_data = await this.store.callOdoo(
        context,
        "",
        params
      );
    },

    openBulkExportDialog() {
      const today = new Date().toISOString().substring(0, 10);
      const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().substring(0, 10);
      this.bulkDialog.mode = 'range';
      this.bulkDialog.date_from = thirtyDaysAgo;
      this.bulkDialog.date_to = today;
      this.bulkDialog.state = 'all';
      this.bulkDialog.visible = true;
    },

    async executeBulkExport() {
      this.isDownloadingBulk = true;
      try {
        const payload = {
          export_all: this.bulkDialog.mode === 'all',
          date_from: this.bulkDialog.mode === 'range' ? this.bulkDialog.date_from : null,
          date_to: this.bulkDialog.mode === 'range' ? this.bulkDialog.date_to : null,
          state: this.bulkDialog.state,
        };

        const res = await this.store.callOdoo("download_bulk_cycle_counts_excel", "", payload);

        if (res && res.ok && res.xlsx_file) {
          const byteCharacters = atob(res.xlsx_file);
          const byteNumbers = new Array(byteCharacters.length);
          for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
          }
          const byteArray = new Uint8Array(byteNumbers);
          const blob = new Blob([byteArray], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
          const link = document.createElement('a');
          link.href = window.URL.createObjectURL(blob);
          link.download = res.filename || 'Reporte_Masivo_Conteos_Ciclicos.xlsx';
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);

          if (this.$toast) {
            this.$toast.add({
              severity: 'success',
              summary: 'Excel Descargado',
              detail: res.message || 'Reporte masivo descargado exitosamente.',
              life: 4000
            });
          }
          this.bulkDialog.visible = false;
        } else {
          if (this.$toast) {
            this.$toast.add({
              severity: 'error',
              summary: 'Error al generar reporte',
              detail: (res && res.error) || 'No se pudo generar el archivo.',
              life: 5000
            });
          }
        }
      } catch (err) {
        console.error("Error al exportar reporte masivo:", err);
        if (this.$toast) {
          this.$toast.add({
            severity: 'error',
            summary: 'Error inesperado',
            detail: String(err),
            life: 5000
          });
        }
      } finally {
        this.isDownloadingBulk = false;
      }
    }
  },

  watch: {
    "store.main_manager_screen": {
      immediate: true,
      deep: true,
      async handler(newVal) {
        if (!newVal?.value) return;

        this.filters = { sort_by: null, sort_order: null };
        this.resetPagination();
        await this.getData(newVal.value);
      }
    }
  },
  async mounted() {
    if (this.store.main_manager_screen?.value) {
      await this.getData(this.store.main_manager_screen.value);
    }

    this.store.$onAction(({name, after})=> {
      if (name === "closeModal"){
        after(async ()=>{
          await this.getData(this.store.main_manager_screen.value);
        })
      }
    })
  }
};
</script>
<style scoped>
.list_view {
    width: 100%;
    height: 100%;
    overflow-y: scroll;
}

.table_wrapper {
    width: 100%;
}

:deep(.p-paginator-content button) {
    width: auto !important;
}

.title_section {
    margin-bottom: 2rem;
}

.flex-between {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.flex-row {
    display: flex;
    align-items: center;
}

.gap-small {
    gap: 0.5rem;
}

@media screen and (max-width: 768px) {
  .flex-between {
    flex-direction: column;
    align-items: flex-start;
    gap: 1rem;
  }
  .title_section {
    margin-bottom: 1rem;
    padding: 0 0.5rem;
  }
  .flex-row {
    width: 100%;
    flex-direction: column;
    gap: 0.5rem;
  }
  .flex-row button {
    width: 100%;
  }
  :deep(.p-datatable-wrapper) {
    overflow-x: auto;
  }
}
</style>
<template>
  <div class="list_view">
    <div class="title_section">
      <h1>{{ store.main_manager_screen.title }}</h1>
      <p>{{ store.main_manager_screen.description }}</p>
      <div v-if="store.main_manager_screen.create_by_aggregate">
        <Button 
        :label="store.main_manager_screen.create_by_aggregate.button_string" /> 
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
          :sortable="true"
          :showFilterMenu="false"
        >
          <template #filter>
            <Select
              v-if="col.type === 'selectable'"
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
              v-else
              v-model="filters[col.field]"
              type="text"
              placeholder="Buscar..."
              class="p-column-filter"
              @input="onFilterChange"
            />
          </template>

          <template #body="slotProps">
            <span v-if="col.type === 'one2many'">
              {{ slotProps.data[col.field]?.name || '' }}
            </span>
            <span v-else>
              {{ slotProps.data[col.field] }}
            </span>
          </template>
        </Column>
      </DataTable>
    </div>
  </div>
</template>

<script>
import { useGeneralStore } from "../../store";
import DataTable from "primevue/datatable";
import Column from "primevue/column";
import InputText from "primevue/inputtext";
import Select from "primevue/select";
import Button from "primevue/button"

export default {
  name: "ListView",

  components: {
    DataTable,
    Column,
    InputText,
    Select, 
    Button
  },

  data() {
    return {
      store: useGeneralStore(),

      server_data: null,

      filters: {
        sort_by: null,
        sort_order: null
      },

      pagination: {
        page: 1,   // backend (1-based)
        rows: 30,  // per page
        first: 0   // PrimeVue (0-based)
      },

      debounceTimeout: null
    };
  },

  methods: {
    /* -------------------- ROW -------------------- */
    onRowClick(event, modal) {
      event.data.map_cols = this.server_data.map_cols;

      if(modal.create_by_aggregate){
        event.data.create_by_aggregate = modal.create_by_aggregate
        event.data.form_type = event.data.map_cols.id ? event.data.map_cols.id : "new"
        this.store.openModal(modal.value, event)
      } else {
        this.store.openModal(modal.value, event);
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
      this.store.loading = true;

      const params = {
        ...this.filters,
        page: this.pagination.page,
        per_page: this.pagination.rows
      };

      console.log(params)
      this.server_data = await this.store.odoo_middleware.getFromOdoo(
        this.store.main_manager_screen.value,
        "",
        params
      );


      this.store.loading = false;
    },

    /* -------------------- INIT -------------------- */
    async getData(context) {

      const params = {
        page: this.pagination.page,
        per_page: this.pagination.rows
      };
      console.log(params)

      this.server_data = await this.store.odoo_middleware.getFromOdoo(
        context,
        "",
        params
      );

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
  }
};
</script>

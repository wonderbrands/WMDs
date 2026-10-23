<template>
  <div class="order-channel-view">
    <!-- Header Title Bar -->
    <div class="header-bar">
      <div class="title-group">
        <i class="fa fa-bullhorn title-icon"></i>
        <div>
          <h2 class="view-title">Canal SLA & Pedidos</h2>
          <p class="view-subtitle">Monitoreo en tiempo real de estatus de pedidos y compromisos de recolección SLA</p>
        </div>
      </div>
      <div class="badges-group">
        <button class="btn-config-sla mr-2" @click="openSlaModal">
          <i class="fa fa-sliders mr-1"></i> Configurar SLA
        </button>
        <div v-if="pendingCount > 0" class="alert-summary-badge pending-badge">
          <i class="fa fa-hourglass-half mr-1"></i>
          <span>{{ pendingCount }} Pendientes <span class="badge-subtitle" v-if="activeChannel !== 'all'">({{ activeChannel }})</span></span>
        </div>
        <div v-if="overdueCount > 0" class="alert-summary-badge overdue-badge">
          <i class="fa fa-exclamation-triangle mr-1"></i>
          <span>{{ overdueCount }} Vencidos</span>
        </div>
        <div v-if="criticalCount > 0" class="alert-summary-badge critical-badge">
          <i class="fa fa-clock-o mr-1"></i>
          <span>{{ criticalCount }} Críticos (&lt; 1h)</span>
        </div>
      </div>
    </div>

    <!-- Main Top Tabs (SLA vs Execution) -->
    <div class="main-tabs-bar">
      <button 
        class="main-tab-btn" 
        :class="{ active: currentMainTab === 'sla' }" 
        @click="switchMainTab('sla')"
      >
        <i class="fa fa-clock-o mr-2"></i> Compromisos SLA & Pendientes
      </button>
      <button 
        class="main-tab-btn" 
        :class="{ active: currentMainTab === 'execution' }" 
        @click="switchMainTab('execution')"
      >
        <i class="fa fa-check-circle mr-2"></i> Operaciones en Almacén (Hecho en el Día)
      </button>
    </div>

    <!-- Filters and Search Toolbar -->
    <div class="toolbar-card">
      <div class="search-input-wrapper">
        <i class="fa fa-search search-icon"></i>
        <input 
          type="text" 
          v-model="searchQuery" 
          @input="onSearchInput"
          @keyup.enter="onSearchEnter"
          :placeholder="currentMainTab === 'sla' ? 'Buscar por Folio SO, Picking, Guía o Cliente...' : 'Buscar por Folio SO, Albarán, Guía o Cliente...'" 
          class="custom-input"
        />
        <button v-if="searchQuery" class="btn-clear" @click="clearSearch">
          <i class="fa fa-times-circle"></i>
        </button>
      </div>

      <!-- Status Filter Chips (For SLA Tab) -->
      <div v-if="currentMainTab === 'sla'" class="filter-chips">
        <button 
          v-for="st in statusOptions" 
          :key="st.value"
          class="chip-button"
          :class="{ active: activeStatus === st.value }"
          @click="setStatusFilter(st.value)"
        >
          {{ st.label }}
        </button>
      </div>

      <!-- Sub-controls for Execution Tab (Matiz Switcher and Stage Chips) -->
      <!-- Sub-controls for Execution Tab (Matiz Switcher, Stage Chips, Fulfillment Filter) -->
      <div v-if="currentMainTab === 'execution'" class="execution-toolbar-sub">
        <div class="matiz-switcher">
          <button 
            class="matiz-btn" 
            :class="{ active: matizMode === 'by_sale' }"
            @click="setMatizMode('by_sale')"
          >
            <i class="fa fa-shopping-cart mr-1"></i> Por Venta (Flujo SO)
          </button>
          <button 
            class="matiz-btn" 
            :class="{ active: matizMode === 'by_stage' }"
            @click="setMatizMode('by_stage')"
          >
            <i class="fa fa-cubes mr-1"></i> Por Etapa de Inventario
          </button>
        </div>

        <div v-if="matizMode === 'by_stage'" class="stage-chips">
          <button 
            v-for="stg in stageOptions" 
            :key="stg.value"
            class="chip-button"
            :class="{ active: stageFilter === stg.value }"
            @click="setStageFilter(stg.value)"
          >
            {{ stg.label }}
          </button>
        </div>

        <!-- Fulfillment Filter (Drop vs Full vs Por Acordar) -->
        <div class="fulfillment-switcher">
          <button 
            class="chip-button"
            :class="{ active: fulfillmentFilter === 'all' }"
            @click="setFulfillmentFilter('all')"
          >
            Todos
          </button>
          <button 
            class="chip-button"
            :class="{ active: fulfillmentFilter === 'drop' }"
            @click="setFulfillmentFilter('drop')"
          >
            <i class="fa fa-home mr-1"></i> Drop
          </button>
          <button 
            class="chip-button"
            :class="{ active: fulfillmentFilter === 'full' }"
            @click="setFulfillmentFilter('full')"
          >
            <i class="fa fa-cubes mr-1"></i> Full
          </button>
          <button 
            class="chip-button"
            :class="{ active: fulfillmentFilter === 'acordar' }"
            @click="setFulfillmentFilter('acordar')"
            title="Ventas DROP sin guía ni paquetería asignada (entrega a acordar con cliente)"
          >
            <i class="fa fa-handshake-o mr-1"></i> Por Acordar
          </button>
        </div>

        <!-- Unconfirmed Filter (Ventas No Confirmadas) -->
        <div class="unconfirmed-switcher">
          <button 
            class="chip-button"
            :class="{ active: unconfirmedFilter === 'all' }"
            @click="setUnconfirmedFilter('all')"
          >
            Todas las Ventas
          </button>
          <button 
            class="chip-button chip-unconfirmed"
            :class="{ active: unconfirmedFilter === 'unconfirmed' }"
            @click="setUnconfirmedFilter('unconfirmed')"
            title="Órdenes en borrador / cotización sin confirmar aún"
          >
            <i class="fa fa-file-text-o mr-1"></i> No Confirmadas
          </button>
          <button 
            class="chip-button"
            :class="{ active: unconfirmedFilter === 'confirmed' }"
            @click="setUnconfirmedFilter('confirmed')"
          >
            <i class="fa fa-check-circle-o mr-1"></i> Confirmadas
          </button>
        </div>
      </div>

      <!-- Channel Select, View Mode, Date Range & Actions -->
      <div class="channel-controls">
        <select v-model="activeChannel" @change="onChannelChange" class="custom-select">
          <option value="all">Todos los Canales {{ currentMainTab === 'sla' && globalOldestDate ? `(${globalOldestDate})` : '' }}</option>
          <option v-for="ch in availableChannels" :key="ch" :value="ch">
            {{ ch }} {{ currentMainTab === 'sla' && channelOldestDate[ch] ? `(${channelOldestDate[ch]})` : '' }}
          </option>
        </select>

        <!-- Date Range Filter with Explicit Labels -->
        <div class="date-filter-group" :class="{ 'filter-bypassed': currentMainTab === 'sla' && activeStatus === 'no_sla' }">
          <span class="date-filter-label">Desde:</span>
          <input
            v-model="dateFrom"
            type="date"
            class="custom-select date-filter"
            :disabled="currentMainTab === 'sla' && activeStatus === 'no_sla'"
            @change="onDateChange"
            :title="currentMainTab === 'sla' && activeStatus === 'no_sla' ? 'Filtro de fechas omitido para pedidos Sin SLA' : 'Fecha desde'"
          />
        </div>
        <div class="date-filter-group" :class="{ 'filter-bypassed': currentMainTab === 'sla' && activeStatus === 'no_sla' }">
          <span class="date-filter-label">Hasta:</span>
          <input
            v-model="dateTo"
            type="date"
            class="custom-select date-filter"
            :disabled="currentMainTab === 'sla' && activeStatus === 'no_sla'"
            @change="onDateChange"
            :title="currentMainTab === 'sla' && activeStatus === 'no_sla' ? 'Filtro de fechas omitido para pedidos Sin SLA' : 'Fecha hasta'"
          />
        </div>
        <span v-if="currentMainTab === 'sla' && activeStatus === 'no_sla'" class="badge-bypassed-dates">
          <i class="fa fa-info-circle mr-1"></i>Sin límite de fecha
        </span>

        <!-- View Mode Switcher -->
        <div class="view-mode-toggle">
          <button 
            class="btn-toggle" 
            :class="{ active: viewMode === 'grid' }" 
            @click="viewMode = 'grid'" 
            title="Vista Cuadrícula / Tarjetas"
          >
            <i class="fa fa-th-large"></i>
          </button>
          <button 
            class="btn-toggle" 
            :class="{ active: viewMode === 'list' }" 
            @click="viewMode = 'list'" 
            title="Vista Lista / Tabla"
          >
            <i class="fa fa-list"></i>
          </button>
        </div>

        <!-- Excel Export Button -->
        <button 
          class="btn-export-excel" 
          @click="exportToExcel" 
          :disabled="isExporting" 
          title="Exportar datos actuales a Excel (.xlsx)"
        >
          <i class="fa fa-file-excel-o mr-1" :class="{'fa-spin': isExporting}"></i>
          <span>Excel</span>
        </button>

        <button class="btn-refresh" @click="fetchAll" title="Actualizar Datos">
          <i class="fa fa-refresh" :class="{'fa-spin': isRefreshing}"></i>
        </button>
      </div>
    </div>

    <!-- Bulk SLA Action Bar (Sticky notification when items selected) -->
    <div v-if="currentMainTab === 'sla' && selectedOrderIds.length > 0" class="bulk-action-bar">
      <div class="bulk-info">
        <i class="fa fa-check-square-o mr-2"></i>
        <span><strong>{{ selectedOrderIds.length }}</strong> pedido(s) seleccionado(s)</span>
      </div>
      <div class="bulk-buttons">
        <button class="btn btn-warning btn-sm font-weight-bold" @click="openBulkReassignModal">
          <i class="fa fa-calendar-plus-o mr-1"></i> Empujar SLA Seleccionados
        </button>
        <button class="btn btn-outline-secondary btn-sm ml-2" @click="selectedOrderIds = []">
          <i class="fa fa-times mr-1"></i> Deseleccionar
        </button>
      </div>
    </div>

    <!-- SLA Metrics Cards (SLA Tab) -->
    <div v-if="currentMainTab === 'sla'" class="metrics-bar">
      <div class="metric-card" title="Total de pedidos (OUT) con fecha SLA dentro del rango de fechas seleccionado, sin importar estado.">
        <div class="metric-value">{{ metrics.pedidos }}</div>
        <div class="metric-label">Pedidos</div>
      </div>
      <div class="metric-card metric-hover" title="OUT cerrados (state = done). Incluye los entregados, sin importar si la fecha de envío cayó dentro del rango.">
        <div class="metric-value metric-sent">{{ metrics.enviados }}</div>
        <div class="metric-label">Enviados</div>
      </div>
      <div class="metric-card metric-hover" title="OUT no cerrados (state != done). Pueden estar pendientes, en flujo, o entregados pero sin cerrar el OUT.">
        <div class="metric-value metric-pending">{{ metrics.no_enviados }}</div>
        <div class="metric-label">No enviados</div>
      </div>
      <div class="metric-card metric-hover" title="De los no enviados: OUT con movimientos sin stock reservado (en espera de abastecimiento).">
        <div class="metric-value metric-waiting">{{ metrics.en_espera }}</div>
        <div class="metric-label">En espera (sin stock)</div>
      </div>
      <div class="metric-note" title="Entregados cuyo OUT aún no se cierra (tienen fecha de envío pero state != done). Por eso no siempre cuadran con la vista de pedidos pendientes.">
        <i class="fa fa-info-circle mr-1"></i>
        <strong>{{ metrics.sin_out_cerrado }}</strong> Enviado/entregado sin OUT cerrado
      </div>
    </div>

    <!-- Execution Metrics Cards (Execution Tab) - Interactivas y Deduplicadas -->
    <div v-if="currentMainTab === 'execution'" class="metrics-bar">
      <div 
        class="metric-card metric-clickable" 
        :class="{ active: matizMode === 'by_stage' && stageFilter === 'PICK' }"
        @click="filterByStageMetric('PICK')"
        title="Albaranes PICK completados en el rango. Clic para filtrar albaranes de recolección."
      >
        <div class="metric-value text-primary">{{ executedMetrics.picked_count }}</div>
        <div class="metric-label"><i class="fa fa-cube mr-1"></i> Pickeados</div>
      </div>
      <div 
        class="metric-card metric-clickable" 
        :class="{ active: matizMode === 'by_stage' && stageFilter === 'PACK' }"
        @click="filterByStageMetric('PACK')"
        title="Albaranes PACK completados en el rango. Clic para filtrar albaranes de empaque."
      >
        <div class="metric-value text-info">{{ executedMetrics.packed_count }}</div>
        <div class="metric-label"><i class="fa fa-archive mr-1"></i> Empacados</div>
      </div>
      <div 
        class="metric-card metric-clickable" 
        :class="{ active: matizMode === 'by_stage' && stageFilter === 'OUT' }"
        @click="filterByStageMetric('OUT')"
        title="Órdenes de venta con albarán OUT completado en el rango. Clic para filtrar albaranes de despacho."
      >
        <div class="metric-value metric-sent">{{ executedMetrics.orders_dispatched_count }}</div>
        <div class="metric-label"><i class="fa fa-truck mr-1"></i> Órdenes Despachadas</div>
      </div>
      <div 
        class="metric-card metric-clickable" 
        :class="{ active: matizMode === 'by_sale' }"
        @click="filterByStageMetric('ALL_SALES')"
        title="Total de órdenes de venta procesadas en el rango. Clic para ver el listado de ventas."
      >
        <div class="metric-value">{{ executedMetrics.total_orders_touched }}</div>
        <div class="metric-label"><i class="fa fa-check-square-o mr-1"></i> Órdenes Procesadas</div>
      </div>
    </div>

    <!-- Data Display Content -->
    <div class="content-body">
      <!-- 1. SLA TAB CONTENT -->
      <div v-if="currentMainTab === 'sla'">
        <div v-if="isRefreshing && orders.length === 0" class="state-message">
          <i class="fa fa-spinner fa-spin fa-2x mb-2"></i>
          <p>Cargando información de pedidos...</p>
        </div>

        <div v-else-if="orders.length === 0" class="state-message">
          <i class="fa fa-inbox fa-3x mb-2 text-muted"></i>
          <p>No se encontraron pedidos con los criterios de búsqueda aplicados.</p>
        </div>

        <!-- 1. Grid Cards View -->
        <div v-else-if="viewMode === 'grid'" class="orders-grid">
          <div 
            v-for="ord in orders" 
            :key="ord.id" 
            class="order-data-card"
            :class="{'card-alert-critical': ord.sla_priority_level === 'critical_1h' || ord.sla_priority_level === 'overdue'}"
          >
            <!-- Top Row: Order Name, Channel & Actions -->
            <div class="card-row-top">
              <div class="d-flex align-items-center">
                <input 
                  type="checkbox" 
                  :value="ord.id" 
                  v-model="selectedOrderIds" 
                  class="mr-2 card-checkbox" 
                  @click.stop
                  title="Seleccionar pedido para empujar SLA"
                />
                <span class="so-number">{{ ord.sale_order_name || ord.name }}</span>
                <span v-if="ord.is_unconfirmed" class="badge-unconfirmed-sub ml-1" title="Venta no confirmada en Odoo">Borrador</span>
              </div>
              <div class="top-badges">
                <span v-if="ord.is_acordar" class="badge-acordar-sub mr-1" title="Venta por acordar con cliente (sin guía)">
                  <i class="fa fa-handshake-o mr-1"></i>Por Acordar
                </span>
                <span v-else-if="ord.fulfillment" class="fulfillment-pill mr-1">
                  {{ ord.fulfillment.toUpperCase() }}
                </span>
                <span class="channel-pill" :class="getChannelClass(ord.channel)">
                  {{ ord.channel || 'Manuales' }}
                </span>
                <button 
                  class="btn-reassign-icon ml-1" 
                  @click.stop="openReassignModal(ord)" 
                  title="Reasignar / Empujar fecha límite SLA"
                >
                  <i class="fa fa-calendar-plus-o"></i>
                </button>
              </div>
            </div>

            <!-- Odoo Entry Date Row -->
            <div v-if="ord.create_date_local" class="odoo-entry-box" title="Fecha y hora de entrada de la venta a Odoo">
              <i class="fa fa-sign-in mr-1 text-primary"></i>
              <span class="text-muted">Ingreso a Odoo: </span>
              <strong>{{ ord.create_date_local }}</strong>
            </div>

            <!-- Middle Row: Latest Registered Picking & WMDS Log Hover -->
            <div class="card-row-sub">
              <span 
                v-if="ord.has_pick"
                class="pick-code-wrapper"
                :title="ord.latest_wmds_log ? ('Último log WMDS (' + (ord.latest_wmds_log_date || '') + ' - ' + (ord.latest_wmds_log_user || 'Sistema') + '):\n' + ord.latest_wmds_log) : 'Sin logs WMDS registrados para este traslado'"
              >
                <i class="fa fa-cube mr-1 text-primary"></i>
                <span class="pick-name">Último Traslado: <strong>{{ ord.name }}</strong></span>
                <i v-if="ord.latest_wmds_log" class="fa fa-info-circle ml-1 log-hover-icon"></i>
              </span>
              <span v-else class="no-pick-badge">
                <i class="fa fa-cube mr-1"></i> Sin pick asignado
              </span>
            </div>

            <!-- Carrier / Paquetería Row -->
            <div class="carrier-info-box">
              <span class="carrier-tag" :class="ord.carrier ? 'carrier-assigned' : 'carrier-unassigned'">
                <i class="fa fa-truck mr-1"></i>
                <span>{{ ord.carrier || 'Sin paquetería' }}</span>
              </span>
            </div>

            <!-- SLA Priority Row -->
            <div v-if="ord.sla_priority_label || ord.sla_date" class="sla-info-box">
              <div class="sla-status-tag" :class="ord.sla_priority_level || 'normal'">
                <i class="fa fa-clock-o mr-1"></i>
                <span>{{ ord.sla_priority_label || 'SLA Programado' }}</span>
              </div>
              <span v-if="ord.sla_date" class="sla-timestamp">
                Límite: {{ formatSlaTime(ord.sla_date, ord.sla_timezone) }}
              </span>
            </div>
            <div v-else class="sla-info-box">
              <div class="sla-status-tag" style="color: #6b7280;">
                <i class="fa fa-question-circle mr-1"></i>
                <span>SLA aún no definido</span>
              </div>
            </div>

            <!-- Manual SLA Override Badge (si fue reasignado) -->
            <div 
              v-if="ord.sla_manual_override" 
              class="manual-override-pill"
              :title="'Reasignado por: ' + (ord.sla_override_user || 'Usuario') + '\nFecha: ' + (ord.sla_override_date || '') + '\nSLA original: ' + (ord.sla_original_date || 'N/A') + (ord.sla_override_note ? ('\nNota: ' + ord.sla_override_note) : '')"
            >
              <i class="fa fa-refresh mr-1 text-warning"></i>
              <span>Reasignado: {{ ord.sla_override_reason_label || 'Manual' }}</span>
            </div>
          </div>
        </div>

        <!-- 2. Table List View -->
        <div v-else-if="viewMode === 'list'" class="orders-table-wrapper">
          <table class="orders-table">
            <thead>
              <tr>
                <th style="width: 40px; text-align: center;">
                  <input type="checkbox" :checked="isAllSelected" @change="toggleSelectAll" title="Seleccionar todos los pedidos"/>
                </th>
                <th>Pedido</th>
                <th>Canal / Modalidad</th>
                <th>Ingreso Odoo</th>
                <th>Último Traslado</th>
                <th>Paquetería</th>
                <th>Estado SLA</th>
                <th>Límite SLA (México)</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              <tr 
                v-for="ord in orders" 
                :key="ord.id"
                :class="{'row-alert-critical': ord.sla_priority_level === 'critical_1h' || ord.sla_priority_level === 'overdue', 'row-selected': selectedOrderIds.includes(ord.id)}"
              >
                <td style="text-align: center;" @click.stop>
                  <input type="checkbox" :value="ord.id" v-model="selectedOrderIds"/>
                </td>
                <td>
                  <strong>{{ ord.sale_order_name || ord.name }}</strong>
                  <span v-if="ord.is_unconfirmed" class="badge-unconfirmed-sub ml-1" title="Venta no confirmada en Odoo">Borrador</span>
                </td>
                <td>
                  <span class="channel-pill" :class="getChannelClass(ord.channel)">
                    {{ ord.channel || 'Manuales' }}
                  </span>
                  <span v-if="ord.is_acordar" class="badge-acordar-sub ml-1" title="Venta por acordar con cliente (sin guía)">
                    <i class="fa fa-handshake-o mr-1"></i>Por Acordar
                  </span>
                  <span v-else-if="ord.fulfillment" class="fulfillment-subpill ml-1">
                    {{ ord.fulfillment.toUpperCase() }}
                  </span>
                </td>
                <td>
                  <span v-if="ord.create_date_local" class="odoo-entry-text" title="Entrada a Odoo">
                    <i class="fa fa-sign-in mr-1 text-muted"></i>
                    {{ ord.create_date_local }}
                  </span>
                  <span v-else class="text-muted">-</span>
                </td>
                <td>
                  <span 
                    v-if="ord.has_pick"
                    class="pick-code-wrapper"
                    :title="ord.latest_wmds_log ? ('Último log WMDS (' + (ord.latest_wmds_log_date || '') + ' - ' + (ord.latest_wmds_log_user || 'Sistema') + '):\n' + ord.latest_wmds_log) : 'Sin logs WMDS registrados para este traslado'"
                  >
                    <i class="fa fa-cube mr-1 text-primary"></i>
                    <span>{{ ord.name }}</span>
                    <i v-if="ord.latest_wmds_log" class="fa fa-info-circle ml-1 log-hover-icon"></i>
                  </span>
                  <span v-else class="no-pick-badge">
                    <i class="fa fa-cube mr-1"></i> Sin pick asignado
                  </span>
                </td>
                <td>
                  <span class="carrier-tag" :class="ord.carrier ? 'carrier-assigned' : 'carrier-unassigned'">
                    <i class="fa fa-truck mr-1"></i>
                    {{ ord.carrier || 'Sin paquetería' }}
                  </span>
                </td>
                <td>
                  <div v-if="ord.sla_priority_label || ord.sla_date" class="sla-status-tag" :class="ord.sla_priority_level || 'normal'">
                    <i class="fa fa-clock-o mr-1"></i>
                    <span>{{ ord.sla_priority_label || 'Programado' }}</span>
                  </div>
                  <span v-else class="text-muted font-italic">Sin SLA</span>

                  <div 
                    v-if="ord.sla_manual_override" 
                    class="manual-override-table-tag mt-1"
                    :title="'Reasignado por ' + (ord.sla_override_user || 'Usuario') + (ord.sla_override_note ? (': ' + ord.sla_override_note) : '')"
                  >
                    <i class="fa fa-refresh mr-1 text-warning"></i>
                    {{ ord.sla_override_reason_label || 'Reasignado' }}
                  </div>
                </td>
                <td>
                  <span v-if="ord.sla_date" class="sla-timestamp-table">
                    {{ formatSlaTime(ord.sla_date, ord.sla_timezone) }}
                  </span>
                  <span v-else class="text-muted">-</span>
                </td>
                <td>
                  <button 
                    class="btn-action-reassign" 
                    @click.stop="openReassignModal(ord)" 
                    title="Reasignar / Empujar fecha límite SLA"
                  >
                    <i class="fa fa-calendar-plus-o mr-1"></i> Empujar
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- SLA Pagination Footer Bar -->
        <div v-if="orders.length > 0 || totalCount > 0" class="pagination-bar">
          <div class="pagination-info">
            Mostrando <strong>{{ paginationFrom }} - {{ paginationTo }}</strong> de <strong>{{ totalCount }}</strong> pedidos
          </div>
          <div class="pagination-controls">
            <button 
              class="btn-page" 
              :disabled="currentPage <= 1 || isRefreshing" 
              @click="goToPage(currentPage - 1)"
              title="Página Anterior"
            >
              <i class="fa fa-chevron-left mr-1"></i> Anterior
            </button>
            <span class="page-current">Pág. {{ currentPage }} de {{ totalPages }}</span>
            <button 
              class="btn-page" 
              :disabled="currentPage >= totalPages || isRefreshing" 
              @click="goToPage(currentPage + 1)"
              title="Página Siguiente"
            >
              Siguiente <i class="fa fa-chevron-right ml-1"></i>
            </button>
          </div>
        </div>
      </div>

      <!-- 2. EXECUTION TAB CONTENT -->
      <div v-else-if="currentMainTab === 'execution'">
        <div v-if="isRefreshing && executedResults.length === 0" class="state-message">
          <i class="fa fa-spinner fa-spin fa-2x mb-2"></i>
          <p>Cargando operaciones realizadas...</p>
        </div>

        <div v-else-if="executedResults.length === 0" class="state-message">
          <i class="fa fa-inbox fa-3x mb-2 text-muted"></i>
          <p>No se encontraron operaciones ejecutadas en la fecha o criterios seleccionados.</p>
        </div>

        <!-- Matiz A: Por Venta -->
        <div v-else-if="matizMode === 'by_sale'">
          <!-- Grid Mode -->
          <div v-if="viewMode === 'grid'" class="orders-grid">
            <div 
              v-for="so in executedResults" 
              :key="so.sale_id" 
              class="order-data-card exec-card"
            >
              <div class="card-row-top">
                <span class="so-number">{{ so.so_name }}</span>
                <div>
                  <span v-if="so.fulfillment" class="fulfillment-pill mr-1">
                    {{ so.fulfillment.toUpperCase() }}
                  </span>
                  <span class="channel-pill" :class="getChannelClass(so.channel)">
                    {{ so.channel || 'Manuales' }}
                  </span>
                </div>
              </div>
              <div class="card-row-sub">
                <span class="text-muted"><i class="fa fa-user mr-1"></i>{{ so.partner_name || 'Cliente' }}</span>
                <span v-if="so.carrier_name" class="carrier-mini-tag"><i class="fa fa-truck mr-1"></i>{{ so.carrier_name }}</span>
              </div>
              
              <div class="wmds-status-row">
                <span class="wmds-badge" :class="'wmds-' + (so.wmds_status_value || 'default')">
                  <i class="fa fa-tag mr-1"></i>{{ so.wmds_status_name || 'Sin Estado WMDS' }}
                </span>
              </div>

              <!-- Pipeline 3 Pasos Stepper -->
              <div class="exec-pipeline-stepper">
                <div class="pipeline-step" :class="{ 'step-done': so.stages.pick.state === 'done' }">
                  <div class="step-icon"><i class="fa fa-cube"></i></div>
                  <div class="step-text">
                    <strong>Pick</strong>
                    <span v-if="so.stages.pick.state === 'done'" class="step-sub">{{ so.stages.pick.operator_name || so.stages.pick.batch_name || 'Hecho' }}</span>
                    <span v-else class="step-sub text-muted">Pendiente</span>
                  </div>
                </div>
                <div class="pipeline-arrow"><i class="fa fa-chevron-right"></i></div>
                <div class="pipeline-step" :class="{ 'step-done': so.stages.pack.state === 'done' }">
                  <div class="step-icon"><i class="fa fa-archive"></i></div>
                  <div class="step-text">
                    <strong>Pack</strong>
                    <span v-if="so.stages.pack.state === 'done'" class="step-sub">{{ so.stages.pack.operator_name || 'Hecho' }}</span>
                    <span v-else class="step-sub text-muted">Pendiente</span>
                  </div>
                </div>
                <div class="pipeline-arrow"><i class="fa fa-chevron-right"></i></div>
                <div class="pipeline-step" :class="{ 'step-done': so.stages.out.state === 'done' }">
                  <div class="step-icon"><i class="fa fa-truck"></i></div>
                  <div class="step-text">
                    <strong>OUT</strong>
                    <span v-if="so.stages.out.state === 'done'" class="step-sub">{{ so.stages.out.carrier_name || 'Despachado' }}</span>
                    <span v-else class="step-sub text-muted">Pendiente</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Table Mode -->
          <div v-else-if="viewMode === 'list'" class="orders-table-wrapper">
            <table class="orders-table">
              <thead>
                <tr>
                  <th>Pedido</th>
                  <th>Canal</th>
                  <th>Fulfillment</th>
                  <th>Cliente</th>
                  <th>Estado WMDS</th>
                  <th>Fase Pick</th>
                  <th>Fase Pack</th>
                  <th>Fase OUT</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="so in executedResults" :key="so.sale_id">
                  <td><strong>{{ so.so_name }}</strong></td>
                  <td><span class="channel-pill" :class="getChannelClass(so.channel)">{{ so.channel || 'Manuales' }}</span></td>
                  <td>
                    <span v-if="so.fulfillment" class="fulfillment-subpill">
                      {{ so.fulfillment.toUpperCase() }}
                    </span>
                    <span v-else class="text-muted">-</span>
                  </td>
                  <td>{{ so.partner_name }}</td>
                  <td>
                    <span class="wmds-badge" :class="'wmds-' + (so.wmds_status_value || 'default')">
                      {{ so.wmds_status_name || 'Sin Estado' }}
                    </span>
                  </td>
                  <td>
                    <span v-if="so.stages.pick.state === 'done'" class="stage-pill-done">
                      <i class="fa fa-check mr-1"></i>{{ so.stages.pick.operator_name || so.stages.pick.batch_name || 'Hecho' }}
                      <small class="text-muted block-sub" v-if="so.stages.pick.date_done">{{ formatSlaDate(so.stages.pick.date_done) }}</small>
                    </span>
                    <span v-else class="text-muted font-italic">Pendiente</span>
                  </td>
                  <td>
                    <span v-if="so.stages.pack.state === 'done'" class="stage-pill-done">
                      <i class="fa fa-check mr-1"></i>{{ so.stages.pack.operator_name || 'Hecho' }}
                      <small class="text-muted block-sub" v-if="so.stages.pack.date_done">{{ formatSlaDate(so.stages.pack.date_done) }}</small>
                    </span>
                    <span v-else class="text-muted font-italic">Pendiente</span>
                  </td>
                  <td>
                    <span v-if="so.stages.out.state === 'done'" class="stage-pill-done stage-pill-out">
                      <i class="fa fa-truck mr-1"></i>{{ so.stages.out.carrier_name || 'Despachado' }}
                      <small class="text-muted block-sub" v-if="so.stages.out.date_done">{{ formatSlaDate(so.stages.out.date_done) }}</small>
                    </span>
                    <span v-else class="text-muted font-italic">Pendiente</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Matiz B: Por Etapa de Inventario -->
        <div v-else-if="matizMode === 'by_stage'" class="orders-table-wrapper">
          <table class="orders-table">
            <thead>
              <tr>
                <th>Hora Fin (CDMX)</th>
                <th>Etapa</th>
                <th>Albarán</th>
                <th>Pedido</th>
                <th>Canal</th>
                <th>Fulfillment</th>
                <th>Lote Batch / Operador</th>
                <th>Paquetería & Guía</th>
                <th>Estado WMDS</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in executedResults" :key="item.id">
                <td><strong>{{ formatSlaDate(item.date_done) }}</strong></td>
                <td>
                  <span class="stage-badge" :class="'stage-' + (item.stage ? item.stage.toLowerCase() : 'unknown')">
                    {{ item.stage_label || item.stage || '-' }}
                  </span>
                </td>
                <td><code>{{ item.name }}</code></td>
                <td><strong>{{ item.so_name }}</strong></td>
                <td><span class="channel-pill" :class="getChannelClass(item.channel)">{{ item.channel || 'Manuales' }}</span></td>
                <td>
                  <span v-if="item.fulfillment" class="fulfillment-subpill">
                    {{ item.fulfillment.toUpperCase() }}
                  </span>
                  <span v-else class="text-muted">-</span>
                </td>
                <td>
                  <div>
                    <span v-if="item.batch_name" class="batch-badge mr-1"><i class="fa fa-tags mr-1"></i>{{ item.batch_name }}</span>
                    <span v-if="item.operator_name" class="operator-txt"><i class="fa fa-user mr-1"></i>{{ item.operator_name }}</span>
                    <span v-if="!item.batch_name && !item.operator_name" class="text-muted">-</span>
                  </div>
                </td>
                <td>
                  <div v-if="item.carrier_name || item.carrier_tracking_ref">
                    <span v-if="item.carrier_name" class="carrier-tag carrier-assigned mr-1">{{ item.carrier_name }}</span>
                    <span v-if="item.carrier_tracking_ref" class="text-muted"><small>{{ item.carrier_tracking_ref }}</small></span>
                  </div>
                  <span v-else class="text-muted">-</span>
                </td>
                <td>
                  <span class="wmds-badge-sm">{{ item.wmds_status_name || '-' }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Execution Pagination Footer Bar -->
        <div v-if="executedResults.length > 0 || executedTotalCount > 0" class="pagination-bar">
          <div class="pagination-info">
            Mostrando <strong>{{ executedPaginationFrom }} - {{ executedPaginationTo }}</strong> de <strong>{{ executedTotalCount }}</strong> registros
          </div>
          <div class="pagination-controls">
            <button 
              class="btn-page" 
              :disabled="executedCurrentPage <= 1 || isRefreshing" 
              @click="goToExecutedPage(executedCurrentPage - 1)"
              title="Página Anterior"
            >
              <i class="fa fa-chevron-left mr-1"></i> Anterior
            </button>
            <span class="page-current">Pág. {{ executedCurrentPage }} de {{ executedTotalPages }}</span>
            <button 
              class="btn-page" 
              :disabled="executedCurrentPage >= executedTotalPages || isRefreshing" 
              @click="goToExecutedPage(executedCurrentPage + 1)"
              title="Página Siguiente"
            >
              Siguiente <i class="fa fa-chevron-right ml-1"></i>
            </button>
          </div>
        </div>
      </div>

    <!-- Reassign SLA Modal (Single & Bulk) -->
    <div v-if="showReassignModal" class="modal-backdrop" @click.self="closeReassignModal">
      <div class="modal-card reassign-modal-card">
        <div class="modal-header">
          <h3 class="modal-title">
            <i class="fa fa-clock-o mr-2 text-warning"></i>
            {{ isBulkReassign ? 'Reasignar / Empujar SLA en Bloque' : 'Reasignar / Empujar SLA Manualmente' }}
          </h3>
          <button class="btn-modal-close" @click="closeReassignModal"><i class="fa fa-times"></i></button>
        </div>

        <div class="modal-body" v-if="reassignTarget || isBulkReassign">
          <div v-if="isBulkReassign" class="reassign-target-summary mb-3 p-3 bg-light rounded border">
            <div><i class="fa fa-cubes text-primary mr-1"></i><strong>Empuje Masivo:</strong> {{ selectedOrderIds.length }} pedido(s) seleccionado(s)</div>
            <small class="text-muted">Se reprogramará la fecha límite de SLA para las órdenes seleccionadas.</small>
          </div>
          <div v-else-if="reassignTarget" class="reassign-target-summary mb-3 p-3 bg-light rounded border">
            <div><strong>Orden / Picking:</strong> {{ reassignTarget.sale_order_name || reassignTarget.sale_name || reassignTarget.name }} <span v-if="(reassignTarget.sale_order_name || reassignTarget.sale_name) && reassignTarget.name">({{ reassignTarget.name }})</span></div>
            <div><strong>Canal / Marketplace:</strong> {{ reassignTarget.channel_label || reassignTarget.channel || 'N/A' }}</div>
            <div><strong>SLA Actual:</strong> {{ reassignTarget.sla_display || formatSlaTime(reassignTarget.sla_date, reassignTarget.sla_timezone) || 'Sin SLA' }}</div>
          </div>

          <form @submit.prevent="saveReassignSla" class="reassign-form">
            <div v-if="isBulkReassign && bulkAvailableMarketplaces.length > 0" class="form-group mb-3">
              <label class="form-label font-weight-bold">Parametrizar por Marketplace</label>
              <select class="form-control" v-model="reassignForm.marketplace">
                <option value="all">Todos los marketplaces de los pedidos seleccionados</option>
                <option v-for="mp in bulkAvailableMarketplaces" :key="mp" :value="mp">{{ mp }}</option>
              </select>
              <small class="form-text text-muted">Aplica el cambio exclusivamente a los pedidos de este canal.</small>
            </div>

            <div class="form-group mb-3">
              <label class="form-label font-weight-bold">Nueva Fecha / Hora Límite SLA <span class="text-danger">*</span></label>
              <input 
                type="datetime-local" 
                class="form-control" 
                v-model="reassignForm.new_sla_date" 
                required 
              />
              <small class="form-text text-muted">Hora local de entrega límite estimada para no penalizar SLA.</small>
            </div>

            <div class="form-group mb-3">
              <label class="form-label font-weight-bold">Motivo del Empuje <span class="text-danger">*</span></label>
              <select class="form-control" v-model="reassignForm.reason" required>
                <option value="no_space">Falta de espacio en unidad de transporte / colecta</option>
                <option value="carrier_cutoff">Corte de paquetería / retraso de recolección</option>
                <option value="platform_rescheduled">Reprogramado por marketplace / plataforma</option>
                <option value="warehouse_delay">Operación de almacén reprogramada</option>
                <option value="customer_request">Solicitud de cliente / comprador</option>
                <option value="other">Otro motivo</option>
              </select>
            </div>

            <div class="form-group mb-3">
              <label class="form-label font-weight-bold">Nota / Justificación Adicional</label>
              <textarea 
                class="form-control" 
                v-model="reassignForm.note" 
                rows="3" 
                placeholder="Detalle el motivo del aplazamiento..."
              ></textarea>
            </div>

            <div class="modal-footer d-flex justify-content-end gap-2 pt-3 border-top">
              <button type="button" class="btn btn-secondary mr-2" @click="closeReassignModal" :disabled="isReassigning">
                Cancelar
              </button>
              <button type="submit" class="btn btn-primary" :disabled="isReassigning">
                <i v-if="isReassigning" class="fa fa-spinner fa-spin mr-1"></i>
                <i v-else class="fa fa-check mr-1"></i>
                {{ isBulkReassign ? 'Aplicar Empuje Masivo' : 'Confirmar Reasignación' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- SLA Configuration Modal -->
    <div v-if="showSlaModal" class="modal-backdrop" @click.self="closeSlaModal">
      <div class="modal-card">
        <div class="modal-header">
          <h3 class="modal-title"><i class="fa fa-sliders mr-2 text-primary"></i>Configuración de Horarios SLA por Marketplace</h3>
          <button class="btn-modal-close" @click="closeSlaModal"><i class="fa fa-times"></i></button>
        </div>

        <div class="modal-body">
          <div class="modal-actions-bar">
            <p class="section-desc">Gestiona las reglas de SLA para marketplaces que no provienen de Yuju o requieren cálculo por horario.</p>
            <button class="btn-primary-sm" @click="prepareNewRule">
              <i class="fa fa-plus mr-1"></i> Nueva Regla SLA
            </button>
          </div>

          <!-- Rules Table -->
          <div class="table-responsive mb-3">
            <table class="rules-table">
              <thead>
                <tr>
                  <th>Marketplace</th>
                  <th>Origen SLA</th>
                  <th>Lun-Vie</th>
                  <th>Sáb</th>
                  <th>Dom</th>
                  <th>Flex</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="schedulesLoading">
                  <td colspan="7" class="text-center py-3"><i class="fa fa-spinner fa-spin mr-1"></i> Cargando reglas...</td>
                </tr>
                <tr v-else-if="schedulesList.length === 0">
                  <td colspan="7" class="text-center py-3 text-muted">No hay reglas SLA configuradas. Haz clic en "Nueva Regla SLA" para agregar una.</td>
                </tr>
                <tr v-for="rule in schedulesList" :key="rule.id" :class="{ 'row-editing': formRule.id === rule.id }">
                  <td><strong>{{ rule.marketplace }}</strong></td>
                  <td>
                    <span class="badge-source" :class="rule.sla_source">
                      {{ getSlaSourceLabel(rule.sla_source) }}
                    </span>
                  </td>
                  <td>{{ rule.monday_to_friday_ }}h</td>
                  <td>{{ rule.saturday }}h</td>
                  <td>{{ rule.sunday }}h</td>
                  <td>{{ rule.flex || 0 }}m</td>
                  <td class="action-buttons">
                    <button class="btn-icon text-info mr-2" @click="editRule(rule)" title="Editar"><i class="fa fa-pencil"></i></button>
                    <button class="btn-icon text-danger" @click="deleteRule(rule.id)" title="Eliminar"><i class="fa fa-trash"></i></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Rule Edit / Form Panel -->
          <div v-if="showRuleForm" class="rule-form-card">
            <h4 class="form-title">
              {{ formRule.id ? 'Editar Regla SLA - ' + formRule.marketplace : 'Nueva Regla SLA por Marketplace' }}
            </h4>

            <div class="form-grid">
              <div class="form-group">
                <label>Marketplace:</label>
                <select v-model="formRule.marketplace" class="custom-select-sm">
                  <option value="" disabled>Selecciona un Marketplace</option>
                  <option v-for="ch in availableChannels" :key="ch" :value="ch">{{ ch }}</option>
                </select>
              </div>

              <div class="form-group">
                <label>Origen de SLA:</label>
                <select v-model="formRule.sla_source" class="custom-select-sm">
                  <option value="auto">Automático / Híbrido (Yuju si existe, si no Calcular)</option>
                  <option value="yuju">Yuju (Fecha Límite Marketplace)</option>
                  <option value="calculated">Cálculo por Horario (SLA Schedule)</option>
                </select>
              </div>

              <div class="form-group">
                <label>Lunes a Viernes (Horas a sumar):</label>
                <input type="number" step="0.5" min="0" v-model.number="formRule.monday_to_friday_" class="custom-input-sm" />
              </div>

              <div class="form-group">
                <label>Sábado (Horas a sumar):</label>
                <input type="number" step="0.5" min="0" v-model.number="formRule.saturday" class="custom-input-sm" />
              </div>

              <div class="form-group">
                <label>Domingo (Horas a sumar):</label>
                <input type="number" step="0.5" min="0" v-model.number="formRule.sunday" class="custom-input-sm" />
              </div>

              <div class="form-group" v-if="isMercadoLibreForm">
                <label>Flex (Minutos - Mercado Libre):</label>
                <input type="number" min="0" v-model.number="formRule.flex" class="custom-input-sm" />
              </div>

              <div class="form-group checkbox-group">
                <label class="checkbox-label">
                  <input type="checkbox" v-model="formRule.auto_fill_dates" />
                  Auto-completar Priority Date
                </label>
              </div>
            </div>

            <div class="form-actions">
              <button class="btn-secondary-sm mr-2" @click="showRuleForm = false">Cancelar</button>
              <button class="btn-primary-sm" @click="saveRule" :disabled="isSavingRule">
                <i class="fa fa-save mr-1"></i> Guardar Regla
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  </div>
</template>

<script>
import { useGeneralStore } from "../../store/index";

export default {
  name: "OrderChannelView",
  data() {
    return {
      store: useGeneralStore(),
      isRefreshing: false,
      searchQuery: "",
      searchTimeout: null,
      currentMainTab: "sla", // "sla" | "execution"
      matizMode: "by_sale", // "by_sale" | "by_stage"
      stageFilter: "all", // "all" | "PICK" | "PACK" | "OUT"
      fulfillmentFilter: "all", // "all" | "drop" | "full" | "acordar"
      unconfirmedFilter: "all", // "all" | "unconfirmed" | "confirmed"
      selectedOrderIds: [],
      isBulkReassign: false,
      activeStatus: "all",
      activeChannel: "all",
      viewMode: "grid", // "grid" o "list"
      dateFrom: "",
      dateTo: "",
      isExporting: false,
      showReassignModal: false,
      reassignTarget: null,
      isReassigning: false,
      reassignForm: {
        new_sla_date: "",
        reason: "no_space",
        note: "",
        marketplace: "all"
      },
      metrics: {
        pedidos: 0,
        enviados: 0,
        no_enviados: 0,
        en_espera: 0,
        sin_out_cerrado: 0
      },
      executedMetrics: {
        picked_count: 0,
        packed_count: 0,
        dispatched_count: 0,
        orders_dispatched_count: 0,
        total_orders_touched: 0
      },
      availableChannels: [],
      orders: [],
      totalCount: 0,
      currentPage: 1,
      pageSize: 50,
      executedResults: [],
      executedTotalCount: 0,
      executedCurrentPage: 1,
      executedPageSize: 50,
      criticalCount: 0,
      overdueCount: 0,
      pendingCount: 0,
      totalPendingAll: 0,
      marketplacePending: {},
      channelOldestDate: {},
      timerId: null,

      // Modal SLA Config
      showSlaModal: false,
      schedulesLoading: false,
      schedulesList: [],
      showRuleForm: false,
      isSavingRule: false,
      formRule: {
        id: null,
        marketplace: "",
        sla_source: "auto",
        monday_to_friday_: 24,
        saturday: 0,
        sunday: 0,
        flex: 0,
        sameDay_nextDay: 0,
        auto_fill_dates: false
      }
    };
  },
  computed: {
    totalPages() {
      return Math.max(1, Math.ceil(this.totalCount / this.pageSize));
    },
    isAllSelected() {
      if (!this.orders || this.orders.length === 0) return false;
      return this.orders.every(o => this.selectedOrderIds.includes(o.id));
    },
    bulkAvailableMarketplaces() {
      if (!this.selectedOrderIds || this.selectedOrderIds.length === 0) return [];
      const channels = new Set();
      this.orders.forEach(o => {
        if (this.selectedOrderIds.includes(o.id) && o.channel) {
          channels.add(o.channel.trim());
        }
      });
      return Array.from(channels).sort();
    },
    paginationFrom() {
      if (this.totalCount === 0 || this.orders.length === 0) return 0;
      return (this.currentPage - 1) * this.pageSize + 1;
    },
    paginationTo() {
      return Math.min(this.totalCount, (this.currentPage - 1) * this.pageSize + this.orders.length);
    },
    executedTotalPages() {
      return Math.max(1, Math.ceil(this.executedTotalCount / this.executedPageSize));
    },
    executedPaginationFrom() {
      if (this.executedTotalCount === 0 || this.executedResults.length === 0) return 0;
      return (this.executedCurrentPage - 1) * this.executedPageSize + 1;
    },
    executedPaginationTo() {
      return Math.min(this.executedTotalCount, (this.executedCurrentPage - 1) * this.executedPageSize + this.executedResults.length);
    },
    stageOptions() {
      return [
        { label: "Todos", value: "all" },
        { label: "Solo Pick", value: "PICK" },
        { label: "Solo Pack", value: "PACK" },
        { label: "Solo OUT", value: "OUT" }
      ];
    },
    globalOldestDate() {
      let oldest = null;
      Object.values(this.channelOldestDate).forEach((d) => {
        if (d && (!oldest || d < oldest)) oldest = d;
      });
      return oldest ? this.formatSlaDate(oldest) : "";
    },
    statusOptions() {
      return [
        { label: "Todos", value: "all" },
        { label: "Sin SLA Definido", value: "no_sla" },
        { label: "Vencidos", value: "overdue" },
        { label: "Críticos (< 1h)", value: "critical_1h" },
        { label: "Urgentes (< 2h)", value: "urgent_2h" },
        { label: "Advertencia (< 6h)", value: "warning_6h" },
        { label: "En Tiempo (< 24h)", value: "notice_24h" },
        { label: "Normal (> 24h)", value: "normal" }
      ];
    },
    isMercadoLibreForm() {
      if (!this.formRule.marketplace) return false;
      const m = this.formRule.marketplace.toLowerCase();
      return m.includes("mercado") || m.includes("meli");
    }
  },
  methods: {
    switchMainTab(tab) {
      if (this.currentMainTab === tab) return;
      this.currentMainTab = tab;
      this.fetchAll();
    },
    setMatizMode(m) {
      if (this.matizMode === m) return;
      this.matizMode = m;
      this.executedCurrentPage = 1;
      this.fetchExecutionData();
    },
    setStageFilter(stg) {
      if (this.stageFilter === stg) return;
      this.stageFilter = stg;
      this.executedCurrentPage = 1;
      this.fetchExecutionData();
    },
    goToExecutedPage(pg) {
      if (pg < 1 || pg > this.executedTotalPages || pg === this.executedCurrentPage) return;
      this.executedCurrentPage = pg;
      this.fetchExecutionData();
    },
    setStatusFilter(val) {
      this.activeStatus = val;
      this.currentPage = 1;
      this.fetchOrders();
    },
    onSearchEnter() {
      if (this.currentMainTab === 'sla') {
        this.currentPage = 1;
        this.fetchOrders();
      } else {
        this.executedCurrentPage = 1;
        this.fetchExecutionData();
      }
    },
    onSearchInput() {
      if (this.searchTimeout) clearTimeout(this.searchTimeout);
      this.searchTimeout = setTimeout(() => {
        if (this.currentMainTab === 'sla') {
          this.currentPage = 1;
          this.fetchOrders();
        } else {
          this.executedCurrentPage = 1;
          this.fetchExecutionData();
        }
      }, 400);
    },
    clearSearch() {
      this.searchQuery = "";
      if (this.currentMainTab === 'sla') {
        this.currentPage = 1;
        this.fetchOrders();
      } else {
        this.executedCurrentPage = 1;
        this.fetchExecutionData();
      }
    },
    onChannelChange() {
      this.currentPage = 1;
      this.executedCurrentPage = 1;
      this.fetchAll();
      this.checkExpiringAlerts();
    },
    onDateChange() {
      this.currentPage = 1;
      this.executedCurrentPage = 1;
      this.fetchAll();
    },
    async fetchAll() {
      this.store.loading = true;
      this.isRefreshing = true;
      try {
        if (this.currentMainTab === 'sla') {
          await Promise.all([this.fetchOrders(), this.fetchMetrics()]);
        } else {
          await Promise.all([this.fetchExecutionMetrics(), this.fetchExecutionData()]);
        }
      } finally {
        this.store.loading = false;
        this.isRefreshing = false;
      }
    },
    goToPage(pg) {
      if (pg < 1 || pg > this.totalPages || pg === this.currentPage) return;
      this.currentPage = pg;
      this.fetchOrders();
    },
    toggleSelectAll(e) {
      if (e.target.checked) {
        const ids = this.orders.map(o => o.id);
        this.selectedOrderIds = Array.from(new Set([...this.selectedOrderIds, ...ids]));
      } else {
        const pageIds = new Set(this.orders.map(o => o.id));
        this.selectedOrderIds = this.selectedOrderIds.filter(id => !pageIds.has(id));
      }
    },
    setUnconfirmedFilter(val) {
      if (this.unconfirmedFilter === val) return;
      this.unconfirmedFilter = val;
      this.currentPage = 1;
      this.selectedOrderIds = [];
      this.fetchAll();
    },
    openBulkReassignModal() {
      if (!this.selectedOrderIds || this.selectedOrderIds.length === 0) return;
      this.isBulkReassign = true;
      this.reassignTarget = null;
      const d = new Date();
      d.setDate(d.getDate() + 1);
      d.setHours(15, 0, 0, 0);
      this.reassignForm = {
        new_sla_date: d.toISOString().slice(0, 16),
        reason: "no_space",
        note: "",
        marketplace: "all"
      };
      this.showReassignModal = true;
    },
    async fetchOrders() {
      this.store.loading = true;
      this.isRefreshing = true;
      try {
        const dateFromParam = (this.currentMainTab === 'sla' && this.activeStatus === 'no_sla') ? '' : this.dateFrom;
        const dateToParam = (this.currentMainTab === 'sla' && this.activeStatus === 'no_sla') ? '' : this.dateTo;
        const res = await this.store.callOdooSilent("order_channel_query", "", {
          query: this.searchQuery,
          status_filter: this.activeStatus,
          channel_filter: this.activeChannel,
          fulfillment_filter: this.fulfillmentFilter,
          unconfirmed_filter: this.unconfirmedFilter,
          date_from: dateFromParam,
          date_to: dateToParam,
          limit: this.pageSize,
          page: this.currentPage
        });

        if (res) {
          if (res.results) {
            this.orders = res.results;
          } else {
            this.orders = [];
          }
          if (res.total_count !== undefined) {
            this.totalCount = res.total_count;
          } else {
            this.totalCount = this.orders.length;
          }
          if (res.available_channels && Array.isArray(res.available_channels) && res.available_channels.length > 0) {
            this.availableChannels = res.available_channels;
          }
          if (res.channel_oldest_date) {
            this.channelOldestDate = res.channel_oldest_date;
          }
        }
      } catch (e) {
        console.error("Error al consultar el canal de pedidos:", e);
      } finally {
        this.isRefreshing = false;
        this.store.loading = false;
      }
    },
    async fetchMetrics() {
      try {
        const res = await this.store.callOdooSilent("order_sla_metrics", "", {
          date_from: this.dateFrom,
          date_to: this.dateTo,
          channel_filter: this.activeChannel,
          fulfillment_filter: this.fulfillmentFilter,
          unconfirmed_filter: this.unconfirmedFilter
        });
        if (res && res.success) {
          this.metrics = {
            pedidos: res.total_orders || 0,
            enviados: res.sent_orders || 0,
            no_enviados: res.pending_orders || 0,
            en_espera: res.waiting_orders || 0,
            sin_out_cerrado: res.delivered_out_not_closed || 0
          };
        }
      } catch (e) {
        console.error("Error al obtener métricas SLA:", e);
      }
    },
    setFulfillmentFilter(val) {
      if (this.fulfillmentFilter === val) return;
      this.fulfillmentFilter = val;
      this.currentPage = 1;
      this.executedCurrentPage = 1;
      this.selectedOrderIds = [];
      this.fetchAll();
    },
    filterByStageMetric(metricKey) {
      if (metricKey === 'ALL_SALES') {
        this.matizMode = 'by_sale';
        this.stageFilter = 'all';
      } else {
        this.matizMode = 'by_stage';
        if (this.stageFilter === metricKey) {
          this.stageFilter = 'all';
        } else {
          this.stageFilter = metricKey;
        }
      }
      this.executedCurrentPage = 1;
      this.fetchExecutionData();
    },
    async exportToExcel() {
      this.isExporting = true;
      try {
        const dateFromParam = (this.currentMainTab === 'sla' && this.activeStatus === 'no_sla') ? '' : this.dateFrom;
        const dateToParam = (this.currentMainTab === 'sla' && this.activeStatus === 'no_sla') ? '' : this.dateTo;
        const params = {
          tab: this.currentMainTab,
          query: this.searchQuery,
          channel_filter: this.activeChannel,
          date_from: dateFromParam,
          date_to: dateToParam
        };
        if (this.currentMainTab === 'sla') {
          params.status_filter = this.activeStatus;
        } else {
          params.matiz_mode = this.matizMode;
          params.stage_filter = this.stageFilter;
          params.fulfillment_filter = this.fulfillmentFilter;
        }

        const res = await this.store.callOdooSilent("export_order_channel_excel", "", params);
        if (res && (res.ok || res.success) && res.xlsx_file) {
          const byteCharacters = atob(res.xlsx_file);
          const byteNumbers = new Array(byteCharacters.length);
          for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
          }
          const byteArray = new Uint8Array(byteNumbers);
          const blob = new Blob([byteArray], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.style.display = "none";
          a.href = url;
          a.download = res.filename || `export_${this.currentMainTab}.xlsx`;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          a.remove();
        } else {
          alert((res && (res.error?.message || res.error)) || "Error al exportar archivo Excel");
        }
      } catch (e) {
        console.error("Error al exportar Excel:", e);
        alert("Error al exportar archivo Excel");
      } finally {
        this.isExporting = false;
      }
    },
    openReassignModal(item) {
      this.isBulkReassign = false;
      this.reassignTarget = item;
      let defaultDate = "";
      if (item.sla_date) {
        try {
          defaultDate = String(item.sla_date).replace(" ", "T").slice(0, 16);
        } catch(e) {}
      }
      if (!defaultDate) {
        const d = new Date();
        d.setDate(d.getDate() + 1);
        d.setHours(15, 0, 0, 0);
        defaultDate = d.toISOString().slice(0, 16);
      }
      this.reassignForm = {
        new_sla_date: defaultDate,
        reason: item.sla_override_reason || "no_space",
        note: item.sla_override_note || "",
        marketplace: "all"
      };
      this.showReassignModal = true;
    },
    closeReassignModal() {
      this.showReassignModal = false;
      this.reassignTarget = null;
      this.isBulkReassign = false;
    },
    async saveReassignSla() {
      if (!this.reassignForm.new_sla_date) {
        alert("Por favor defina la nueva fecha SLA");
        return;
      }
      this.isReassigning = true;
      try {
        let res = null;
        if (this.isBulkReassign) {
          res = await this.store.callOdooSilent("bulk_reassign_sla", "", {
            order_ids: this.selectedOrderIds,
            new_sla_date: this.reassignForm.new_sla_date.replace("T", " ") + ":00",
            reason: this.reassignForm.reason,
            note: this.reassignForm.note,
            marketplace: this.reassignForm.marketplace
          });
        } else {
          if (!this.reassignTarget) return;
          res = await this.store.callOdooSilent("reassign_sla", "", {
            order_id: this.reassignTarget.id,
            pick_id: this.reassignTarget.pick_id,
            new_sla_date: this.reassignForm.new_sla_date.replace("T", " ") + ":00",
            reason: this.reassignForm.reason,
            note: this.reassignForm.note
          });
        }

        if (res && res.success) {
          if (this.$toast) {
            this.$toast.add({
              severity: "success",
              summary: "SLA Reasignado",
              detail: res.message || "SLA reasignado exitosamente",
              life: 4000
            });
          }
          this.closeReassignModal();
          this.selectedOrderIds = [];
          this.fetchAll();
        } else {
          alert((res && (res.error?.message || res.error)) || "Error al reasignar SLA");
        }
      } catch (e) {
        console.error("Error al reasignar SLA:", e);
        alert("Error al comunicarse con el servidor");
      } finally {
        this.isReassigning = false;
      }
    },
    async fetchExecutionMetrics() {
      try {
        const res = await this.store.callOdooSilent("executed_operations_metrics", "", {
          date_from: this.dateFrom,
          date_to: this.dateTo,
          channel_filter: this.activeChannel,
          fulfillment_filter: this.fulfillmentFilter
        });
        if (res && res.success) {
          this.executedMetrics = {
            picked_count: res.picked_count || 0,
            packed_count: res.packed_count || 0,
            dispatched_count: res.dispatched_count || 0,
            orders_dispatched_count: res.orders_dispatched_count || 0,
            total_orders_touched: res.total_orders_touched || 0
          };
        }
      } catch (e) {
        console.error("Error al obtener métricas de ejecución:", e);
      }
    },
    async fetchExecutionData() {
      this.store.loading = true;
      this.isRefreshing = true;
      try {
        const res = await this.store.callOdooSilent("executed_operations_query", "", {
          query: this.searchQuery,
          channel_filter: this.activeChannel,
          date_from: this.dateFrom,
          date_to: this.dateTo,
          matiz_mode: this.matizMode,
          stage_filter: this.stageFilter,
          fulfillment_filter: this.fulfillmentFilter,
          limit: this.executedPageSize,
          page: this.executedCurrentPage
        });
        if (res && res.success) {
          this.executedResults = res.results || [];
          this.executedTotalCount = res.total_count !== undefined ? res.total_count : this.executedResults.length;
        } else {
          this.executedResults = [];
          this.executedTotalCount = 0;
        }
      } catch (e) {
        console.error("Error al consultar operaciones ejecutadas:", e);
        this.executedResults = [];
        this.executedTotalCount = 0;
      } finally {
        this.store.loading = false;
        this.isRefreshing = false;
      }
    },
    async checkExpiringAlerts() {
      try {
        const res = await this.store.callOdooSilent("sla_expiring_alerts", "", {
          channel_filter: this.activeChannel
        });
        if (res && res.success) {
          const prevCount = this.criticalCount;
          this.criticalCount = res.critical_count !== undefined ? res.critical_count : 0;
          this.overdueCount = res.overdue_count !== undefined ? res.overdue_count : 0;
          this.pendingCount = res.current_channel_pending !== undefined ? res.current_channel_pending : (res.total_pending || 0);
          this.totalPendingAll = res.total_pending !== undefined ? res.total_pending : 0;
          if (res.marketplace_pending) {
            this.marketplacePending = res.marketplace_pending;
          }

          this.store.sla_critical_count = this.criticalCount;
          this.store.sla_overdue_count = this.overdueCount;

          if (this.criticalCount > prevCount && this.criticalCount > 0) {
            this.$toast.add({
              severity: "warn",
              summary: "ALERTA DE RECOLECCIÓN SLA",
              detail: `Hay ${this.criticalCount} pedido(s) con vencimiento en menos de 1 hora.`,
              life: 7000
            });
          }
        }
      } catch (e) {
        console.error("Error al verificar alertas SLA:", e);
      }
    },

    // Modal SLA Management
    async openSlaModal() {
      this.showSlaModal = true;
      await this.fetchSchedules();
    },
    closeSlaModal() {
      this.showSlaModal = false;
      this.showRuleForm = false;
    },
    async fetchSchedules() {
      this.schedulesLoading = true;
      try {
        const res = await this.store.callOdooSilent("get_marketplace_schedules", "", {});
        if (res && res.success) {
          this.schedulesList = res.schedules || [];
          if (res.available_channels && Array.isArray(res.available_channels)) {
            this.availableChannels = res.available_channels;
          }
        }
      } catch (e) {
        console.error("Error cargando horarios SLA:", e);
      } finally {
        this.schedulesLoading = false;
      }
    },
    prepareNewRule() {
      this.formRule = {
        id: null,
        marketplace: this.availableChannels.length > 0 ? this.availableChannels[0] : "",
        sla_source: "auto",
        monday_to_friday_: 24,
        saturday: 0,
        sunday: 0,
        flex: 0,
        sameDay_nextDay: 0,
        auto_fill_dates: false
      };
      this.showRuleForm = true;
    },
    editRule(rule) {
      this.formRule = { ...rule };
      this.showRuleForm = true;
    },
    async saveRule() {
      if (!this.formRule.marketplace) return;
      this.isSavingRule = true;
      try {
        const res = await this.store.callOdooSilent("save_marketplace_schedule", "", { data: this.formRule });
        if (res && res.success) {
          await this.fetchSchedules();
          this.showRuleForm = false;
          this.fetchOrders();
        }
      } catch (e) {
        console.error("Error guardando regla SLA:", e);
      } finally {
        this.isSavingRule = false;
      }
    },
    async deleteRule(id) {
      if (!confirm("¿Eliminar esta regla de SLA?")) return;
      try {
        const res = await this.store.callOdooSilent("delete_marketplace_schedule", "", { id });
        if (res && res.success) {
          await this.fetchSchedules();
          this.fetchOrders();
        }
      } catch (e) {
        console.error("Error eliminando regla SLA:", e);
      }
    },
    getSlaSourceLabel(src) {
      switch (src) {
        case "auto": return "Automático / Yuju";
        case "yuju": return "Yuju";
        case "calculated": return "Calculado";
        default: return src || "Auto";
      }
    },
    formatCutoffTime(val) {
      if (val === undefined || val === null) return "17:00";
      const hrs = Math.floor(val);
      const mins = Math.round((val - hrs) * 60);
      return `${String(hrs).padStart(2, "0")}:${String(mins).padStart(2, "0")}`;
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
    formatSlaDate(dtStr) {
      if (!dtStr) return "";
      const clean = String(dtStr).trim().replace("T", " ");
      const m = clean.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2}):(\d{2})/);
      if (m) {
        const [, y, mo, d, h, mi] = m;
        return `${d}/${mo}/${y} ${h}:${mi}`;
      }
      return clean.slice(0, 16);
    },
    formatSlaTime(dtStr, tz) {
      if (!dtStr) return "";
      try {
        // tz 'local' => el sla_date del marketplace ya está en hora local (ej. Mercado Libre).
        // tz 'utc' (default) => sla_date en UTC, se convierte a CDMX.
        if (tz === 'local') {
          const clean = String(dtStr).replace("T", " ").split(".")[0];
          const m = clean.match(/^(\d{4})-(\d{2})-(\d{2}) (\d{1,2}):(\d{2})(?::(\d{2}))?/);
          if (m) {
            const [y, mo, d, h, mi, s] = [m[1], m[2], m[3], m[4], m[5], m[6] || "00"];
            return `${d}/${mo}/${y}, ${h.padStart(2, "0")}:${mi} ${Number(h) >= 12 ? "p.m." : "a.m."}`;
          }
          return clean;
        }
        const dt = new Date(dtStr.endsWith("Z") ? dtStr : dtStr + "Z");
        return dt.toLocaleString("es-MX", { 
          timeZone: "America/Mexico_City",
          day: '2-digit', 
          month: '2-digit', 
          year: 'numeric', 
          hour: '2-digit', 
          minute: '2-digit' 
        });
      } catch (e) {
        return dtStr;
      }
    }
  },
  mounted() {
    const today = new Date().toLocaleDateString("sv-SE", { timeZone: "America/Mexico_City" });
    this.dateFrom = today;
    this.dateTo = today;
    this.fetchAll();
    this.checkExpiringAlerts();
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
.order-channel-view {
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
  margin-bottom: 16px;
  width: 100%;
}
.title-group {
  display: flex;
  align-items: center;
  gap: 12px;
}
.title-icon {
  font-size: 1.8rem;
  color: #d97706;
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
.badges-group {
  display: flex;
  align-items: center;
}
.btn-config-sla {
  background: #4f46e5;
  color: #ffffff;
  border: none;
  padding: 7px 14px;
  border-radius: 6px;
  font-weight: 600;
  font-size: 0.85rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  transition: background-color 0.2s;
}
.btn-config-sla:hover {
  background: #4338ca;
}
.alert-summary-badge {
  background-color: #ef4444;
  color: #ffffff;
  padding: 6px 14px;
  border-radius: 20px;
  font-weight: 700;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  box-shadow: 0 2px 4px rgba(239, 68, 68, 0.2);
  margin-left: 8px;
}
.pending-badge {
  background-color: #2563eb;
  box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2);
}
.overdue-badge {
  background-color: #dc2626;
}
.critical-badge {
  background-color: #f59e0b;
}
.badge-subtitle {
  font-weight: 500;
  opacity: 0.9;
  margin-left: 2px;
}

.toolbar-card {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
}
.search-input-wrapper {
  position: relative;
  flex: 1;
  min-width: 250px;
}
.search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: #9ca3af;
}
.custom-input {
  width: 100%;
  padding: 8px 32px 8px 34px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 0.9rem;
  outline: none;
}
.custom-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}
.btn-clear {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: #9ca3af;
  cursor: pointer;
}

.filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.chip-button {
  background: #ffffff;
  border: 1px solid #d1d5db;
  color: #374151;
  padding: 6px 12px;
  border-radius: 16px;
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}
.chip-button:hover {
  background: #f3f4f6;
}
.chip-button.active {
  background: #2563eb;
  color: #ffffff;
  border-color: #2563eb;
}
.chip-badge {
  margin-left: 4px;
  font-size: 0.75rem;
  opacity: 0.9;
}

.channel-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}
.date-filter {
  max-width: 150px;
}
.no-pick-badge {
  display: inline-flex;
  align-items: center;
  background: #fef3c7;
  color: #92400e;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 0.78rem;
  font-weight: 600;
}

.metrics-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}
.metric-card {
  flex: 1;
  min-width: 140px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px 16px;
  text-align: center;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.metric-value {
  font-size: 1.7rem;
  font-weight: 700;
  color: #111827;
  line-height: 1.2;
}
.metric-sent { color: #059669; }
.metric-pending { color: #dc2626; }
.metric-waiting { color: #d97706; }
.metric-label {
  font-size: 0.8rem;
  color: #6b7280;
  font-weight: 600;
  margin-top: 4px;
}
.metric-hover {
  cursor: help;
}
.metric-note {
  flex-basis: 100%;
  display: inline-flex;
  align-items: center;
  font-size: 0.8rem;
  color: #92400e;
  background: #fef3c7;
  border: 1px dashed #f59e0b;
  border-radius: 6px;
  padding: 6px 12px;
  cursor: help;
}
.view-mode-toggle {
  display: flex;
  background: #e5e7eb;
  border-radius: 6px;
  padding: 2px;
  gap: 2px;
}
.btn-toggle {
  background: none;
  border: none;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 0.85rem;
  color: #4b5563;
  cursor: pointer;
  transition: all 0.15s ease;
}
.btn-toggle:hover {
  color: #111827;
}
.btn-toggle.active {
  background: #ffffff;
  color: #2563eb;
  box-shadow: 0 1px 2px rgba(0,0,0,0.08);
}
.filter-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: #4b5563;
}
.custom-select {
  padding: 6px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 0.85rem;
  background-color: #ffffff;
  outline: none;
}
.btn-refresh {
  background: #ffffff;
  border: 1px solid #d1d5db;
  padding: 6px 10px;
  border-radius: 6px;
  color: #4b5563;
  cursor: pointer;
}
.btn-refresh:hover {
  background: #f3f4f6;
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

.orders-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
  padding-bottom: 16px;
}

.order-data-card {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.order-data-card:hover {
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
  transform: translateY(-2px);
}
.card-alert-critical {
  border-left: 4px solid #ef4444;
}

.card-row-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.so-number {
  font-weight: 700;
  font-size: 1.05rem;
  color: #111827;
}

.channel-pill {
  padding: 3px 8px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
}
.ch-meli { background: #ffe600; color: #2d3277; }
.ch-coppel { background: #fff100; color: #0055a5; }
.ch-tiktok { background: #000000; color: #ffffff; }
.ch-amazon { background: #ff9900; color: #111111; }
.ch-walmart { background: #0071ce; color: #ffffff; }
.ch-shopify { background: #95bf47; color: #ffffff; }
.ch-default { background: #e5e7eb; color: #374151; }

.card-row-sub {
  font-size: 0.85rem;
  color: #4b5563;
}
.pick-code-wrapper {
  display: inline-flex;
  align-items: center;
  cursor: pointer;
}
.log-hover-icon {
  color: #3b82f6;
  font-size: 0.85rem;
}
.carrier-info-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  background: #f1f5f9;
  padding: 5px 10px;
  border-radius: 6px;
  font-size: 0.78rem;
}
.carrier-tag {
  display: inline-flex;
  align-items: center;
  font-weight: 600;
  max-width: 170px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.carrier-assigned {
  color: #1e40af;
}
.carrier-unassigned {
  color: #94a3b8;
  font-style: italic;
  font-weight: 500;
}
.tracking-tag {
  color: #475569;
  font-family: monospace;
  font-size: 0.74rem;
  background: #e2e8f0;
  padding: 2px 6px;
  border-radius: 4px;
  max-width: 130px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sla-info-box {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #f8fafc;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 0.8rem;
}
.sla-status-tag {
  font-weight: 600;
  display: flex;
  align-items: center;
}
.sla-status-tag.critical_1h { color: #dc2626; }
.sla-status-tag.urgent_2h { color: #d97706; }
.sla-status-tag.warning_6h { color: #b45309; }
.sla-status-tag.notice_24h { color: #2563eb; }
.sla-status-tag.normal { color: #059669; }
.sla-status-tag.overdue { color: #991b1b; }

.sla-timestamp {
  font-size: 0.75rem;
  color: #64748b;
  font-weight: 500;
}

.yuju-due-box {
  font-size: 0.78rem;
  color: #475569;
}

/* Orders Table Styles */
.orders-table-wrapper {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow-x: auto;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.orders-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
  text-align: left;
}
.orders-table thead th {
  background: #f9fafb;
  padding: 10px 14px;
  font-weight: 600;
  color: #374151;
  border-bottom: 1px solid #e5e7eb;
  white-space: nowrap;
}
.orders-table tbody td {
  padding: 10px 14px;
  border-bottom: 1px solid #f3f4f6;
  color: #1f2937;
  vertical-align: middle;
}
.orders-table tbody tr:hover {
  background: #f8fafc;
}
.orders-table tbody tr.row-alert-critical {
  background-color: #fef2f2;
}
.sla-timestamp-table {
  font-weight: 500;
  color: #4b5563;
  white-space: nowrap;
}
.badge-due {
  display: inline-block;
  background: #f1f5f9;
  color: #475569;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-family: monospace;
}

/* Pagination Styles */
.pagination-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  margin-top: 16px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.03);
}
.pagination-info {
  font-size: 0.85rem;
  color: #4b5563;
}
.pagination-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}
.btn-page {
  display: inline-flex;
  align-items: center;
  padding: 6px 14px;
  background-color: #f9fafb;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 500;
  color: #374151;
  cursor: pointer;
  transition: all 0.15s ease;
}
.btn-page:hover:not(:disabled) {
  background-color: #f3f4f6;
  border-color: #9ca3af;
  color: #111827;
}
.btn-page:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background-color: #f3f4f6;
}
.page-current {
  font-size: 0.85rem;
  font-weight: 600;
  color: #1f2937;
}

/* Modal CSS */
.modal-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}
.modal-card {
  background: #ffffff;
  border-radius: 12px;
  width: 90%;
  max-width: 920px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);
  overflow: hidden;
}
.modal-header {
  padding: 16px 24px;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #f9fafb;
}
.modal-title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  color: #111827;
}
.btn-modal-close {
  background: none;
  border: none;
  font-size: 1.2rem;
  color: #9ca3af;
  cursor: pointer;
}
.btn-modal-close:hover {
  color: #374151;
}
.modal-body {
  padding: 20px 24px;
  overflow-y: auto;
}
.modal-actions-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.section-desc {
  margin: 0;
  font-size: 0.85rem;
  color: #6b7280;
}

.rules-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
.rules-table th, .rules-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #e5e7eb;
  text-align: left;
}
.rules-table th {
  background-color: #f9fafb;
  font-weight: 600;
  color: #4b5563;
}
.badge-source {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}
.badge-source.auto { background-color: #e0e7ff; color: #3730a3; }
.badge-source.yuju { background-color: #d1fae5; color: #065f46; }
.badge-source.calculated { background-color: #fef3c7; color: #92400e; }

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.9rem;
}

.rule-form-card {
  background-color: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  margin-top: 16px;
}
.form-title {
  margin: 0 0 14px 0;
  font-size: 1rem;
  font-weight: 700;
  color: #1f2937;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.form-group label {
  font-size: 0.78rem;
  font-weight: 600;
  color: #374151;
}
.custom-select-sm, .custom-input-sm {
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid #d1d5db;
  font-size: 0.85rem;
  background-color: #ffffff;
}
.checkbox-group {
  justify-content: flex-end;
}
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
.btn-primary-sm {
  background-color: #2563eb;
  color: #ffffff;
  border: none;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
}
.btn-primary-sm:hover { background-color: #1d4ed8; }
.btn-secondary-sm {
  background-color: #e5e7eb;
  color: #374151;
  border: none;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
}
.btn-secondary-sm:hover { background-color: #d1d5db; }

/* ==========================================================================
   Execution / Hecho en el Día Tab Styles
   ========================================================================== */
.main-tabs-bar {
  display: flex;
  gap: 8px;
  background-color: #f1f5f9;
  padding: 6px;
  border-radius: 10px;
  margin-bottom: 14px;
}

.main-tab-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 18px;
  font-size: 0.88rem;
  font-weight: 600;
  color: #64748b;
  background: transparent;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.main-tab-btn:hover {
  color: #1e293b;
  background-color: rgba(255, 255, 255, 0.6);
}

.main-tab-btn.active {
  color: #2563eb;
  background-color: #ffffff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.main-tab-btn .badge-pill {
  background-color: #e2e8f0;
  color: #475569;
  font-size: 0.72rem;
  padding: 2px 7px;
  border-radius: 9999px;
  font-weight: 700;
}

.main-tab-btn.active .badge-pill {
  background-color: #dbeafe;
  color: #1d4ed8;
}

.execution-toolbar-sub {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #ffffff;
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  margin-bottom: 16px;
}

.matiz-switcher {
  display: flex;
  align-items: center;
  gap: 6px;
}

.matiz-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: #64748b;
  margin-right: 6px;
}

.matiz-btn {
  background-color: #f8fafc;
  border: 1px solid #cbd5e1;
  color: #475569;
  padding: 5px 12px;
  border-radius: 6px;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.matiz-btn:hover {
  background-color: #e2e8f0;
}

.matiz-btn.active {
  background-color: #2563eb;
  color: #ffffff;
  border-color: #2563eb;
}

.stage-chips {
  display: flex;
  align-items: center;
  gap: 6px;
}

.stage-chip-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: #64748b;
  margin-right: 4px;
}

.stage-chip {
  background-color: #f1f5f9;
  border: 1px solid #cbd5e1;
  color: #475569;
  padding: 4px 10px;
  border-radius: 9999px;
  font-size: 0.76rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.stage-chip:hover {
  background-color: #e2e8f0;
}

.stage-chip.active {
  background-color: #0f172a;
  color: #ffffff;
  border-color: #0f172a;
}

.stage-chip.pick.active { background-color: #0284c7; border-color: #0284c7; }
.stage-chip.pack.active { background-color: #d97706; border-color: #d97706; }
.stage-chip.out.active { background-color: #16a34a; border-color: #16a34a; }

/* Stage Badges */
.stage-badge {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.3px;
  text-transform: uppercase;
}
.stage-pick {
  background-color: #e0f2fe;
  color: #0369a1;
  border: 1px solid #bae6fd;
}
.stage-pack {
  background-color: #fef3c7;
  color: #b45309;
  border: 1px solid #fde68a;
}
.stage-out {
  background-color: #dcfce7;
  color: #15803d;
  border: 1px solid #bbf7d0;
}

.batch-badge {
  display: inline-block;
  background-color: #f1f5f9;
  color: #334155;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.72rem;
  border: 1px solid #e2e8f0;
}

/* Stepper inside By-Sale cards & table */
.exec-pipeline-stepper {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.pipeline-step {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.68rem;
  font-weight: 700;
  background-color: #f1f5f9;
  color: #94a3b8;
  border: 1px solid #e2e8f0;
}

.pipeline-step.step-done {
  background-color: #ecfdf5;
  color: #059669;
  border-color: #a7f3d0;
}

.pipeline-arrow {
  color: #cbd5e1;
  font-size: 0.62rem;
}

.exec-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px;
  margin-top: 14px;
}

.exec-card {
  background-color: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.exec-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #f1f5f9;
}

.exec-card-channel {
  font-size: 0.75rem;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
}

.exec-card-body {
  margin-bottom: 10px;
}

.exec-card-partner {
  font-size: 0.82rem;
  color: #334155;
  margin-bottom: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.exec-card-pickings {
  display: flex;
  flex-direction: column;
  gap: 4px;
  background-color: #f8fafc;
  padding: 6px 8px;
  border-radius: 6px;
}

.exec-picking-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.72rem;
}

.exec-picking-name {
  color: #475569;
  font-family: monospace;
}

.exec-picking-date {
  color: #64748b;
}

.exec-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 6px;
  border-top: 1px solid #f1f5f9;
}

/* Date Filter Labels */
.date-filter-group {
  display: flex;
  align-items: center;
  gap: 4px;
  transition: opacity 0.2s ease;
}
.date-filter-group.filter-bypassed {
  opacity: 0.5;
}
.date-filter-group.filter-bypassed input {
  background-color: #f1f5f9;
  cursor: not-allowed;
}
.date-filter-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: #475569;
  white-space: nowrap;
}
.badge-bypassed-dates {
  font-size: 0.72rem;
  font-weight: 600;
  color: #ea580c;
  background-color: #ffedd5;
  border: 1px solid #fed7aa;
  padding: 3px 7px;
  border-radius: 4px;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
}

/* Excel Export Button */
.btn-export-excel {
  background-color: #10b981;
  color: #ffffff;
  border: none;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  transition: all 0.2s ease;
  white-space: nowrap;
}
.btn-export-excel:hover:not(:disabled) {
  background-color: #059669;
  transform: translateY(-1px);
}
.btn-export-excel:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Fulfillment Switcher & Badges */
.fulfillment-switcher {
  display: flex;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  overflow: hidden;
  background-color: #f8fafc;
}
.fulfillment-btn {
  background: transparent;
  border: none;
  padding: 5px 10px;
  font-size: 0.75rem;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.fulfillment-btn.active {
  background-color: #4f46e5;
  color: #ffffff;
}
.fulfillment-pill {
  font-size: 0.68rem;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  background-color: #f1f5f9;
  color: #475569;
  border: 1px solid #cbd5e1;
}
.fulfillment-tag {
  display: inline-block;
  font-size: 0.68rem;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 3px;
  background-color: #e2e8f0;
  color: #334155;
  text-transform: uppercase;
}

/* Metric Cards Clickable as Filters */
.metric-clickable {
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
  user-select: none;
}
.metric-clickable:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
}
.metric-clickable.active {
  border-color: #3b82f6 !important;
  background-color: #eff6ff !important;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3) !important;
}

/* Odoo Entry Date */
.odoo-entry-box {
  font-size: 0.75rem;
  color: #475569;
  padding: 4px 8px;
  background-color: #f8fafc;
  border-radius: 4px;
  border-left: 3px solid #3b82f6;
  margin: 4px 0 6px 0;
}
.odoo-entry-date {
  font-family: monospace;
  font-size: 0.78rem;
  color: #1e293b;
}

/* SLA Manual Override Badges */
.manual-override-pill {
  display: flex;
  align-items: center;
  font-size: 0.7rem;
  font-weight: 600;
  color: #b45309;
  background-color: #fef3c7;
  border: 1px dashed #f59e0b;
  border-radius: 4px;
  padding: 3px 6px;
  margin-top: 4px;
}
.manual-override-table-tag {
  display: inline-block;
  font-size: 0.68rem;
  font-weight: 600;
  color: #b45309;
  background-color: #fef3c7;
  border: 1px solid #fde68a;
  border-radius: 3px;
  padding: 1px 4px;
  margin-top: 2px;
}

/* Reassign Action Buttons */
.btn-reassign-icon {
  background: transparent;
  border: 1px solid #cbd5e1;
  color: #64748b;
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-reassign-icon:hover {
  background-color: #f59e0b;
  color: #ffffff;
  border-color: #f59e0b;
}
.btn-action-reassign {
  background-color: #fef3c7;
  border: 1px solid #fcd34d;
  color: #92400e;
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-action-reassign:hover {
  background-color: #f59e0b;
  color: #ffffff;
}

/* Reassign Modal Card */
.reassign-modal-card {
  max-width: 520px;
  width: 100%;
}
.reassign-target-summary {
  background-color: #f8fafc;
  border-radius: 6px;
  font-size: 0.85rem;
  line-height: 1.5;
}

/* Bulk SLA Action Bar */
.bulk-action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #fef3c7;
  border: 1px solid #fde68a;
  color: #92400e;
  padding: 8px 16px;
  border-radius: 8px;
  margin: 10px 0 16px 0;
  box-shadow: 0 2px 6px rgba(245, 158, 11, 0.15);
}
.bulk-info {
  font-size: 0.9rem;
  font-weight: 500;
}
.bulk-buttons {
  display: flex;
  align-items: center;
}
.badge-acordar-sub {
  background-color: #f3e8ff;
  border: 1px solid #d8b4fe;
  color: #6b21a8;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
}
.badge-unconfirmed-sub {
  background-color: #fef3c7;
  border: 1px solid #fde68a;
  color: #b45309;
  font-size: 0.68rem;
  font-weight: 600;
  padding: 1px 5px;
  border-radius: 3px;
}
.unconfirmed-switcher {
  display: flex;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  overflow: hidden;
  background-color: #f8fafc;
  margin-left: 8px;
}
.row-selected {
  background-color: #fffbeb !important;
}
.card-checkbox {
  cursor: pointer;
  transform: scale(1.15);
}
</style>

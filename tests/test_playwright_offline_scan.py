#!/usr/bin/env python3
"""
Playwright Automated Test Suite for WMDs Offline Scan Buffer & Dexie Queue.
Tests rapid-fire scanning, zero drops, FIFO processing, persistence across reload,
and error handling.
"""

import sys
import os
import time
import subprocess
import asyncio
from playwright.async_api import async_playwright, expect

VITE_DIR = "/home/dev/wonder_dev/odoo-restore-env/extra-addons/wonderbrands2026/wmds/static/src/js/WMDs_Component_Project"
VITE_PORT = 5173
BASE_URL = f"http://127.0.0.1:{VITE_PORT}/test_harness.html"

async def run_tests():
    print("=====================================================================")
    print(" 🚀 INICIANDO PRUEBAS PLAYWRIGHT: BUFFER LOCAL DEXIE Y COLA DE ESCANEO")
    print("=====================================================================")

    # 1. Start Vite server
    print(f"\n[1/6] Iniciando servidor Vite en puerto {VITE_PORT}...")
    vite_proc = subprocess.Popen(
        ["npx", "vite", "--port", str(VITE_PORT), "--host", "127.0.0.1"],
        cwd=VITE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for Vite to be ready
    await asyncio.sleep(2.5)

    try:
        async with async_playwright() as p:
            print("[2/6] Lanzando Chromium headless...")
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context()
            page = await context.new_page()

            page.on("console", lambda msg: print(f"  [Browser Console] {msg.type}: {msg.text}"))

            # Open test harness
            print(f"Navegando a {BASE_URL}...")
            await page.goto(BASE_URL, wait_until="networkidle")

            # Wait for test harness ready
            await page.wait_for_function("() => window.__TEST__ !== undefined")
            print("✔ Test harness cargado y __TEST__ disponible.")

            # Iniciar sesión seleccionando Carrier (DHL Express)
            print("\n--- Seleccionando Carrier DHL Express e iniciando sesión ---")
            await page.select_option("select.carrier-dropdown", "1")
            await page.click("button:has-text('Iniciar Sesión')")
            
            # Wait for scanner to be mounted
            await page.wait_for_selector(".carrier-indicator", timeout=5000)
            carrier_text = await page.inner_text(".carrier-indicator")
            assert "DHL Express" in carrier_text, f"Carrier inesperado: {carrier_text}"
            print(f"✔ Sesión iniciada con: {carrier_text.strip()}")

            # -----------------------------------------------------------------
            # TEST CASE 1: ESCANEO RÁPIDO ULTRA-CONSECUTIVO (< 50ms)
            # -----------------------------------------------------------------
            print("\n-----------------------------------------------------------------")
            print(" TEST CASE 1: Escaneo rápido ultra-consecutivo (5 EI en < 150ms)")
            print("-----------------------------------------------------------------")
            barcodes = [
                "EI_FAST_101/1",
                "EI_FAST_102/1",
                "EI_FAST_103/1",
                "EI_FAST_104/1",
                "EI_FAST_105/1"
            ]

            t0 = time.time()
            for bc in barcodes:
                await page.evaluate(f"window.__TEST__.simulateLaserScan('{bc}')")
                await asyncio.sleep(0.02) # 20ms entre escaneos
            total_scan_time = (time.time() - t0) * 1000
            print(f"✔ 5 escaneos inyectados en {total_scan_time:.1f}ms (promedio {(total_scan_time/5):.1f}ms/scan).")

            # Verificar que en UI se agregaron inmediatamente los 5
            so_count = await page.evaluate("window.__TEST__.getDispatchVm().so.length")
            print(f"✔ Elementos en memoria de DispatchComponent: {so_count} de 5")
            assert so_count == 5, f"Esperados 5 escaneos en UI, encontrados {so_count}"

            # Verificar persistencia inmediata en Dexie IndexedDB
            records = await page.evaluate("""
                async () => {
                    const db = window.__TEST__.localDb;
                    return await db.scanQueue.toArray();
                }
            """)
            print(f"✔ Registros encontrados en IndexedDB Dexie: {len(records)}")
            assert len(records) == 5, f"Esperados 5 registros en Dexie, encontrados {len(records)}"

            for r in records:
                print(f"    - ID: {r['id']}, Barcode: {r['barcode']}, Status: {r['status']}")

            # -----------------------------------------------------------------
            # TEST CASE 2: PROCESAMIENTO FIFO EN BACKGROUND Y VACIADO DE COLA
            # -----------------------------------------------------------------
            print("\n-----------------------------------------------------------------")
            print(" TEST CASE 2: Procesamiento FIFO en background y sincronización")
            print("-----------------------------------------------------------------")

            # Esperar a que el worker procese todos los items
            print("Esperando drenado de cola por scanQueueWorker...")
            for _ in range(50):
                pending_count = await page.evaluate("""
                    async () => {
                        const db = window.__TEST__.localDb;
                        return await db.scanQueue.where('status').anyOf('pending', 'processing').count();
                    }
                """)
                if pending_count == 0:
                    break
                await asyncio.sleep(0.1)

            assert pending_count == 0, "La cola no se vació en el tiempo esperado"
            print("✔ Todos los 5 escaneos fueron procesados por el worker en background.")

            # Verificar que todos los registros en Dexie quedaron como 'synced'
            statuses = await page.evaluate("""
                async () => {
                    const db = window.__TEST__.localDb;
                    const items = await db.scanQueue.toArray();
                    return items.map(x => ({ barcode: x.barcode, status: x.status }));
                }
            """)
            for s in statuses:
                assert s['status'] == 'synced', f"Estado incorrecto para {s['barcode']}: {s['status']}"
            print(f"✔ 100% de los registros en Dexie tienen status='synced': {[s['barcode'] for s in statuses]}")

            # Verificar que en UI cada item tiene status 'synced' y producto asignado
            ui_synced = await page.evaluate("""
                () => {
                    const vm = window.__TEST__.getDispatchVm();
                    return vm.so.every(o => o.sync_status === 'synced' && o.product_name.includes('SKU-TEST'));
                }
            """)
            assert ui_synced, "No todos los items en UI se actualizaron a synced con sus datos"
            print("✔ UI actualizada de forma reactiva con status 'synced' y nombres de producto.")

            # -----------------------------------------------------------------
            # TEST CASE 3: PERSISTENCIA LOCAL ANTE RECARGA DE PÁGINA (PWA RELOAD)
            # -----------------------------------------------------------------
            print("\n-----------------------------------------------------------------")
            print(" TEST CASE 3: Persistencia ante recarga de página (PWA reload)")
            print("-----------------------------------------------------------------")

            # Congelar backend para que los escaneos queden pendientes en Dexie
            await page.evaluate("window.__TEST__.testState.backendDelayMs = 2000;")
            
            # Encolar 2 nuevos escaneos
            await page.evaluate("window.__TEST__.simulateLaserScan('EI_RELOAD_201/1')")
            await page.evaluate("window.__TEST__.simulateLaserScan('EI_RELOAD_202/1')")

            # Verificar que están en Dexie
            pending_before = await page.evaluate("""
                async () => {
                    const db = window.__TEST__.localDb;
                    return await db.scanQueue.where('status').anyOf('pending', 'processing').count();
                }
            """)
            print(f"✔ Escaneos pendientes en Dexie antes del reload: {pending_before}")
            assert pending_before >= 1, "Debía haber escaneos pendientes en Dexie"

            # Simular que el usuario cierra o recarga la página / PWA
            print("Recargando página (simulación reinicio PWA / handheld)...")
            await page.reload(wait_until="networkidle")
            await page.wait_for_function("() => window.__TEST__ !== undefined")

            # Restaurar delay rápido
            await page.evaluate("window.__TEST__.testState.backendDelayMs = 40;")

            # Seleccionar carrier o verificar recuperación
            await page.select_option("select.carrier-dropdown", "1")
            await page.click("button:has-text('Iniciar Sesión')")
            await page.wait_for_selector(".carrier-indicator", timeout=5000)

            # Esperar a que el worker reinicie y procese los pendientes restaurados
            print("Esperando drenado tras recarga...")
            pending_after = -1
            for _ in range(50):
                pending_after = await page.evaluate("""
                    async () => {
                        const db = window.__TEST__.localDb;
                        return await db.scanQueue.where('status').anyOf('pending', 'processing').count();
                    }
                """)
                if pending_after == 0:
                    break
                await asyncio.sleep(0.1)

            print(f"✔ Pendientes después de recuperación y drenado: {pending_after}")
            assert pending_after == 0, "El worker debió reanudar y procesar los escaneos pendientes tras la recarga"

            # -----------------------------------------------------------------
            # TEST CASE 4: MANEJO DE PEDIDOS CANCELADOS Y ERRORES SIN BLOQUEO
            # -----------------------------------------------------------------
            print("\n-----------------------------------------------------------------")
            print(" TEST CASE 4: Pedido cancelado y error de negocio sin bloqueo")
            print("-----------------------------------------------------------------")

            # Registrar barcode cancelado
            await page.evaluate("window.__TEST__.testState.cancelledBarcodes.add('EI_CANCEL_301/1');")
            
            # Escanear pedido cancelado seguido inmediatamente de uno válido
            await page.evaluate("window.__TEST__.simulateLaserScan('EI_CANCEL_301/1');")
            await page.evaluate("window.__TEST__.simulateLaserScan('EI_VALID_302/1');")

            # Esperar a que el worker procese ambos
            await asyncio.sleep(1.0)

            # Verificar que el cancelado fue marcado como error/cancelado
            cancel_status = await page.evaluate("""
                async () => {
                    const db = window.__TEST__.localDb;
                    const rec = await db.scanQueue.where('barcode').equals('EI_CANCEL_301/1').first();
                    const vm = window.__TEST__.getDispatchVm();
                    const uiItem = vm.so.find(o => o.name === 'EI_CANCEL_301/1');
                    return {
                        dbStatus: rec ? rec.status : null,
                        uiState: uiItem ? uiItem.so_state : null
                    };
                }
            """)
            print(f"✔ Resultado escaneo cancelado: DB status={cancel_status['dbStatus']}, UI state={cancel_status['uiState']}")
            assert cancel_status['dbStatus'] == 'error', f"DB status debió ser error, fue: {cancel_status['dbStatus']}"
            assert cancel_status['uiState'] == 'cancel', f"UI state debió ser cancel, fue: {cancel_status['uiState']}"

            # Verificar que el escaneo siguiente continuó normalmente y se sincronizó
            valid_status = await page.evaluate("""
                async () => {
                    const db = window.__TEST__.localDb;
                    const rec = await db.scanQueue.where('barcode').equals('EI_VALID_302/1').first();
                    return rec ? rec.status : null;
                }
            """)
            print(f"✔ Resultado escaneo siguiente: DB status={valid_status}")
            assert valid_status == 'synced', f"El escaneo válido debió procesarse como synced, fue: {valid_status}"

            # Confirmar remoción física en el modal obligatorio
            print("Confirmando remoción física de paquete cancelado en modal...")
            await page.evaluate("window.__TEST__.getDispatchVm().confirmCancelledScan('EI_CANCEL_301/1');")
            await asyncio.sleep(1.2)
            await page.wait_for_selector(".cancelled-modal-overlay", state="detached", timeout=3000)
            print("✔ Modal de cancelados cerrado tras confirmar remoción física.")

            # -----------------------------------------------------------------
            # TEST CASE 5: PREVENCIÓN DE DESPACHO CON COLA PENDIENTE
            # -----------------------------------------------------------------
            print("\n-----------------------------------------------------------------")
            print(" TEST CASE 5: Barrera de despacho mientras hay cola activa")
            print("-----------------------------------------------------------------")

            # Retrasar backend 1.5 segundos
            await page.evaluate("window.__TEST__.testState.backendDelayMs = 1500;")
            
            # Encolar un escaneo lento
            await page.evaluate("window.__TEST__.simulateLaserScan('EI_SLOW_401/1');")

            # Intentar click en "Entregar a paquetería" inmediatamente
            await page.click("button:has-text('Entregar a paquetería')")

            # Verificar que DispatchComponent mostró Toast de advertencia y no despachó
            dispatch_called = await page.evaluate("""
                () => {
                    const calls = window.__TEST__.testState.backendCalls;
                    return calls.some(c => c.context === 'dispatch_orders');
                }
            """)
            print(f"✔ Llamada a dispatch_orders prevenida mientras había cola: {not dispatch_called}")
            assert not dispatch_called, "No debió llamarse a dispatch_orders con escaneos pendientes"

            # Esperar a que termine de procesar el lento
            print("Esperando finalización de cola lenta...")
            for _ in range(50):
                pending_count = await page.evaluate("""
                    async () => {
                        const db = window.__TEST__.localDb;
                        return await db.scanQueue.where('status').anyOf('pending', 'processing').count();
                    }
                """)
                if pending_count == 0:
                    break
                await asyncio.sleep(0.1)

            # Ahora intentar despacho limpio
            await page.evaluate("window.__TEST__.testState.backendDelayMs = 10;")
            await page.click("button:has-text('Entregar a paquetería')")
            await asyncio.sleep(0.5)

            dispatch_success = await page.evaluate("""
                () => {
                    const calls = window.__TEST__.testState.backendCalls;
                    return calls.some(c => c.context === 'dispatch_orders');
                }
            """)
            print(f"✔ Despacho ejecutado exitosamente tras completar sincronización: {dispatch_success}")
            assert dispatch_success, "dispatch_orders debió ser invocado tras vaciar cola"

            await context.close()
            await browser.close()

            print("\n=====================================================================")
            print(" ✅ TODAS LAS PRUEBAS DE PLAYWRIGHT PASARON CON ÉXITO (100%)")
            print("=====================================================================")

    finally:
        print("\nDeteniendo servidor Vite de pruebas...")
        vite_proc.terminate()
        try:
            vite_proc.wait(timeout=3)
        except Exception:
            vite_proc.kill()
        print("Servidor detenido.")

if __name__ == "__main__":
    asyncio.run(run_tests())

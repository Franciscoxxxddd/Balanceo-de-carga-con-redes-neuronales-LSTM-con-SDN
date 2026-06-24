#!/usr/bin/env python3
"""
=============================================================
 PRUEBA 1: Tráfico Base (Control)
 Carga: Baja (70-100 pps) | Puerto 80
 Objetivo: Validar latencia base (IPTD) y conectividad
           extremo a extremo sin estrés.
 Métricas: IPLR, IPTD, IPDV, Throughput, Equidad
=============================================================
"""
import os, sys, time

# Agregar directorio padre al path para importar test_common
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from test_common import *

# ─── CONFIGURACIÓN ────────────────────────────────────────
MODO = parse_modo()
PRUEBA_NUM = 1
PRUEBA_NOMBRE = "Tráfico Base (Control)"
RESULTADO_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    f"resultado_prueba{PRUEBA_NUM}_{MODO}.json")
DURACION = 30  # segundos


def run():
    net = Mininet(controller=RemoteController, switch=OVSKernelSwitch)
    print_header(PRUEBA_NUM, PRUEBA_NOMBRE, MODO)

    c0 = net.addController('c0', ip='127.0.0.1', port=6633)
    servers, clients = crear_topologia(net)
    net.start()

    print(">>> Iniciando servicios en servidores...")
    iniciar_servicios(servers)
    time.sleep(3)

    # Iniciar monitoreo del controlador
    monitor = MonitorController()
    monitor.start()

    resultados = init_resultados(PRUEBA_NUM, PRUEBA_NOMBRE, MODO, DURACION)

    # ─── FASE 1: Tráfico HTTP ligero (70 peticiones por cliente) ───
    print("\n--- Fase 1: Tráfico HTTP ligero (70 pps) ---")
    for cli in clients:
        print(f"    {cli.name} → curl http://{VIP_WEB}/ ({MIN_PACKETS} peticiones)")
        cli.cmd(f"for i in $(seq 1 {MIN_PACKETS}); do "
                f"curl -s -o /dev/null --connect-timeout 2 http://{VIP_WEB}/; "
                f"sleep 0.3; done &")
    time.sleep(DURACION)

    # ─── FASE 2: Métricas completas ITU-T + RFC 2544 ───
    metricas = medir_metricas_completas(clients, servers, VIP_WEB)

    # ─── FASE 3: Back-to-Back ───
    print("\n--- Midiendo Back-to-Back Frames ---")
    b2b = medir_back_to_back(clients[0], servers[0], port=5002)
    metricas['back_to_back'] = b2b

    # ─── FASE 4: Equidad ───
    print("\n--- Equidad de servidores ---")
    cpus, rams = leer_equidad_servidores()
    metricas['equidad'] = calcular_equidad(cpus, rams)
    print(f"    CPU: avg={metricas['equidad']['cpu']['promedio']:.2f}%, "
          f"std={metricas['equidad']['cpu']['desviacion_std']:.2f}%")

    # ─── FASE 5: Recovery Time ───
    print("\n--- Midiendo System Recovery ---")
    recovery = medir_recovery_time(clients[0], servers[0].IP())
    metricas['recovery'] = recovery
    print(f"    Recovery: {recovery['recovery_s']}s, estable={recovery['estable']}")

    # ─── COMPILAR Y GUARDAR ───
    monitor.stop()
    resultados['metricas'] = metricas
    resultados = finalizar_resultados(resultados, monitor, MODO)
    guardar_resultados(resultados, RESULTADO_FILE)

    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()

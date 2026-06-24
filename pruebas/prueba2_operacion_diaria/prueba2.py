#!/usr/bin/env python3
"""
=============================================================
 PRUEBA 2: Operación Diaria (Normal)
 Carga: Media (100-200 pps) | 7+ hosts simultáneos
 Objetivo: Medir equidad de carga en servidores bajo
           operación normal sostenida.
 Métricas: IPLR, IPTD, IPDV, Throughput, Equidad
=============================================================
"""
import os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from test_common import *

MODO = parse_modo()
PRUEBA_NUM = 2
PRUEBA_NOMBRE = "Operación Diaria (Normal)"
RESULTADO_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    f"resultado_prueba{PRUEBA_NUM}_{MODO}.json")
DURACION = 60


def run():
    net = Mininet(controller=RemoteController, switch=OVSKernelSwitch)
    print_header(PRUEBA_NUM, PRUEBA_NOMBRE, MODO)

    c0 = net.addController('c0', ip='127.0.0.1', port=6633)
    servers, clients = crear_topologia(net)
    net.start()

    print(">>> Iniciando servicios...")
    iniciar_servicios(servers)
    time.sleep(3)

    monitor = MonitorController()
    monitor.start()

    resultados = init_resultados(PRUEBA_NUM, PRUEBA_NOMBRE, MODO, DURACION)

    # ─── FASE 1: HTTP sostenido desde 12 hosts (100-200 pps) ───
    print("\n--- Fase 1: Tráfico HTTP sostenido (12 hosts, ~150 pps) ---")
    for cli in clients:
        # 70 peticiones con sleep 0.1 = ~10 pps por host × 12 = ~120 pps
        cli.cmd(f"for i in $(seq 1 {MIN_PACKETS}); do "
                f"curl -s -o /dev/null --connect-timeout 2 http://{VIP_WEB}/; "
                f"sleep 0.1; done &")
        print(f"    {cli.name} → {MIN_PACKETS} peticiones HTTP concurrentes")

    print(f"    Ejecutando durante {DURACION}s...")
    time.sleep(DURACION)

    # ─── FASE 2: Métricas completas ───
    metricas = medir_metricas_completas(clients, servers, VIP_WEB)

    # ─── FASE 3: Back-to-Back ───
    print("\n--- Midiendo Back-to-Back Frames ---")
    metricas['back_to_back'] = medir_back_to_back(clients[0], servers[0], port=5002)

    # ─── FASE 4: Equidad (múltiples muestras) ───
    print("\n--- Equidad de servidores (5 muestras) ---")
    equidad_samples = []
    for _ in range(5):
        cpus, rams = leer_equidad_servidores()
        equidad_samples.append({'cpus': cpus, 'rams': rams})
        time.sleep(1)

    if equidad_samples:
        cpus_f = [statistics.mean([s['cpus'][i] for s in equidad_samples]) for i in range(4)]
        rams_f = [statistics.mean([s['rams'][i] for s in equidad_samples]) for i in range(4)]
    else:
        cpus_f, rams_f = [0] * 4, [0] * 4

    metricas['equidad'] = calcular_equidad(cpus_f, rams_f)
    print(f"    CPU: avg={metricas['equidad']['cpu']['promedio']:.2f}%, "
          f"std={metricas['equidad']['cpu']['desviacion_std']:.2f}%")

    # ─── Recovery Time ───
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

#!/usr/bin/env python3
"""
=============================================================
 PRUEBA 4: Tráfico Pesado (Streaming)
 Carga: Alta TCP | Puerto 8080 | Mínimo 70 ráfagas/host
 Objetivo: Medir Throughput de servidores y paquetes caídos
           bajo streaming masivo.
 Métricas: IPLR, IPTD, IPDV, Throughput, Equidad
=============================================================
"""
import os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from test_common import *

MODO = parse_modo()
PRUEBA_NUM = 4
PRUEBA_NOMBRE = "Tráfico Pesado (Streaming)"
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

    # ─── FASE 1: Servidores iperf en 8080 ───
    print("\n--- Fase 1: Servidores iperf (streaming) ---")
    for srv in servers:
        srv.cmd("iperf -s -p 8080 &")
        print(f"    {srv.name} escuchando streaming en :8080")
    time.sleep(2)

    # ─── FASE 2: Flujos TCP masivos simulando video ───
    print(f"\n--- Fase 2: Inyectando flujos de streaming ({DURACION}s) ---")
    for cli in clients:
        # Streaming: 3 flujos TCP paralelos + 70 curls al VIP
        cli.cmd(f"iperf -c {VIP_STREAMING} -p 8080 -t {DURACION} -P 3 "
                f"-w 256k -i 1 -f m > /tmp/stream_{cli.name}.log 2>&1 &")
        cli.cmd(f"for i in $(seq 1 {MIN_PACKETS}); do "
                f"curl -s -o /dev/null --connect-timeout 2 "
                f"http://{VIP_STREAMING}:8080/; sleep 0.2; done &")
        print(f"    {cli.name} → streaming (3 flujos TCP, window=256k)")

    print(f"    Ejecutando streaming durante {DURACION}s...")
    time.sleep(DURACION + 2)

    # ─── FASE 3: Recoger throughput ───
    print("\n--- Fase 3: Recopilando throughput ---")
    throughputs_stream = {}
    for cli in clients:
        tp = medir_throughput_iperf_log(cli, f"/tmp/stream_{cli.name}.log")
        throughputs_stream[cli.name] = tp
        print(f"    {cli.name}: {tp:.2f} Mbps")

    tp_total = sum(throughputs_stream.values())
    print(f"    Throughput TOTAL: {tp_total:.2f} Mbps")

    # ─── FASE 4: Métricas ITU-T completas ───
    metricas = medir_metricas_completas(clients, servers, VIP_WEB)
    metricas['throughput_streaming'] = throughputs_stream
    metricas['throughput_total'] = tp_total

    # ─── FASE 5: Back-to-Back ───
    print("\n--- Midiendo Back-to-Back Frames ---")
    limpiar_iperf(servers)
    metricas['back_to_back'] = medir_back_to_back(clients[0], servers[0], port=5002)

    # ─── FASE 6: Equidad ───
    cpus, rams = leer_equidad_servidores()
    metricas['equidad'] = calcular_equidad(cpus, rams)

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

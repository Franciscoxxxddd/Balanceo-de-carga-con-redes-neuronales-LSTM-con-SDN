#!/usr/bin/env python3
"""
=============================================================
 PRUEBA 8: Tráfico Mixto Concurrente
 Carga: Media-Alta | 50% HTTP + 50% Streaming
 Objetivo: Reportar cómo la congestión afecta la pérdida
           de paquetes de manera global.
 Métricas: IPLR, IPTD, IPDV, Throughput, Equidad
=============================================================
"""
import os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from test_common import *

MODO = parse_modo()
PRUEBA_NUM = 8
PRUEBA_NOMBRE = "Tráfico Mixto Concurrente"
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

    # iperf servers
    for srv in servers:
        srv.cmd("iperf -s -p 8080 &")
    time.sleep(2)

    # ─── Perfil 1: HTTP ligero (cli1-cli6 = 50%) ───
    http_clients = clients[:6]
    stream_clients = clients[6:]

    print(f"\n--- Perfil HTTP (cli1-cli6): {MIN_PACKETS} peticiones/host ---")
    for cli in http_clients:
        cli.cmd(f"for i in $(seq 1 {MIN_PACKETS}); do "
                f"curl -s -o /dev/null --connect-timeout 2 http://{VIP_WEB}/; "
                f"sleep 0.3; done &")

    # ─── Perfil 2: Streaming pesado (cli7-cli12 = 50%) ───
    print(f"--- Perfil Streaming (cli7-cli12): 3 flujos TCP/host ---")
    for cli in stream_clients:
        cli.cmd(f"iperf -c {VIP_STREAMING} -p 8080 -t {DURACION} -P 3 "
                f"-w 256k -i 1 -f m > /tmp/mix_{cli.name}.log 2>&1 &")

    print(f"    Ejecutando tráfico mixto durante {DURACION}s...")
    time.sleep(DURACION)

    # ─── Recoger throughput streaming ───
    print("\n--- Recopilando throughput streaming ---")
    throughputs_stream = {}
    for cli in stream_clients:
        tp = medir_throughput_iperf_log(cli, f"/tmp/mix_{cli.name}.log")
        throughputs_stream[cli.name] = tp
        print(f"    {cli.name}: {tp:.2f} Mbps")

    limpiar_iperf(servers)

    # ─── Métricas ITU-T completas ───
    metricas = medir_metricas_completas(clients, servers, VIP_WEB)
    metricas['throughput_streaming'] = throughputs_stream
    metricas['perfil_http'] = [cli.name for cli in http_clients]
    metricas['perfil_streaming'] = [cli.name for cli in stream_clients]

    # ─── Back-to-Back ───
    print("\n--- Midiendo Back-to-Back Frames ---")
    metricas['back_to_back'] = medir_back_to_back(clients[0], servers[0], port=5002)

    # ─── Equidad ───
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

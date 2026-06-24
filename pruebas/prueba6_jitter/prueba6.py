#!/usr/bin/env python3
"""
=============================================================
 PRUEBA 6: Degradación de Enlace (Jitter)
 Carga: 70 pps | Retardo artificial 50ms en srv1/srv2
 Objetivo: Evaluar IPDV (Jitter) y desvío preventivo de IA.
           Filtrar puertos 8080 (Streaming) y 5060 (VoIP).
 Métricas: IPLR, IPTD, IPDV, Throughput
=============================================================
"""
import os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from test_common import *

MODO = parse_modo()
PRUEBA_NUM = 6
PRUEBA_NOMBRE = "Degradación de Enlace (Jitter)"
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
    srv1, srv2, srv3, srv4 = servers

    # ─── FASE 1: Latencia BASE sin degradación ───
    print("\n--- Fase 1: Latencia BASE (sin degradación) ---")
    latencias_base = {}
    for cli in clients:
        latencias_base[cli.name] = medir_iptd(cli, VIP_WEB, count=10)
        print(f"    {cli.name} base: {latencias_base[cli.name]['avg']:.2f}ms")

    # ─── FASE 2: Inyectar retardo 50ms en srv1 y srv2 ───
    print("\n--- Fase 2: Inyectando retardo 50ms en srv1 y srv2 ---")
    srv1.cmd(f"tc qdisc replace dev {srv1.name}-eth0 root "
             f"netem delay 50ms 10ms loss 3%")
    srv2.cmd(f"tc qdisc replace dev {srv2.name}-eth0 root "
             f"netem delay 50ms 10ms loss 3%")
    print(f"    srv1: delay 50ms ±10ms, loss 3%")
    print(f"    srv2: delay 50ms ±10ms, loss 3%")

    # También degradar clientes ligeramente
    for cli in clients:
        cli.cmd(f"tc qdisc replace dev {cli.name}-eth0 root "
                f"netem delay 5ms 3ms loss 3% 25%")

    # ─── FASE 3: Tráfico HTTP con degradación (70 pps) ───
    print(f"\n--- Fase 3: Tráfico con degradación ({DURACION}s) ---")
    for cli in clients:
        cli.cmd(f"for i in $(seq 1 {MIN_PACKETS}); do "
                f"curl -s -o /dev/null --connect-timeout 2 http://{VIP_WEB}/; "
                f"sleep 0.3; done &")
    time.sleep(DURACION)

    # ─── FASE 4: Latencia CON degradación ───
    print("\n--- Fase 4: Latencia CON degradación ---")
    latencias_degradada = {}
    for cli in clients:
        latencias_degradada[cli.name] = medir_iptd(cli, VIP_WEB, count=10)
        print(f"    {cli.name} degradada: "
              f"{latencias_degradada[cli.name]['avg']:.2f}ms")

    # ─── FASE 5: IPDV específico para Streaming y VoIP ───
    print("\n--- Fase 5: IPDV para Streaming (8080) y VoIP (5060) ---")
    ipdv_streaming = {}
    ipdv_voip = {}
    for cli in clients[:4]:
        ipdv_streaming[cli.name] = medir_ipdv(cli, VIP_STREAMING, count=MIN_PACKETS)
        ipdv_voip[cli.name] = medir_ipdv(cli, VIP_VOIP, count=MIN_PACKETS)
        print(f"    {cli.name}: Streaming jitter="
              f"{ipdv_streaming[cli.name]['jitter_mdev']:.2f}ms, "
              f"VoIP jitter={ipdv_voip[cli.name]['jitter_mdev']:.2f}ms")

    # ─── FASE 6: Throughput ───
    print("\n--- Fase 6: Throughput ---")
    throughputs = {}
    for srv in servers:
        tp = medir_throughput_servidor(srv, clients[0], port=5001, duration=5)
        throughputs[srv.name] = tp
        print(f"    {srv.name}: {tp:.2f} Mbps")

    # ─── Limpiar netem ───
    limpiar_netem([srv1, srv2] + clients)

    # ─── FASE 7: Métricas ITU-T (post-limpieza para baseline) ───
    metricas = medir_metricas_completas(clients, servers, VIP_WEB)
    metricas['latencia_base'] = latencias_base
    metricas['latencia_degradada'] = latencias_degradada
    metricas['ipdv_streaming'] = ipdv_streaming
    metricas['ipdv_voip'] = ipdv_voip
    metricas['throughput_degradado'] = throughputs

    # ─── FASE 8: Back-to-Back ───
    print("\n--- Midiendo Back-to-Back Frames ---")
    metricas['back_to_back'] = medir_back_to_back(clients[0], servers[0], port=5002)

    # ─── FASE 9: Equidad ───
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

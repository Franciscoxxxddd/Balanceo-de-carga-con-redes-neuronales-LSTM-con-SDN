#!/usr/bin/env python3
"""
=============================================================
 PRUEBA 5: Ráfagas Asimétricas (Spikes)
 Carga: Variable 10 → 300 pps en <5 segundos
 Objetivo: Evaluar tiempo de reacción de la IA y
           System Recovery tras spike abrupto.
 Métricas: IPLR, IPTD, IPDV, Throughput, Recovery
=============================================================
"""
import os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from test_common import *

MODO = parse_modo()
PRUEBA_NUM = 5
PRUEBA_NOMBRE = "Ráfagas Asimétricas (Spikes)"
RESULTADO_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    f"resultado_prueba{PRUEBA_NUM}_{MODO}.json")
DURACION = 45


def run():
    net = Mininet(controller=RemoteController, switch=OVSKernelSwitch)
    print_header(PRUEBA_NUM, PRUEBA_NOMBRE, MODO)

    c0 = net.addController('c0', ip='127.0.0.1', port=6633)
    servers, clients = crear_topologia(net)
    net.start()

    print(">>> Iniciando servicios...")
    iniciar_servicios(servers)
    time.sleep(3)

    # Condiciones de red base
    print("--- Aplicando netem base (delay + loss) ---")
    for cli in clients:
        cli.cmd(f"tc qdisc replace dev {cli.name}-eth0 root "
                f"netem delay 10ms 8ms loss 4% 25%")

    monitor = MonitorController()
    monitor.start()

    resultados = init_resultados(PRUEBA_NUM, PRUEBA_NOMBRE, MODO, DURACION)

    # ─── FASE 1: Carga BAJA (15s) - ~10 pps ───
    print("\n--- Fase 1: Carga BAJA (15s) ---")
    latencias_baja = {}
    for cli in clients[:4]:
        cli.cmd(f"for i in $(seq 1 {MIN_PACKETS}); do "
                f"curl -s -o /dev/null --connect-timeout 2 http://{VIP_WEB}/; "
                f"sleep 1; done &")
    time.sleep(10)
    for cli in clients[:4]:
        latencias_baja[cli.name] = medir_iptd(cli, VIP_WEB, count=5)
        print(f"    {cli.name} lat_baja: {latencias_baja[cli.name]['avg']:.2f}ms")
    time.sleep(5)

    # ─── FASE 2: SPIKE - Transición a CRÍTICA en <5s ───
    print("\n--- Fase 2: ¡¡¡ SPIKE !!! Carga CRÍTICA ---")
    t_spike_start = time.time()

    for srv in servers:
        srv.cmd("iperf -s -p 5001 &")
    time.sleep(1)

    for cli in clients:
        srv_idx = clients.index(cli) % 4
        cli.cmd(f"iperf -c {servers[srv_idx].IP()} -p 5001 -t 20 -P 5 "
                f"-i 1 -f m > /tmp/spike_{cli.name}.log 2>&1 &")
        cli.cmd(f"for i in $(seq 1 100); do "
                f"curl -s -o /dev/null --connect-timeout 1 http://{VIP_WEB}/; "
                f"sleep 0.02; done &")
    print(f"    12 hosts × 5 flujos paralelos + 100 HTTP rápidos")

    # ─── FASE 3: Medir IPLR/IPTD/IPDV DURANTE el spike ───
    print("\n--- Fase 3: Midiendo DURANTE el spike ---")
    time.sleep(3)
    iplr_spike = {}
    iptd_spike = {}
    ipdv_spike = {}
    for cli in clients:
        iplr_spike[cli.name] = medir_iplr(cli, VIP_WEB, count=MIN_PACKETS)
        iptd_spike[cli.name] = medir_iptd(cli, VIP_WEB, count=5)
        ipdv_spike[cli.name] = medir_ipdv(cli, VIP_WEB, count=MIN_PACKETS)
        print(f"    {cli.name}: IPLR={iplr_spike[cli.name]['porcentaje']}%, "
              f"lat={iptd_spike[cli.name]['avg']:.2f}ms")

    print("\n--- Midiendo IPDV Streaming (8080) y VoIP (5060) ---")
    ipdv_streaming = {}
    ipdv_voip = {}
    for cli in clients[:4]:
        ipdv_streaming[cli.name] = medir_ipdv(cli, VIP_STREAMING, count=MIN_PACKETS)
        ipdv_voip[cli.name] = medir_ipdv(cli, VIP_VOIP, count=MIN_PACKETS)
        print(f"    {cli.name}: Streaming={ipdv_streaming[cli.name]['jitter_mdev']:.2f}ms, "
              f"VoIP={ipdv_voip[cli.name]['jitter_mdev']:.2f}ms")

    # Calcular promedios bajo spike
    perdida_vals = [v['porcentaje'] for v in iplr_spike.values()]
    perdida_general = round(statistics.mean(perdida_vals), 2) if perdida_vals else 0.0
    jitter_vals = [v['jitter_mdev'] for v in ipdv_spike.values()]
    jitter_avg = round(statistics.mean(jitter_vals), 2) if jitter_vals else 0.0
    lat_vals = [v['avg'] for v in iptd_spike.values() if v['avg'] > 0]
    latencia_avg = round(statistics.mean(lat_vals), 2) if lat_vals else 0.0

    time.sleep(10)
    t_spike_end = time.time()
    tiempo_reaccion = t_spike_end - t_spike_start

    # ─── FASE 4: Throughput ───
    print("\n--- Calculando throughput ---")
    throughputs = {}
    for cli in clients:
        tp = medir_throughput_iperf_log(cli, f"/tmp/spike_{cli.name}.log")
        throughputs[cli.name] = tp
        print(f"    {cli.name}: {tp:.2f} Mbps")

    # ─── FASE 5: Throughput desde servidores ───
    print("\n--- Throughput desde servidores ---")
    throughput_srv = {}
    for srv in servers:
        tp = medir_throughput_servidor(srv, clients[0], port=5001, duration=5)
        throughput_srv[srv.name] = tp

    # ─── FASE 6: Back-to-Back ───
    print("\n--- Midiendo Back-to-Back Frames ---")
    b2b = medir_back_to_back(clients[0], servers[0], port=5002)

    # ─── FASE 7: Recovery Time ───
    print("\n--- Midiendo System Recovery ---")
    limpiar_netem(clients)
    limpiar_iperf(servers)
    recovery = medir_recovery_time(clients[0], servers[0].IP())
    if recovery['estable']:
        print(f"    ✅ Sistema estable en {recovery['recovery_s']}s")
    else:
        print(f"    ⚠️  No se alcanzó estabilidad")

    # ─── Equidad ───
    cpus, rams = leer_equidad_servidores()

    # Compilar métricas (medidas DURANTE el spike)
    metricas = {
        'iplr': iplr_spike,
        'iptd': iptd_spike,
        'ipdv': ipdv_spike,
        'throughput': throughput_srv,
        'perdida_general': perdida_general,
        'jitter_avg': jitter_avg,
        'latencia_avg': latencia_avg,
        'latencia_baja': latencias_baja,
        'latencia_spike': {k: v for k, v in iptd_spike.items()},
        'tiempo_reaccion_s': tiempo_reaccion,
        'throughput_spike': throughputs,
        'recovery': recovery,
        'equidad': calcular_equidad(cpus, rams),
        'back_to_back': b2b,
        'ipdv_streaming': ipdv_streaming,
        'ipdv_voip': ipdv_voip
    }

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

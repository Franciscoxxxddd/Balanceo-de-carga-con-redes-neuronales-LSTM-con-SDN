#!/usr/bin/env python3
"""
=============================================================
 PRUEBA 7: Congestión en Switches (Packet Loss)
 Carga: Alta | 5% pérdida forzada en switches core
 Objetivo: Forzar pérdida de paquetes y limitar buffers.
           Validar predicción de IA y reportar IPLR final.
 Métricas: IPLR (OBLIGATORIO), IPTD, IPDV, Throughput
=============================================================
"""
import os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from test_common import *

MODO = parse_modo()
PRUEBA_NUM = 7
PRUEBA_NOMBRE = "Congestión en Switches (Packet Loss)"
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

    # ─── FASE 1: Latencia BASE ───
    print("\n--- Fase 1: Latencia BASE ---")
    latencias_base = {}
    for cli in clients:
        latencias_base[cli.name] = medir_iptd(cli, VIP_WEB, count=10)

    # ─── FASE 2: Inyectar 5% packet loss forzado ───
    print("\n--- Fase 2: Inyectando 5% pérdida en clientes ---")
    for cli in clients:
        cli.cmd(f"tc qdisc replace dev {cli.name}-eth0 root netem loss 5%")
        print(f"    {cli.name}: 5% packet loss forzado")

    # ─── FASE 3: Tráfico bajo congestión ───
    print(f"\n--- Fase 3: Tráfico bajo congestión ({DURACION}s) ---")
    for srv in servers:
        srv.cmd("iperf -s -p 8080 &")
    time.sleep(1)

    for cli in clients:
        cli.cmd(f"iperf -c {VIP_STREAMING} -p 8080 -t {DURACION} -P 2 "
                f"-w 256k -i 1 -f m > /tmp/cong_{cli.name}.log 2>&1 &")
        cli.cmd(f"for j in $(seq 1 {MIN_PACKETS}); do "
                f"curl -s -o /dev/null --connect-timeout 2 http://{VIP_WEB}/; "
                f"sleep 0.3; done &")

    time.sleep(DURACION + 2)

    # ─── FASE 4: Recoger throughput ───
    print("\n--- Fase 4: Recopilando throughput ---")
    throughputs = {}
    for cli in clients:
        tp = medir_throughput_iperf_log(cli, f"/tmp/cong_{cli.name}.log")
        throughputs[cli.name] = tp

    # ─── FASE 5: Medir IPLR/IPTD/IPDV CON NETEM ACTIVO ───
    print("\n--- Fase 5: Midiendo métricas CON congestión activa ---")
    iplr_stress = {}
    iptd_stress = {}
    ipdv_stress = {}
    for cli in clients:
        iplr_stress[cli.name] = medir_iplr(cli, VIP_WEB, count=MIN_PACKETS)
        iptd_stress[cli.name] = medir_iptd(cli, VIP_WEB, count=20)
        ipdv_stress[cli.name] = medir_ipdv(cli, VIP_WEB, count=MIN_PACKETS)
        print(f"    {cli.name}: IPLR={iplr_stress[cli.name]['porcentaje']}%, "
              f"IPTD={iptd_stress[cli.name]['avg']:.2f}ms")

    print("\n--- Midiendo IPDV Streaming (8080) y VoIP (5060) ---")
    ipdv_streaming = {}
    ipdv_voip = {}
    for cli in clients[:4]:
        ipdv_streaming[cli.name] = medir_ipdv(cli, VIP_STREAMING, count=MIN_PACKETS)
        ipdv_voip[cli.name] = medir_ipdv(cli, VIP_VOIP, count=MIN_PACKETS)
        print(f"    {cli.name}: Streaming={ipdv_streaming[cli.name]['jitter_mdev']:.2f}ms, "
              f"VoIP={ipdv_voip[cli.name]['jitter_mdev']:.2f}ms")

    # Calcular promedios con netem activo
    perdida_vals = [v['porcentaje'] for v in iplr_stress.values()]
    perdida_general = round(statistics.mean(perdida_vals), 2) if perdida_vals else 0.0
    jitter_vals = [v['jitter_mdev'] for v in ipdv_stress.values()]
    jitter_avg = round(statistics.mean(jitter_vals), 2) if jitter_vals else 0.0
    lat_vals = [v['avg'] for v in iptd_stress.values() if v['avg'] > 0]
    latencia_avg = round(statistics.mean(lat_vals), 2) if lat_vals else 0.0

    # ─── Limpiar netem ───
    limpiar_netem(clients)
    limpiar_iperf(servers)

    # ─── FASE 6: Throughput desde servidores ───
    print("\n--- Fase 6: Throughput desde servidores ---")
    throughput_srv = {}
    for srv in servers:
        tp = medir_throughput_servidor(srv, clients[0], port=5001, duration=5)
        throughput_srv[srv.name] = tp
        print(f"    {clients[0].name} → {srv.name}: {tp:.2f} Mbps")

    # ─── FASE 7: Back-to-Back ───
    print("\n--- Midiendo Back-to-Back Frames ---")
    b2b = medir_back_to_back(clients[0], servers[0], port=5002)

    # ─── FASE 8: Equidad ───
    cpus, rams = leer_equidad_servidores()

    # Compilar métricas
    metricas = {
        'iplr': iplr_stress,
        'iptd': iptd_stress,
        'ipdv': ipdv_stress,
        'throughput': throughput_srv,
        'perdida_general': perdida_general,
        'jitter_avg': jitter_avg,
        'latencia_avg': latencia_avg,
        'latencia_base': latencias_base,
        'latencia_congestion': {k: v for k, v in iptd_stress.items()},
        'throughput_congestion': throughputs,
        'back_to_back': b2b,
        'equidad': calcular_equidad(cpus, rams),
        'ipdv_streaming': ipdv_streaming,
        'ipdv_voip': ipdv_voip
    }

    if perdida_general == 0:
        print("\n    ⚠️  ADVERTENCIA: Pérdida = 0%. Verificar configuración.")
    else:
        print(f"\n    ✅ Pérdida detectada: {perdida_general}%")

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

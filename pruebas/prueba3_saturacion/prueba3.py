#!/usr/bin/env python3
"""
=============================================================
 PRUEBA 3: Estrés Crítico (Saturación)
 Carga: Alta (>250 pps) con iperf masivo
 Objetivo: Superar BW del enlace troncal (10 Mbps) para
           GARANTIZAR pérdida de paquetes medible.
 Métricas: IPLR (OBLIGATORIO >0%), IPTD, IPDV, Throughput,
           Back-to-Back, System Recovery
=============================================================
"""
import os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from test_common import *

MODO = parse_modo()
PRUEBA_NUM = 3
PRUEBA_NOMBRE = "Estrés Crítico (Saturación)"
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

    # ─── FASE 1: Servidores iperf ───
    print("\n--- Fase 1: Iniciando servidores iperf ---")
    for srv in servers:
        srv.cmd("iperf -s -p 8080 &")
        print(f"    {srv.name} escuchando en puerto 8080")
    time.sleep(2)

    # ─── FASE 2: Condiciones de red realistas ───
    print("\n--- Fase 2: Aplicando netem (delay + loss) ---")
    for cli in clients:
        cli.cmd(f"tc qdisc replace dev {cli.name}-eth0 root "
                f"netem delay 15ms 5ms loss 5% 25%")
        print(f"    {cli.name}: delay 15ms ±5ms, loss 5%")

    # ─── FASE 3: Inyección masiva para SATURAR el enlace de 10 Mbps ───
    print(f"\n--- Fase 3: Inyección masiva ({DURACION}s) ---")
    print(f"    OBJETIVO: Superar {BW_TRUNK} Mbps troncal → pérdida GARANTIZADA")
    for cli in clients:
        cli.cmd(f"iperf -c {VIP_STREAMING} -p 8080 -t {DURACION} -P 5 "
                f"-b 5M -w 256k -i 1 -f m > /tmp/stress_{cli.name}.log 2>&1 &")
        cli.cmd(f"for i in $(seq 1 {MIN_PACKETS}); do "
                f"curl -s -o /dev/null --connect-timeout 2 http://{VIP_WEB}/; "
                f"sleep 0.05; done &")
        print(f"    {cli.name} → 5 flujos × 5Mbps + {MIN_PACKETS} HTTP")

    # ─── FASE 4: Medir IPLR/IPTD/IPDV DURANTE la saturación (mid-stress) ───
    print("\n--- Fase 4: Esperando 30s para medir DURANTE la saturación ---")
    time.sleep(30)

    print("\n--- Midiendo IPLR/IPTD/IPDV CON estrés activo ---")
    iplr_stress = {}
    iptd_stress = {}
    ipdv_stress = {}
    for cli in clients:
        iplr_stress[cli.name] = medir_iplr(cli, VIP_WEB, count=MIN_PACKETS)
        iptd_stress[cli.name] = medir_iptd(cli, VIP_WEB, count=20)
        ipdv_stress[cli.name] = medir_ipdv(cli, VIP_WEB, count=MIN_PACKETS)
        print(f"    {cli.name}: IPLR={iplr_stress[cli.name]['porcentaje']}%, "
              f"IPTD={iptd_stress[cli.name]['avg']:.2f}ms, "
              f"IPDV={ipdv_stress[cli.name]['jitter_mdev']:.2f}ms")

    # Calcular promedios bajo estrés
    perdida_vals = [v['porcentaje'] for v in iplr_stress.values()]
    perdida_general = round(statistics.mean(perdida_vals), 2) if perdida_vals else 0.0
    jitter_vals = [v['jitter_mdev'] for v in ipdv_stress.values()]
    jitter_avg = round(statistics.mean(jitter_vals), 2) if jitter_vals else 0.0
    lat_vals = [v['avg'] for v in iptd_stress.values() if v['avg'] > 0]
    latencia_avg = round(statistics.mean(lat_vals), 2) if lat_vals else 0.0

    # Esperar a que termine el iperf restante
    remaining = max(0, DURACION - 50)
    if remaining > 0:
        print(f"    Esperando {remaining}s restantes...")
        time.sleep(remaining)

    # ─── FASE 5: Recoger throughput ───
    print("\n--- Fase 5: Recopilando throughput ---")
    throughputs = {}
    for cli in clients:
        tp = medir_throughput_iperf_log(cli, f"/tmp/stress_{cli.name}.log")
        throughputs[cli.name] = tp
        print(f"    {cli.name}: {tp:.2f} Mbps")

    # ─── FASE 6: IPDV Streaming (8080) y VoIP (5060) ───
    print("\n--- IPDV para Streaming y VoIP ---")
    ipdv_streaming = {}
    ipdv_voip = {}
    for cli in clients[:4]:
        ipdv_streaming[cli.name] = medir_ipdv(cli, VIP_STREAMING, count=MIN_PACKETS)
        ipdv_voip[cli.name] = medir_ipdv(cli, VIP_VOIP, count=MIN_PACKETS)
        print(f"    {cli.name}: Streaming={ipdv_streaming[cli.name]['jitter_mdev']:.2f}ms, "
              f"VoIP={ipdv_voip[cli.name]['jitter_mdev']:.2f}ms")

    # ─── FASE 7: Back-to-Back (con netem aún activo) ───
    print("\n--- Midiendo Back-to-Back Frames ---")
    b2b = medir_back_to_back(clients[0], servers[0], port=5002)

    # ─── FASE 8: Recovery Time ───
    print("\n--- Midiendo System Recovery ---")
    limpiar_netem(clients)
    limpiar_iperf(servers)
    recovery = medir_recovery_time(clients[0], servers[0].IP())
    if recovery['estable']:
        print(f"    ✅ Sistema estable en {recovery['recovery_s']}s")
    else:
        print(f"    ⚠️  No se alcanzó estabilidad en {recovery['recovery_s']}s")

    # ─── FASE 8: Throughput post-limpieza ───
    print("\n--- Throughput post-limpieza ---")
    throughput_srv = {}
    for srv in servers:
        tp = medir_throughput_servidor(srv, clients[0], port=5001, duration=5)
        throughput_srv[srv.name] = tp
        print(f"    {srv.name}: {tp:.2f} Mbps")

    # ─── FASE 9: Equidad ───
    cpus, rams = leer_equidad_servidores()

    # Compilar métricas (las medidas DURANTE el estrés)
    metricas = {
        'iplr': iplr_stress,
        'iptd': iptd_stress,
        'ipdv': ipdv_stress,
        'throughput': throughput_srv,
        'perdida_general': perdida_general,
        'jitter_avg': jitter_avg,
        'latencia_avg': latencia_avg,
        'throughput_iperf': throughputs,
        'back_to_back': b2b,
        'recovery': recovery,
        'equidad': calcular_equidad(cpus, rams),
        'ipdv_streaming': ipdv_streaming,
        'ipdv_voip': ipdv_voip
    }

    if metricas['perdida_general'] == 0:
        print("\n    ⚠️  ADVERTENCIA: Pérdida = 0%. Verificar topología.")
    else:
        print(f"\n    ✅ Pérdida detectada: {metricas['perdida_general']}%")

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

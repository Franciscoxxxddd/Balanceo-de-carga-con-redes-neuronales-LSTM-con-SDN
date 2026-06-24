#!/usr/bin/env python3
"""
=============================================================
 PRUEBA 9: Simulación de Caída de Servidor
 Carga: Media | srv4 CPU/RAM al 100%
 Objetivo: Validar descarte automático del nodo y medir
           pérdida de paquetes durante detección.
 Métricas: IPLR, IPTD, Throughput, Recovery, Equidad
 NOTA: Requiere 'stress' (sudo apt-get install stress)
=============================================================
"""
import os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from test_common import *

MODO = parse_modo()
PRUEBA_NUM = 9
PRUEBA_NOMBRE = "Simulación de Caída (Imputación)"
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
    srv4 = servers[3]

    # ─── FASE 1: Saturar srv4 (CPU+RAM al 100%) ───
    print("\n--- Fase 1: Saturando srv4 (CPU+RAM al 100%) ---")
    srv4.cmd("stress --cpu 4 --vm 2 --vm-bytes 128M --timeout 120 &")
    srv4.cmd(f"tc qdisc replace dev {srv4.name}-eth0 root "
             f"netem delay 500ms 200ms loss 30% 50%")
    print(f"    srv4: stress --cpu 4 --vm 2, delay 500ms, loss 30%")

    # Degradar algunos clientes también
    for cli in clients[:6]:
        cli.cmd(f"tc qdisc replace dev {cli.name}-eth0 root "
                f"netem delay 20ms 10ms loss 5% 25%")

    # Crear force_crash.txt para que el controlador lo detecte
    try:
        crash_path = os.path.join(BASE_DIR, 'force_crash.txt')
        with open(crash_path, 'w') as f:
            f.write('1')
    except Exception:
        pass

    # Forzar métricas en estado_red.json
    try:
        estado_path = os.path.join(BASE_DIR, 'estado_red.json')
        with open(estado_path, 'r') as f:
            estado = json.load(f)
        estado['ultimo_evento']['metricas']['srv4_cpu'] = 100.0
        estado['ultimo_evento']['metricas']['srv4_ram'] = 100.0
        with open(estado_path, 'w') as f:
            json.dump(estado, f)
    except Exception:
        pass

    time.sleep(5)

    # ─── FASE 2: Tráfico HTTP desde 12 hosts ───
    print(f"\n--- Fase 2: Tráfico HTTP desde 12 hosts ({DURACION}s) ---")
    for cli in clients:
        cli.cmd(f"for i in $(seq 1 {MIN_PACKETS}); do "
                f"curl -s -o /dev/null --connect-timeout 2 http://{VIP_WEB}/; "
                f"sleep 0.3; done &")

    # ─── FASE 3: Medir IPLR/IPTD/IPDV DURANTE la caída (mid-stress) ───
    print("\n--- Fase 3: Midiendo IPLR/IPTD/IPDV CON srv4 caído ---")
    time.sleep(15)

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

    # Calcular promedios bajo estrés
    perdida_vals = [v['porcentaje'] for v in iplr_stress.values()]
    perdida_general = round(statistics.mean(perdida_vals), 2) if perdida_vals else 0.0
    jitter_vals = [v['jitter_mdev'] for v in ipdv_stress.values()]
    jitter_avg = round(statistics.mean(jitter_vals), 2) if jitter_vals else 0.0
    lat_vals = [v['avg'] for v in iptd_stress.values() if v['avg'] > 0]
    latencia_avg = round(statistics.mean(lat_vals), 2) if lat_vals else 0.0

    time.sleep(max(0, DURACION - 40))

    # ─── FASE 4: Pérdida directa a srv4 ───
    print("\n--- Fase 4: Midiendo pérdida directa a srv4 ---")
    iplr_srv4 = medir_iplr(clients[0], srv4.IP(), count=30)
    print(f"    Pérdida directa a srv4: {iplr_srv4['porcentaje']}%")

    # ─── FASE 5: Throughput ───
    print("\n--- Fase 5: Throughput ---")
    throughputs = {}
    for srv in servers:
        srv.cmd("iperf -s -p 5001 &")
    time.sleep(1)
    for srv in servers:
        r = clients[0].cmd(f"iperf -c {srv.IP()} -p 5001 -t 5 -f m")
        m = re.search(r'([\d.]+)\s+Mbits/sec', r)
        throughputs[srv.name] = float(m.group(1)) if m else 0.0

    # ─── Limpiar ───
    srv4.cmd("killall stress 2>/dev/null")
    limpiar_netem([srv4] + clients[:6])
    limpiar_iperf(servers)
    try:
        os.remove(os.path.join(BASE_DIR, 'force_crash.txt'))
    except Exception:
        pass

    # ─── FASE 6: Back-to-Back ───
    print("\n--- Midiendo Back-to-Back Frames ---")
    b2b = medir_back_to_back(clients[0], servers[0], port=5002)

    # ─── FASE 7: Recovery Time ───
    print("\n--- Midiendo System Recovery ---")
    recovery = medir_recovery_time(clients[0], servers[0].IP())
    if recovery['estable']:
        print(f"    ✅ Sistema estable en {recovery['recovery_s']}s")
    else:
        print(f"    ⚠️  No se alcanzó estabilidad")

    # ─── Equidad ───
    cpus, rams = leer_equidad_servidores()

    # Compilar métricas (medidas DURANTE la caída)
    metricas = {
        'iplr': iplr_stress,
        'iptd': iptd_stress,
        'ipdv': ipdv_stress,
        'throughput': {k: v for k, v in throughputs.items()},
        'perdida_general': perdida_general,
        'jitter_avg': jitter_avg,
        'latencia_avg': latencia_avg,
        'throughput_caida': throughputs,
        'iplr_directo_srv4': iplr_srv4,
        'srv4_saturado': True,
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

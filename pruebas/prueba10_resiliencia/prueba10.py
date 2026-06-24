#!/usr/bin/env python3
"""
=============================================================
 PRUEBA 10: Resiliencia (Estabilidad a Largo Plazo)
 Carga: Fluctuante 70-300 pps | 15 minutos continuos
 Objetivo: Medir estabilidad a largo plazo y System Recovery
           global con tráfico determinista (seed=42).
 Métricas: IPLR, IPTD, Throughput, Recovery, Equidad temporal
=============================================================
"""
import os, sys, time, random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from test_common import *

MODO = parse_modo()
PRUEBA_NUM = 10
PRUEBA_NOMBRE = "Resiliencia (Estabilidad a Largo Plazo)"
RESULTADO_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    f"resultado_prueba{PRUEBA_NUM}_{MODO}.json")
DURACION = 900  # 15 minutos


def run():
    # Generador determinista para tráfico fluctuante
    rng_traffic = random.Random(SEED)

    net = Mininet(controller=RemoteController, switch=OVSKernelSwitch)
    print_header(PRUEBA_NUM, PRUEBA_NOMBRE, MODO)
    print(f"  DURACIÓN: 15 MINUTOS")
    print(f"{'=' * 60}\n")

    c0 = net.addController('c0', ip='127.0.0.1', port=6633)
    servers, clients = crear_topologia(net)
    net.start()

    print(">>> Iniciando servicios...")
    iniciar_servicios(servers)
    time.sleep(3)

    monitor = MonitorController()
    monitor.start()

    resultados = init_resultados(PRUEBA_NUM, PRUEBA_NOMBRE, MODO, DURACION)

    latencia_temporal = []
    equidad_samples = []

    print(f"\n>>> Iniciando prueba de resiliencia (15 minutos)...")
    t_start = time.time()
    ciclo = 0

    while (time.time() - t_start) < DURACION:
        ciclo += 1
        elapsed = int(time.time() - t_start)
        minutos = elapsed // 60
        segundos = elapsed % 60
        print(f"\n--- Ciclo {ciclo} ({minutos}m {segundos}s / 15m) ---")

        # Tráfico fluctuante determinista (seed=42)
        n_requests = rng_traffic.choice([MIN_PACKETS, 80, 100, 150, 200, 250, 300])
        sleep_interval = rng_traffic.choice([0.02, 0.05, 0.1, 0.2, 0.5])
        n_clients = rng_traffic.randint(2, 12)
        selected = rng_traffic.sample(clients, n_clients)

        print(f"    {n_clients} clientes × {n_requests} paquetes "
              f"(sleep={sleep_interval}s)")

        for cli in selected:
            cli.cmd(f"for i in $(seq 1 {n_requests}); do "
                    f"curl -s -o /dev/null --connect-timeout 2 "
                    f"http://{VIP_WEB}/; sleep {sleep_interval}; done &")

        # Cada 3 ciclos: medir latencia
        if ciclo % 3 == 0:
            lat = medir_iptd(clients[0], servers[0].IP(), count=3)
            latencia_temporal.append({
                'ciclo': ciclo,
                'tiempo_s': elapsed,
                'latencia_avg': lat['avg'],
                'loss': lat['loss']
            })
            print(f"    Latencia: {lat['avg']:.2f}ms, loss: {lat['loss']}%")

        # Cada 5 ciclos: medir equidad
        if ciclo % 5 == 0:
            cpus, rams = leer_equidad_servidores()
            equidad_samples.append({
                'tiempo': elapsed,
                'cpus': cpus,
                'rams': rams,
                'cpu_std': statistics.stdev(cpus) if len(cpus) > 1 else 0,
                'ram_std': statistics.stdev(rams) if len(rams) > 1 else 0
            })

        time.sleep(30)  # 30s entre ciclos

    # ─── Métricas finales ───
    print("\n--- Métricas finales post-resiliencia ---")
    metricas = medir_metricas_completas(clients, servers, VIP_WEB)

    # ─── Throughput final ───
    print("\n--- Throughput final ---")
    throughputs = {}
    for srv in servers:
        tp = medir_throughput_servidor(srv, clients[0], port=5001, duration=5)
        throughputs[srv.name] = tp
        print(f"    {clients[0].name} → {srv.name}: {tp:.2f} Mbps")
    metricas['throughput_final'] = throughputs

    # ─── Recovery global ───
    print("\n--- System Recovery global ---")
    recovery = medir_recovery_time(clients[0], servers[0].IP())
    metricas['recovery'] = recovery

    # ─── Back-to-Back ───
    print("\n--- Midiendo Back-to-Back Frames ---")
    metricas['back_to_back'] = medir_back_to_back(clients[0], servers[0], port=5002)

    # ─── Equidad final ───
    cpus, rams = leer_equidad_servidores()
    metricas['equidad'] = calcular_equidad(cpus, rams)

    metricas['latencia_temporal'] = latencia_temporal
    metricas['equidad_temporal'] = equidad_samples
    metricas['total_ciclos'] = ciclo
    metricas['duracion_real_s'] = int(time.time() - t_start)

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

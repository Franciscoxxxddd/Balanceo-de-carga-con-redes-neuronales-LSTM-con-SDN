#!/usr/bin/env python3
"""
=================================================================
 MÓDULO COMÚN PARA LAS 10 PRUEBAS COMPARATIVAS SDN (RR vs IA)
 Métricas: ITU-T Y.1540 (IPLR, IPTD, IPDV) + RFC 2544
 Topología: BW limitado con colas restrictivas
 Semilla: seed=42 para reproducibilidad
=================================================================
"""

import os
import sys
import time
import json
import re
import random
import statistics
import subprocess
import threading

from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.link import TCLink

# ─── CONSTANTES GLOBALES ─────────────────────────────────────
SEED = 42                            # Semilla fija para reproducibilidad
RNG = random.Random(SEED)            # Generador determinista compartido
BW_TRUNK = 10                        # Ancho de banda troncal (Mbps)
BW_ACCESS = 100                      # Ancho de banda de acceso (Mbps)
QUEUE_SIZE = 50                      # Tamaño de cola en switches core
MIN_PACKETS = 70                     # Mínimo de paquetes por flujo

# IPs Virtuales (VIPs)
VIP_WEB = "10.0.0.100"
VIP_STREAMING = "10.0.0.101"
VIP_DATABASE = "10.0.0.200"
VIP_VOIP = "10.0.0.201"

# IPs de servidores reales
SERVER_IPS = ["10.0.0.1", "10.0.0.2", "10.0.0.3", "10.0.0.4"]

# Ruta base del proyecto
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


# ─── PARSEO DE ARGUMENTOS ────────────────────────────────────
def parse_modo():
    """Parsea el argumento RR|IA de la línea de comandos"""
    if len(sys.argv) > 1:
        modo = sys.argv[1].upper()
        if modo in ["RR", "IA"]:
            return modo
    print(f"Uso: sudo python3 {sys.argv[0]} [RR|IA]")
    sys.exit(1)


# ─── MONITOREO DEL CONTROLADOR ───────────────────────────────
class MonitorController:
    """Hilo que monitorea CPU/RAM del proceso ryu-manager"""

    def __init__(self):
        self.stats = []
        self.active = True
        self._thread = None

    def start(self):
        """Inicia el hilo de monitoreo"""
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Detiene el monitoreo"""
        self.active = False
        time.sleep(1)

    def _loop(self):
        """Bucle principal de monitoreo"""
        while self.active:
            try:
                r = subprocess.run(
                    ['bash', '-c',
                     "ps aux | grep '[r]yu-manager' | head -1 | awk '{print $3, $4, $6}'"],
                    capture_output=True, text=True, timeout=5
                )
                parts = r.stdout.strip().split()
                if len(parts) >= 3:
                    self.stats.append({
                        'timestamp': time.time(),
                        'cpu_percent': float(parts[0]),
                        'ram_percent': float(parts[1]),
                        'ram_kb': int(parts[2])
                    })
            except Exception:
                pass
            time.sleep(1)

    def get_summary(self):
        """Retorna resumen estadístico del monitoreo"""
        if not self.stats:
            return {'muestras': 0, 'cpu_avg': 0, 'cpu_max': 0,
                    'ram_avg': 0, 'ram_max': 0, 'historial': []}
        return {
            'muestras': len(self.stats),
            'cpu_avg': statistics.mean([s['cpu_percent'] for s in self.stats]),
            'cpu_max': max([s['cpu_percent'] for s in self.stats]),
            'ram_avg': statistics.mean([s['ram_percent'] for s in self.stats]),
            'ram_max': max([s['ram_percent'] for s in self.stats]),
            'historial': self.stats
        }


# ─── TOPOLOGÍA ───────────────────────────────────────────────
def crear_topologia(net):
    """
    Crea la topología con 3 switches, 4 servidores, 12 clientes.
    Enlaces troncales limitados a 10 Mbps con colas de 50 paquetes
    para garantizar pérdida observable bajo estrés.
    """
    # Switches OpenFlow 1.3
    s1 = net.addSwitch('s1', protocols='OpenFlow13')  # Servidores
    s3 = net.addSwitch('s3', protocols='OpenFlow13')  # Core
    s4 = net.addSwitch('s4', protocols='OpenFlow13')  # Clientes

    # 4 Servidores con MACs fijas
    srv1 = net.addHost('srv1', ip='10.0.0.1', mac='00:00:00:00:00:01')
    srv2 = net.addHost('srv2', ip='10.0.0.2', mac='00:00:00:00:00:02')
    srv3 = net.addHost('srv3', ip='10.0.0.3', mac='00:00:00:00:00:03')
    srv4 = net.addHost('srv4', ip='10.0.0.4', mac='00:00:00:00:00:04')

    # 12 Clientes
    clients_hosts = []
    for i in range(1, 13):
        h = net.addHost(f'cli{i}', ip=f'10.0.0.{10 + i}')
        clients_hosts.append(h)

    servers = [srv1, srv2, srv3, srv4]

    # Enlaces de acceso: servidores → s1 (100 Mbps)
    for h in servers:
        net.addLink(s1, h, cls=TCLink, bw=BW_ACCESS)

    # Enlaces de acceso: clientes → s4 (100 Mbps)
    for h in clients_hosts:
        net.addLink(s4, h, cls=TCLink, bw=BW_ACCESS)

    # Enlaces troncales con BW limitado y cola restrictiva
    net.addLink(s1, s3, cls=TCLink, bw=BW_TRUNK, max_queue_size=QUEUE_SIZE)
    net.addLink(s4, s3, cls=TCLink, bw=BW_TRUNK, max_queue_size=QUEUE_SIZE)

    return servers, clients_hosts


def iniciar_servicios(servers):
    """Inicia los 4 servicios HTTP en cada servidor"""
    for srv in servers:
        for name, port in [("WEB", 80), ("STREAMING", 8080),
                           ("DATABASE", 3306), ("VOIP", 5060)]:
            d = f"/tmp/{srv.name}_{name}_{port}"
            srv.cmd(f"mkdir -p {d}")
            srv.cmd(f"echo '<h1>{name} en {srv.name}</h1>' > {d}/index.html")
            srv.cmd(f"cd {d} && python3 -m http.server {port} > {d}/http.log 2>&1 &")


# ─── MÉTRICAS ITU-T Y.1540 ──────────────────────────────────

def medir_iptd(src, dst_ip, count=20):
    """
    IP Packet Transfer Delay (ITU-T Y.1540)
    Retorna: dict con min/avg/max/mdev/loss
    """
    result = src.cmd(f"ping -c {count} -W 2 -i 0.1 {dst_ip}")
    m = re.search(
        r'rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)', result)
    if m:
        loss_m = re.search(r'([\d.]+)% packet loss', result)
        loss = float(loss_m.group(1)) if loss_m else 0.0
        return {
            'min': float(m.group(1)),
            'avg': float(m.group(2)),
            'max': float(m.group(3)),
            'mdev': float(m.group(4)),
            'loss': loss
        }
    loss_m = re.search(r'([\d.]+)% packet loss', result)
    loss = float(loss_m.group(1)) if loss_m else 100.0
    return {'min': 0, 'avg': 0, 'max': 0, 'mdev': 0, 'loss': loss}


def medir_iplr(src, dst_ip, count=50):
    """
    IP Packet Loss Ratio (ITU-T Y.1540)
    Mide el PORCENTAJE EXACTO de paquetes perdidos con precisión decimal.
    Retorna: dict con enviados, recibidos, perdidos, porcentaje
    """
    result = src.cmd(f"ping -c {count} -W 2 -i 0.05 {dst_ip}")
    # Extraer paquetes transmitidos y recibidos
    tx_m = re.search(r'(\d+) packets transmitted', result)
    rx_m = re.search(r'(\d+) received', result)
    loss_m = re.search(r'([\d.]+)% packet loss', result)

    enviados = int(tx_m.group(1)) if tx_m else count
    recibidos = int(rx_m.group(1)) if rx_m else 0
    perdidos = enviados - recibidos
    porcentaje = float(loss_m.group(1)) if loss_m else (
        (perdidos / enviados * 100) if enviados > 0 else 100.0)

    return {
        'enviados': enviados,
        'recibidos': recibidos,
        'perdidos': perdidos,
        'porcentaje': round(porcentaje, 2)
    }


def medir_ipdv(src, dst_ip, count=50):
    """
    IP Packet Delay Variation (ITU-T Y.1540) - Jitter
    Extrae mdev del ping como métrica de jitter.
    """
    result = src.cmd(f"ping -c {count} -W 2 -i 0.05 {dst_ip}")
    m = re.search(
        r'rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)', result)
    if m:
        return {
            'avg_delay': float(m.group(2)),
            'jitter_mdev': float(m.group(4)),
            'min': float(m.group(1)),
            'max': float(m.group(3))
        }
    return {'avg_delay': 0, 'jitter_mdev': 0, 'min': 0, 'max': 0}


# ─── MÉTRICAS RFC 2544 ──────────────────────────────────────

def medir_throughput_servidor(server_host, client_host, port=5001, duration=10):
    """
    Throughput (RFC 2544) - Medido DESDE LA PERSPECTIVA DEL SERVIDOR.
    Retorna throughput en Mbps.
    """
    server_host.cmd(f"iperf -s -p {port} &")
    time.sleep(1)
    # -r hace bidireccional; usamos -f m para Mbps
    result = client_host.cmd(
        f"iperf -c {server_host.IP()} -p {port} -t {duration} -f m")
    server_host.cmd(f"kill %iperf 2>/dev/null")

    # Parsear resultado
    m = re.search(r'([\d.]+)\s+Mbits/sec', result)
    return float(m.group(1)) if m else 0.0


def medir_throughput_iperf_log(client_host, log_path):
    """Extrae throughput del log de iperf de un cliente"""
    r = client_host.cmd(f"cat {log_path} 2>/dev/null | tail -30")
    # Priorizar líneas [SUM] para múltiples flujos
    sum_matches = re.findall(r'\[SUM\].*?([\d.]+)\s+([MGK]?)bits/sec', r)
    if sum_matches:
        val, unit = sum_matches[-1]
        val = float(val)
        return val * 1000 if unit == 'G' else (val / 1000 if unit == 'K' else val)
    matches = re.findall(r'([\d.]+)\s+([MGK]?)bits/sec', r)
    if matches:
        val, unit = matches[-1]
        val = float(val)
        return val * 1000 if unit == 'G' else (val / 1000 if unit == 'K' else val)
    return 0.0


def medir_back_to_back(client_host, server_host, port=5001):
    """
    Back-to-Back Frames (RFC 2544)
    Envía ráfagas de tamaño creciente y mide cuántos paquetes
    se absorben antes de la primera pérdida.
    """
    results = {}
    server_host.cmd(f"iperf -s -u -p {port} &")
    time.sleep(1)

    for burst in [10, 50, 100, 200, 500]:
        # Ráfaga UDP con -n (bytes) a máxima velocidad
        r = client_host.cmd(
            f"iperf -c {server_host.IP()} -u -p {port} -l 1470 "
            f"-b 100m -n {burst * 1470} -f m 2>&1")
        # Buscar datagrams perdidos
        loss_m = re.search(r'([\d.]+)%', r)
        lost_m = re.search(r'(\d+)/\s*(\d+)', r)
        results[f'burst_{burst}'] = {
            'frames_enviados': burst,
            'loss_percent': float(loss_m.group(1)) if loss_m else 0,
            'detalle': lost_m.group(0) if lost_m else 'N/A'
        }

    server_host.cmd(f"kill %iperf 2>/dev/null")
    return results


def medir_recovery_time(client_host, target_ip, max_wait=60):
    """
    System Recovery (RFC 2544)
    Mide el tiempo en segundos para volver a un estado estable
    después de una sobrecarga. Retorna tiempo en ms.
    """
    # Medir latencia actual como baseline
    baseline = medir_iptd(client_host, target_ip, count=3)
    baseline_avg = baseline['avg'] if baseline['avg'] > 0 else 999
    # Umbral: latencia < 50ms o mejora del 50%
    threshold = min(50.0, baseline_avg * 0.5)

    for check in range(1, max_wait + 1):
        time.sleep(1)
        lat = medir_iptd(client_host, target_ip, count=2)
        if lat['avg'] > 0 and lat['avg'] <= threshold:
            return {
                'recovery_s': check,
                'recovery_ms': check * 1000,
                'latencia_final': lat['avg'],
                'latencia_inicial': baseline_avg,
                'estable': True
            }
    return {
        'recovery_s': max_wait,
        'recovery_ms': max_wait * 1000,
        'latencia_final': baseline_avg,
        'latencia_inicial': baseline_avg,
        'estable': False
    }


# ─── EQUIDAD DE SERVIDORES ───────────────────────────────────

def leer_equidad_servidores():
    """Lee CPU/RAM de los 4 servidores desde estado_red.json"""
    try:
        path = os.path.join(BASE_DIR, 'estado_red.json')
        with open(path, 'r') as f:
            estado = json.load(f)
        mets = estado.get('ultimo_evento', {}).get('metricas', {})
        cpus = [mets.get(f'srv{i}_cpu', 0) for i in range(1, 5)]
        rams = [mets.get(f'srv{i}_ram', 0) for i in range(1, 5)]
        return cpus, rams
    except Exception:
        return [0] * 4, [0] * 4


def calcular_equidad(cpus, rams):
    """Calcula estadísticas de equidad"""
    return {
        'cpu': {
            'valores': cpus,
            'promedio': statistics.mean(cpus),
            'desviacion_std': statistics.stdev(cpus) if len(cpus) > 1 else 0
        },
        'ram': {
            'valores': rams,
            'promedio': statistics.mean(rams),
            'desviacion_std': statistics.stdev(rams) if len(rams) > 1 else 0
        }
    }


# ─── MÉTRICAS COMPLETAS ─────────────────────────────────────

def medir_metricas_completas(clients, servers, vip=VIP_WEB):
    """
    Mide TODAS las métricas obligatorias ITU-T Y.1540 + RFC 2544
    de forma estandarizada para todos los clientes.
    """
    print("\n--- Midiendo IPLR (Pérdida de Paquetes) ---")
    iplr = {}
    for cli in clients:
        iplr[cli.name] = medir_iplr(cli, vip, count=MIN_PACKETS)
        print(f"    {cli.name}: {iplr[cli.name]['porcentaje']}% "
              f"({iplr[cli.name]['perdidos']}/{iplr[cli.name]['enviados']})")

    print("\n--- Midiendo IPTD (Latencia) ---")
    iptd = {}
    for cli in clients:
        iptd[cli.name] = medir_iptd(cli, vip, count=20)
        print(f"    {cli.name}: avg={iptd[cli.name]['avg']:.2f}ms")

    print("\n--- Midiendo IPDV (Jitter) ---")
    ipdv = {}
    for cli in clients:
        ipdv[cli.name] = medir_ipdv(cli, vip, count=MIN_PACKETS)
        print(f"    {cli.name}: jitter={ipdv[cli.name]['jitter_mdev']:.2f}ms")

    print("\n--- Midiendo IPDV Streaming (8080) y VoIP (5060) ---")
    ipdv_streaming = {}
    ipdv_voip = {}
    for cli in clients[:4]:
        ipdv_streaming[cli.name] = medir_ipdv(cli, VIP_STREAMING, count=MIN_PACKETS)
        ipdv_voip[cli.name] = medir_ipdv(cli, VIP_VOIP, count=MIN_PACKETS)
        print(f"    {cli.name}: Streaming={ipdv_streaming[cli.name]['jitter_mdev']:.2f}ms, "
              f"VoIP={ipdv_voip[cli.name]['jitter_mdev']:.2f}ms")

    print("\n--- Midiendo Throughput (desde servidores) ---")
    throughput = {}
    for srv in servers:
        tp = medir_throughput_servidor(srv, clients[0], port=5001, duration=5)
        throughput[srv.name] = tp
        print(f"    {clients[0].name} → {srv.name}: {tp:.2f} Mbps")

    # Calcular pérdida general
    perdida_valores = [v['porcentaje'] for v in iplr.values()]
    perdida_general = round(statistics.mean(perdida_valores), 2) if perdida_valores else 0.0
    print(f"\n    ══ IPLR GENERAL: {perdida_general}% ══")

    # Jitter promedio
    jitter_valores = [v['jitter_mdev'] for v in ipdv.values()]
    jitter_avg = round(statistics.mean(jitter_valores), 2) if jitter_valores else 0.0

    # Latencia promedio
    lat_valores = [v['avg'] for v in iptd.values() if v['avg'] > 0]
    latencia_avg = round(statistics.mean(lat_valores), 2) if lat_valores else 0.0

    return {
        'iplr': iplr,
        'iptd': iptd,
        'ipdv': ipdv,
        'throughput': throughput,
        'perdida_general': perdida_general,
        'jitter_avg': jitter_avg,
        'latencia_avg': latencia_avg,
        'ipdv_streaming': ipdv_streaming,
        'ipdv_voip': ipdv_voip
    }


# ─── DECISIONES DEL CONTROLADOR ─────────────────────────────

def capturar_decisiones(modo, test_start_ts):
    """Lee decisiones del controlador desde estado_red_log.json"""
    decisiones = []
    log_path = os.path.join(BASE_DIR, 'estado_red_log.json')
    try:
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                        evt = ev.get('e', {})
                        if evt.get('modo', '') == modo:
                            decisiones.append({
                                'timestamp': ev.get('t', 0),
                                'cliente': evt.get('cliente', ''),
                                'servicio': evt.get('servicio', ''),
                                'servidor': evt.get('servidor_elegido', ''),
                                'modo': modo,
                                'mets': evt.get('metricas', {})
                            })
                    except Exception:
                        pass
    except Exception:
        pass

    # Filtrar solo decisiones de esta prueba
    decisiones_test = [d for d in decisiones
                       if d.get('timestamp', 0) >= test_start_ts]
    return decisiones_test


def calcular_response_time(decisiones_test):
    """Calcula tiempo de respuesta promedio del controlador"""
    if len(decisiones_test) >= 2:
        timestamps = sorted([d['timestamp'] for d in decisiones_test
                             if d.get('timestamp', 0) > 0])
        if len(timestamps) >= 2:
            intervals = [timestamps[i + 1] - timestamps[i]
                         for i in range(len(timestamps) - 1)]
            avg_ms = statistics.mean(intervals) * 1000
            return round(avg_ms, 2), len(timestamps)
    return 0, len(decisiones_test)


# ─── RESULTADOS ──────────────────────────────────────────────

def init_resultados(prueba_num, prueba_nombre, modo, duracion):
    """Crea el diccionario base de resultados"""
    controlador = "ryu_service_rr.py" if modo == "RR" else "ryu_service_ai.py"
    return {
        'prueba': prueba_num,
        'nombre': prueba_nombre,
        'modo': modo,
        'controlador': controlador,
        'seed': SEED,
        'bw_trunk_mbps': BW_TRUNK,
        'bw_access_mbps': BW_ACCESS,
        'queue_size': QUEUE_SIZE,
        'inicio': time.strftime('%Y-%m-%d %H:%M:%S'),
        'duracion_config': duracion,
        'metricas': {}
    }


def finalizar_resultados(resultados, monitor, modo):
    """Completa los resultados con stats del controlador y decisiones"""
    resultados['controlador_stats'] = monitor.get_summary()
    resultados['fin'] = time.strftime('%Y-%m-%d %H:%M:%S')

    # Capturar decisiones
    test_start_ts = time.mktime(
        time.strptime(resultados['inicio'], '%Y-%m-%d %H:%M:%S'))
    decisiones = capturar_decisiones(modo, test_start_ts)
    avg_ms, total = calcular_response_time(decisiones)
    resultados['response_time_avg_ms'] = avg_ms
    resultados['response_time_total_decisions'] = total
    resultados['decisiones'] = decisiones[-200:]

    return resultados


def guardar_resultados(resultados, filepath):
    """Guarda resultados en JSON"""
    with open(filepath, 'w') as f:
        json.dump(resultados, f, indent=2)
    print(f"\n{'=' * 60}")
    print(f"  RESULTADOS GUARDADOS: {filepath}")
    print(f"  Controlador CPU avg: {resultados['controlador_stats']['cpu_avg']:.2f}%")
    print(f"  IPLR General: {resultados['metricas'].get('perdida_general', 'N/A')}%")
    print(f"  Response Time: {resultados.get('response_time_avg_ms', 0)}ms")
    print(f"{'=' * 60}\n")


# ─── UTILIDADES ──────────────────────────────────────────────

def print_header(prueba_num, prueba_nombre, modo):
    """Imprime encabezado de la prueba"""
    print(f"\n{'=' * 60}")
    print(f"  PRUEBA {prueba_num}: {prueba_nombre} [{modo}]")
    print(f"  Seed: {SEED} | BW Troncal: {BW_TRUNK} Mbps | Cola: {QUEUE_SIZE}")
    print(f"{'=' * 60}\n")


def limpiar_netem(hosts):
    """Limpia reglas tc netem de una lista de hosts"""
    for h in hosts:
        h.cmd(f"tc qdisc del dev {h.name}-eth0 root 2>/dev/null")


def limpiar_iperf(servers):
    """Detiene iperf en todos los servidores"""
    for srv in servers:
        srv.cmd("kill %iperf 2>/dev/null; killall iperf 2>/dev/null")

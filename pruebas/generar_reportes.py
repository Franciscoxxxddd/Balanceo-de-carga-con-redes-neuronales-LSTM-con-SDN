#!/usr/bin/env python3
"""
=================================================================
 GENERADOR DE REPORTES COMPARATIVOS (RR vs IA)
 
 Genera 3 reportes separados:
   1. Métricas Globales (ITU-T Y.1540 + RFC 2544)
   2. Asignación Comparativa (servidor por petición)
   3. Conmutación por Saturación (exclusivo IA)
 
 Uso: python3 generar_reportes.py
=================================================================
"""

import os
import json
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_DIR = os.path.join(BASE_DIR, 'reportes')

PRUEBAS = [
    (1, 'prueba1_trafico_base', 'Tráfico Base'),
    (2, 'prueba2_operacion_diaria', 'Operación Diaria'),
    (3, 'prueba3_saturacion', 'Estrés Crítico'),
    (4, 'prueba4_streaming', 'Streaming'),
    (5, 'prueba5_rafagas', 'Ráfagas'),
    (6, 'prueba6_jitter', 'Jitter'),
    (7, 'prueba7_packet_loss', 'Congestión'),
    (8, 'prueba8_trafico_mixto', 'Tráfico Mixto'),
    (9, 'prueba9_caida', 'Caída Servidor'),
    (10, 'prueba10_resiliencia', 'Resiliencia'),
]


def cargar_resultado(prueba_dir, modo):
    """Carga el JSON de resultados de una prueba"""
    num = prueba_dir.split('_')[0].replace('prueba', '')
    path = os.path.join(BASE_DIR, prueba_dir, f'resultado_prueba{num}_{modo}.json')
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"  ⚠️  Error cargando {path}: {e}")
        return None


def extraer_metricas_resumen(resultado):
    """Extrae las métricas clave de un resultado"""
    if not resultado:
        return None
    m = resultado.get('metricas', {})
    return {
        'iplr_percent': m.get('perdida_general', 0),
        'iptd_avg_ms': m.get('latencia_avg', 0),
        'ipdv_jitter_ms': m.get('jitter_avg', 0),
        'throughput': m.get('throughput', {}),
        'recovery_s': m.get('recovery', {}).get('recovery_s', None),
        'recovery_ms': m.get('recovery', {}).get('recovery_ms', None),
        'equidad_cpu_std': m.get('equidad', {}).get('cpu', {}).get('desviacion_std', None),
        'equidad_ram_std': m.get('equidad', {}).get('ram', {}).get('desviacion_std', None),
        'response_time_ms': resultado.get('response_time_avg_ms', 0),
        'total_decisiones': resultado.get('response_time_total_decisions', 0),
    }


def generar_reporte_metricas_globales():
    """
    REPORTE 1: Métricas Globales
    Compara IPLR, IPTD, IPDV, Throughput, Recovery para RR vs IA
    """
    print("\n═══ REPORTE 1: MÉTRICAS GLOBALES (ITU-T + RFC 2544) ═══")
    reporte = {
        'titulo': 'Reporte de Métricas Globales - RR vs IA',
        'generado': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'estandares': ['ITU-T Y.1540 (IPLR, IPTD, IPDV)', 'RFC 2544 (Throughput, Back-to-Back, Recovery)'],
        'pruebas': []
    }

    for num, dir_name, nombre in PRUEBAS:
        rr = cargar_resultado(dir_name, 'RR')
        ia = cargar_resultado(dir_name, 'IA')

        rr_m = extraer_metricas_resumen(rr)
        ia_m = extraer_metricas_resumen(ia)

        entrada = {
            'prueba': num,
            'nombre': nombre,
            'RR': rr_m if rr_m else 'NO DISPONIBLE',
            'IA': ia_m if ia_m else 'NO DISPONIBLE',
        }

        # Calcular diferencias si ambos están disponibles
        if rr_m and ia_m:
            entrada['diferencia'] = {
                'iplr_percent': round((ia_m['iplr_percent'] or 0) - (rr_m['iplr_percent'] or 0), 2),
                'iptd_avg_ms': round((ia_m['iptd_avg_ms'] or 0) - (rr_m['iptd_avg_ms'] or 0), 2),
                'ipdv_jitter_ms': round((ia_m['ipdv_jitter_ms'] or 0) - (rr_m['ipdv_jitter_ms'] or 0), 2),
                'nota': 'Valores negativos = IA es mejor'
            }

        reporte['pruebas'].append(entrada)

        status_rr = f"IPLR={rr_m['iplr_percent']}%" if rr_m else "N/A"
        status_ia = f"IPLR={ia_m['iplr_percent']}%" if ia_m else "N/A"
        print(f"  P{num:2d} {nombre:25s} | RR: {status_rr:15s} | IA: {status_ia}")

    return reporte


def generar_reporte_asignacion():
    """
    REPORTE 2: Asignación Comparativa
    Muestra servidor asignado petición por petición (RR vs IA)
    """
    print("\n═══ REPORTE 2: ASIGNACIÓN COMPARATIVA (RR vs IA) ═══")
    reporte = {
        'titulo': 'Reporte de Asignación Comparativa - Servidor por Petición',
        'generado': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'pruebas': []
    }

    for num, dir_name, nombre in PRUEBAS:
        rr = cargar_resultado(dir_name, 'RR')
        ia = cargar_resultado(dir_name, 'IA')

        rr_decisiones = rr.get('decisiones', []) if rr else []
        ia_decisiones = ia.get('decisiones', []) if ia else []

        # Alinear decisiones por cliente+servicio
        asignaciones = []
        max_len = max(len(rr_decisiones), len(ia_decisiones))

        for i in range(min(max_len, 50)):  # Máximo 50 por prueba
            rr_d = rr_decisiones[i] if i < len(rr_decisiones) else {}
            ia_d = ia_decisiones[i] if i < len(ia_decisiones) else {}

            asignaciones.append({
                'peticion': i + 1,
                'cliente_RR': rr_d.get('cliente', ''),
                'servicio_RR': rr_d.get('servicio', ''),
                'servidor_RR': rr_d.get('servidor', ''),
                'cliente_IA': ia_d.get('cliente', ''),
                'servicio_IA': ia_d.get('servicio', ''),
                'servidor_IA': ia_d.get('servidor', ''),
                'coincide': rr_d.get('servidor', '') == ia_d.get('servidor', '') and rr_d.get('servidor', '') != ''
            })

        coincidencias = sum(1 for a in asignaciones if a['coincide'])
        total = len(asignaciones)
        pct = round(coincidencias / total * 100, 1) if total > 0 else 0

        reporte['pruebas'].append({
            'prueba': num,
            'nombre': nombre,
            'total_comparadas': total,
            'coincidencias': coincidencias,
            'porcentaje_coincidencia': pct,
            'asignaciones': asignaciones
        })

        print(f"  P{num:2d} {nombre:25s} | {total:3d} decisiones | "
              f"Coincidencia: {pct}%")

    return reporte


def generar_reporte_conmutacion_ia():
    """
    REPORTE 3: Conmutación por Saturación (Exclusivo IA)
    Registra eventos donde la IA detectó saturación y desvió tráfico.
    """
    print("\n═══ REPORTE 3: CONMUTACIÓN POR SATURACIÓN (SOLO IA) ═══")
    reporte = {
        'titulo': 'Reporte de Conmutación por Saturación - IA-LSTM',
        'generado': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'descripcion': 'Eventos donde la IA detectó servidor saturado y redirigió tráfico',
        'eventos_por_prueba': []
    }

    total_eventos = 0

    for num, dir_name, nombre in PRUEBAS:
        ia = cargar_resultado(dir_name, 'IA')
        if not ia:
            continue

        decisiones = ia.get('decisiones', [])
        eventos_saturacion = []

        # Buscar eventos de re-elección (evicción por saturación)
        for d in decisiones:
            mets = d.get('mets', {})
            # Detectar si algún servidor estaba >90% CPU
            for i in range(1, 5):
                cpu = mets.get(f'srv{i}_cpu', 0)
                if cpu > 90:
                    eventos_saturacion.append({
                        'timestamp': d.get('timestamp', 0),
                        'cliente': d.get('cliente', ''),
                        'servicio': d.get('servicio', ''),
                        'servidor_original': f'srv{i}',
                        'cpu_detectada': round(cpu, 1),
                        'nuevo_servidor': d.get('servidor', ''),
                        'fue_desviado': d.get('servidor', '') != f'srv{i}'
                    })

        total_eventos += len(eventos_saturacion)

        if eventos_saturacion:
            reporte['eventos_por_prueba'].append({
                'prueba': num,
                'nombre': nombre,
                'total_eventos': len(eventos_saturacion),
                'eventos': eventos_saturacion[:30]  # Máximo 30 por prueba
            })

        n = len(eventos_saturacion)
        if n > 0:
            print(f"  P{num:2d} {nombre:25s} | {n:3d} eventos de saturación detectados")
        else:
            print(f"  P{num:2d} {nombre:25s} | Sin eventos de saturación")

    reporte['total_eventos_globales'] = total_eventos
    print(f"\n  TOTAL GLOBAL: {total_eventos} eventos de conmutación por saturación")

    return reporte


def main():
    print("=" * 65)
    print("  GENERADOR DE REPORTES COMPARATIVOS SDN (RR vs IA-LSTM)")
    print("=" * 65)

    # Crear directorio de reportes
    os.makedirs(REPORT_DIR, exist_ok=True)

    # Generar los 3 reportes
    r1 = generar_reporte_metricas_globales()
    r2 = generar_reporte_asignacion()
    r3 = generar_reporte_conmutacion_ia()

    # Guardar reportes
    files = [
        ('reporte_metricas_globales.json', r1),
        ('reporte_asignacion_comparativa.json', r2),
        ('reporte_conmutacion_ia.json', r3),
    ]

    print(f"\n{'=' * 65}")
    print("  REPORTES GUARDADOS:")
    for fname, data in files:
        path = os.path.join(REPORT_DIR, fname)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"    ✅ {path}")
    print(f"{'=' * 65}\n")


if __name__ == '__main__':
    main()

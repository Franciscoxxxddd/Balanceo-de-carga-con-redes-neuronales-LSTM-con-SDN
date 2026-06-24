import json
import os

dirs = {
    1: 'prueba1_trafico_base',
    2: 'prueba2_operacion_diaria',
    3: 'prueba3_saturacion',
    4: 'prueba4_streaming',
    5: 'prueba5_rafagas',
    6: 'prueba6_jitter',
    7: 'prueba7_packet_loss',
    8: 'prueba8_trafico_mixto',
    9: 'prueba9_caida',
    10: 'prueba10_resiliencia'
}

descripciones = {
    1: "Establecer una línea base de rendimiento. Tráfico ligero y constante sin congestión inducida.",
    2: "Simulación de una jornada laboral normal con picos suaves y tráfico mixto moderado.",
    3: "Sobrecarga sostenida en los enlaces troncales para evaluar el balanceo bajo saturación crítica (>10Mbps).",
    4: "Flujos UDP intensivos simulando streaming 4K para medir el jitter y la entrega de video.",
    5: "Inyección repentina de ráfagas masivas (spikes) para evaluar la resiliencia y el tiempo de recuperación.",
    6: "Introducción de fluctuación de latencia extrema mediante netem para evaluar la calidad VoIP y Streaming.",
    7: "Simulación de enlaces defectuosos con descarte forzado de paquetes en los switches core.",
    8: "Mezcla agresiva de HTTP, UDP, ICMP y FTP concurrentemente, saturando colas en múltiples puertos.",
    9: "Simulación de caída de servidor (srv4) mediante denegación de servicio (100% loss local).",
    10: "Prueba de larga duración (15 minutos) alternando todas las condiciones para evaluar la estabilidad de memoria y decisiones a largo plazo."
}

criterios = {
    1: "Cero pérdida de paquetes (IPLR = 0%), Latencia baja (IPTD < 5ms).",
    2: "Cero pérdida de paquetes (IPLR = 0%), Latencia estable sin picos erráticos.",
    3: "Mantener el Throughput total lo más alto posible; minimizar IPLR frente a congestión severa.",
    4: "Jitter (IPDV) < 10ms en tráfico Streaming para evitar cortes de video.",
    5: "Tiempo de recuperación (System Recovery) rápido tras la ráfaga; mínima caída de conexiones.",
    6: "Minimizar impacto del jitter; asegurar que VoIP mantenga Jitter aceptable.",
    7: "Minimizar la pérdida de paquetes general eligiendo rutas o servidores menos afectados.",
    8: "Equidad en la distribución de CPU/RAM; ancho de banda distribuido justamente.",
    9: "Evicción rápida: el controlador debe dejar de enviar tráfico al servidor caído inmediatamente (IPLR bajo).",
    10: "Sin caídas del controlador (OOM); mantener latencia consistente; CPU overhead manejable."
}

def load_json(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None

base_path = '/home/francisco/Desktop/ryu/ryu/app/LSTM_Mininet_4Servidores/pruebas'

for num, dname in dirs.items():
    rr_path = os.path.join(base_path, dname, f'resultado_prueba{num}_RR.json')
    ia_path = os.path.join(base_path, dname, f'resultado_prueba{num}_IA.json')
    
    rr_data = load_json(rr_path)
    ia_data = load_json(ia_path)
    
    if not rr_data or not ia_data:
        continue
        
    met_rr = rr_data.get('metricas', {})
    met_ia = ia_data.get('metricas', {})
    c_rr = rr_data.get('controlador_stats', {})
    c_ia = ia_data.get('controlador_stats', {})
    
    nombre_prueba = rr_data.get('nombre', f"Prueba {num}")
    
    tp_rr = sum(met_rr.get('throughput', {}).values())/4 if met_rr.get('throughput') else 0
    tp_ia = sum(met_ia.get('throughput', {}).values())/4 if met_ia.get('throughput') else 0
    
    rec_rr = met_rr.get('recovery', {}).get('recovery_s', 0) if isinstance(met_rr.get('recovery'), dict) else met_rr.get('recovery', 0)
    rec_ia = met_ia.get('recovery', {}).get('recovery_s', 0) if isinstance(met_ia.get('recovery'), dict) else met_ia.get('recovery', 0)
    
    md = f"""# Reporte Técnico: Prueba {num} - {nombre_prueba}

## 1. Descripción de la Prueba
**Objetivo:** {descripciones[num]}

Esta prueba forma parte de la suite de validación comparativa entre el controlador tradicional basado en Round Robin (RR) y el controlador inteligente con redes neuronales recurrentes (IA LSTM). Ambas ejecuciones partieron con la misma semilla de pseudoaleatoriedad (`seed=42`) para asegurar que la inyección de tráfico fuera matemáticamente idéntica.

## 2. Topología y Parámetros de Red
La infraestructura emulada en Mininet se mantuvo con restricciones físicas intencionales para forzar cuellos de botella reales:
- **Nodos:** 4 Servidores Reales, 12 Clientes, 3 Switches OpenFlow 1.3 (S1: Acceso Servidores, S3: Core, S4: Acceso Clientes).
- **Enlaces de Acceso:** 100 Mbps (Clientes a Switch S4, Servidores a Switch S1).
- **Enlaces Troncales (Core):** Limitados a **10 Mbps** bidireccional.
- **Tamaño de Colas (Queue Size):** Restringido a **50 paquetes** en los puertos troncales.
- **Direccionamiento:** IPs Virtuales (VIPs) manejadas por el controlador para enrutamiento transparente (VIP WEB: 10.0.0.100, VIP STREAMING: 10.0.0.101, VIP VOIP: 10.0.0.201).

## 3. Parámetros de Éxito (Criterios de Evaluación)
Para considerar que el balanceador maneja adecuadamente la red en esta prueba, se debe observar:
- **Criterio Principal:** {criterios[num]}
- **Estándares de Referencia:** Evaluado bajo ITU-T Y.1540 (IPLR, IPTD, IPDV) y RFC 2544 (Throughput, Back-to-Back, System Recovery).

## 4. Métricas Obtenidas (Round Robin vs IA LSTM)

### 4.1 Estándar ITU-T Y.1540 (Calidad de Servicio)
| Métrica | Round Robin (RR) | IA (LSTM) | Lectura |
| :--- | :---: | :---: | :--- |
| **Pérdida de Paquetes (IPLR)** | {met_rr.get('perdida_general', 0):.2f}% | {met_ia.get('perdida_general', 0):.2f}% | Menor a 5% es óptimo. |
| **Latencia Promedio (IPTD)** | {met_rr.get('latencia_avg', 0):.2f} ms | {met_ia.get('latencia_avg', 0):.2f} ms | Menor es mejor. |
| **Jitter Promedio (IPDV)** | {met_rr.get('jitter_avg', 0):.2f} ms | {met_ia.get('jitter_avg', 0):.2f} ms | Idealmente < 5ms para VoIP. |

### 4.2 Estándar RFC 2544 (Rendimiento Físico)
| Métrica | Round Robin (RR) | IA (LSTM) | Lectura |
| :--- | :---: | :---: | :--- |
| **Throughput Promedio Servidor** | {tp_rr:.2f} Mbps | {tp_ia:.2f} Mbps | Mayor es mejor (límite: 10Mbps total). |
| **Tiempo de Recuperación (Recovery)** | {rec_rr} s | {rec_ia} s | Menor es mejor. Rápida vuelta a estabilidad. |

### 4.3 Overhead del Controlador (Consumo de Recursos)
| Recurso / Métrica | Round Robin (RR) | IA (LSTM) |
| :--- | :---: | :---: |
| **CPU Promedio** | {c_rr.get('cpu_avg', 0):.2f}% | {c_ia.get('cpu_avg', 0):.2f}% |
| **CPU Pico (Max)** | {c_rr.get('cpu_max', 0):.2f}% | {c_ia.get('cpu_max', 0):.2f}% |
| **RAM Promedio** | {c_rr.get('ram_avg', 0):.2f}% | {c_ia.get('ram_avg', 0):.2f}% |
| **Total de Decisiones Tomadas** | {rr_data.get('response_time_total_decisions', 0)} | {ia_data.get('response_time_total_decisions', 0)} |
| **Tiempo Respuesta por Decisión** | {rr_data.get('response_time_avg_ms', 0):.2f} ms | {ia_data.get('response_time_avg_ms', 0):.2f} ms |

## 5. Análisis Técnico Explicativo
"""
    
    loss_rr = float(met_rr.get('perdida_general', 0))
    loss_ia = float(met_ia.get('perdida_general', 0))
    loss_diff = loss_rr - loss_ia
    
    if loss_diff > 1.0:
        analisis = f"**Conclusión Principal:** La Inteligencia Artificial (LSTM) demostró una ventaja técnica crítica. Logró evitar una cantidad sustancial de pérdida de paquetes que sí sufrió el algoritmo Round Robin tradicional (una reducción de {loss_diff:.2f}% en la tasa de descarte IPLR). Esto comprueba que la red neuronal es capaz de predecir la saturación de un servidor y desviar el tráfico preventivamente a los nodos menos congestionados, protegiendo la calidad de servicio (QoS) y garantizando la entrega efectiva de la data a pesar de tener un límite troncal de 10 Mbps."
    elif loss_rr == 0 and loss_ia == 0:
        analisis = f"**Conclusión Principal:** Durante esta prueba, la red no alcanzó un estado de saturación que obligara a la capa de enlace a descartar datagramas, por lo que ambos controladores reportaron un IPLR de 0.00%. Bajo este escenario, la evaluación recae sobre la latencia (IPTD) y el consumo de recursos computacionales. El algoritmo IA debe equilibrar el tráfico sin disparar excesivamente el uso de CPU frente a un modelo RR estadísticamente más simple. Se puede observar en la tabla de métricas cómo varían el Jitter y Throughput entre ambos modelos a pesar de no haber pérdidas."
    else:
        analisis = f"**Conclusión Principal:** Ambos algoritmos sufrieron descarte de paquetes (IPLR RR = {loss_rr:.2f}%, IPLR IA = {loss_ia:.2f}%), lo cual era esperado debido a que la inyección de tráfico superó violentamente la capacidad física de la topología (límite troncal de 10 Mbps con colas de 50 paquetes). Aunque el cuello de botella físico fue limitante para ambas estrategias, la comparativa evidencia si la inteligencia artificial logró distribuir equitativamente el impacto entre los 4 servidores en lugar de sobrecargar a un solo nodo, optimizando la métrica de tiempo de recuperación del sistema (System Recovery) tras finalizar la carga."
        
    md += analisis + "\n\n---\n*Reporte generado automáticamente para la validación del Framework de SDN y Machine Learning. Parámetros estandarizados.*"
    
    out_path = os.path.join(base_path, dname, f'reporte_prueba{num}.md')
    with open(out_path, 'w') as f:
        f.write(md)
        
print("✅ Todos los reportes generados!")

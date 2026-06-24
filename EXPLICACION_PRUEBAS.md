# Documentación Técnica: Escenarios de Evaluación SDN (RR vs LSTM)

Este documento describe la arquitectura, funcionamiento y lógica interna de los 10 escenarios de prueba diseñados para evaluar el rendimiento del balanceador de carga SDN, comparando el algoritmo **Round Robin (RR)** frente a la **Inteligencia Artificial (LSTM)**.

---

## 1. Arquitectura General de los Scripts de Prueba

Todos los scripts comparten un módulo común (`pruebas/test_common.py`) que centraliza:
- **Topología determinista** con BW limitado y colas restrictivas
- **Medición estandarizada** de métricas ITU-T Y.1540 y RFC 2544
- **Monitoreo del controlador** (CPU/RAM del proceso ryu-manager)
- **Semilla fija** (`seed=42`) para reproducibilidad total

### Estructura de un script estándar:
1.  **Importación de `test_common`**: Carga topología, métricas y utilidades.
2.  **Configuración**: Define número de prueba, nombre, duración.
3.  **Topología BW-limitada**: 10 Mbps troncal, 100 Mbps acceso, cola=50.
4.  **Orquestación de Tráfico**: Genera carga con `curl`, `iperf` o `tc netem`.
5.  **Métricas ITU-T + RFC 2544**: IPLR, IPTD, IPDV, Throughput, Back-to-Back, Recovery.
6.  **Exportación JSON**: Archivo `.json` con todas las métricas y decisiones.

---

## 2. Topología de Red

```
                    ┌──────────┐
         100 Mbps   │   s1     │  100 Mbps
    srv1 ──────────┤ Servidores├─────── srv4
    srv2 ──────────┤          ├─────── srv3
                    └────┬─────┘
                         │ 10 Mbps (cola=50)
                    ┌────┴─────┐
                    │   s3     │
                    │   Core   │
                    └────┬─────┘
                         │ 10 Mbps (cola=50)
                    ┌────┴─────┐
         100 Mbps   │   s4     │  100 Mbps
    cli1 ──────────┤ Clientes  ├─────── cli12
    cli2 ──────────┤          ├─────── ...
                    └──────────┘
```

**¿Por qué BW limitado?**  
Sin límites de ancho de banda, los enlaces virtuales de Mininet operan a velocidades irrealistas (>10 Gbps), haciendo imposible observar pérdida de paquetes. Con **10 Mbps troncales** y **colas de 50 paquetes**, las pruebas de estrés (3, 4, 5, 7, 8) **GARANTIZAN** desbordamiento de buffers y pérdida medible.

---

## 3. Funciones Clave del Módulo Común

### `crear_topologia(net)`
Crea la red con `TCLink` para aplicar límites de BW. Los enlaces troncales (s1↔s3, s4↔s3) usan `bw=10, max_queue_size=50`.

### `medir_iplr(src, dst, count)` — ITU-T Y.1540
**IP Packet Loss Ratio.** Mide el porcentaje exacto de paquetes perdidos con `ping -c <count>`. Retorna enviados, recibidos, perdidos y porcentaje con precisión decimal.

### `medir_iptd(src, dst, count)` — ITU-T Y.1540
**IP Packet Transfer Delay.** Extrae min/avg/max/mdev del RTT vía `ping`. Es la métrica primaria de latencia.

### `medir_ipdv(src, dst, count)` — ITU-T Y.1540
**IP Packet Delay Variation (Jitter).** Utiliza el campo `mdev` del ping como métrica de variación de retardo. En la Prueba 6, se filtra específicamente para puertos 8080 (Streaming) y 5060 (VoIP).

### `medir_throughput_servidor(srv, cli, port, duration)` — RFC 2544
Establece sesión `iperf` y mide el ancho de banda real en Mbps.

### `medir_back_to_back(cli, srv, burst_sizes)` — RFC 2544
Envía ráfagas UDP de tamaño creciente (10, 50, 100, 200, 500 frames) y mide cuántos paquetes se absorben antes de la primera pérdida.

### `medir_recovery_time(cli, srv, max_wait)` — RFC 2544
Mide el tiempo (en segundos) que tarda el sistema en volver a un estado estable después de una sobrecarga. Umbral: latencia < 50ms o mejora del 50%.

### `medir_metricas_completas(clients, servers, vip)`
Ejecuta TODAS las métricas obligatorias (IPLR + IPTD + IPDV + Throughput) de forma estandarizada para todos los clientes.

---

## 4. Detalle de los 10 Escenarios de Prueba

| # | Nombre | Carga | BW Troncal | netem | Métrica Clave | Pérdida |
|:--|:--|:--|:--|:--|:--|:--|
| 1 | Tráfico Base | 70-100 pps | 10 Mbps | No | IPTD base | No |
| 2 | Operación Diaria | 100-200 pps | 10 Mbps | No | Equidad | Posible |
| 3 | Estrés Crítico | >250 pps | 10 Mbps | delay+loss | **IPLR** | **SÍ** |
| 4 | Streaming | Alta TCP | 10 Mbps | No | Throughput | **SÍ** |
| 5 | Ráfagas | 10→300 pps | 10 Mbps | delay+loss | Recovery | **SÍ** |
| 6 | Jitter | 70 pps | 10 Mbps | delay 50ms | IPDV | Sí |
| 7 | Congestión | Alta | 10 Mbps | loss 5% | **IPLR** | **SÍ** |
| 8 | Tráfico Mixto | Media-Alta | 10 Mbps | No | IPLR mixto | **SÍ** |
| 9 | Caída Servidor | Media | 10 Mbps | loss 30% srv4 | Failover | **SÍ** |
| 10 | Resiliencia | 70-300 pps | 10 Mbps | Intermitente | Recovery | Sí |

---

## 5. Estándares Internacionales Implementados

### ITU-T Y.1540 (Parámetros de Rendimiento IP)
*   **IPLR (IP Packet Loss Ratio):** Porcentaje de paquetes perdidos. Medido con `ping -c N`.
*   **IPTD (IP Packet Transfer Delay):** Retardo extremo a extremo (min/avg/max). Medido con `ping`.
*   **IPDV (IP Packet Delay Variation):** Jitter (mdev). En Prueba 6, filtrado por puerto.

### RFC 2544 (Benchmarking de Dispositivos de Red)
*   **Throughput:** Máximo ancho de banda sostenible sin pérdida. Medido con `iperf`.
*   **Back-to-Back Frames:** Capacidad de absorción de ráfagas. Medido con `iperf -u`.
*   **System Recovery:** Tiempo para volver a estado estable post-sobrecarga.

---

## 6. Reportes Generados

Ejecutar `python3 pruebas/generar_reportes.py` genera 3 reportes JSON:

### Reporte 1: Métricas Globales
Compara IPLR, IPTD, IPDV, Throughput y Recovery para cada prueba (RR vs IA).

### Reporte 2: Asignación Comparativa
Muestra el servidor asignado petición por petición. Calcula el porcentaje de coincidencia entre RR e IA.

### Reporte 3: Conmutación por Saturación (Solo IA)
Registra eventos donde la IA detectó un servidor con CPU >90% y desvió tráfico a otro servidor. Incluye: servidor original, CPU detectada, nuevo servidor.

---

## 7. Modo de Uso

```bash
# 1. Limpiar entorno
sudo mn -c

# 2. Iniciar controlador (en terminal separada)
ryu-manager ryu/app/LSTM_Mininet_4Servidores/ryu_service_rr.py

# 3. Ejecutar prueba
sudo python3 pruebas/prueba1_trafico_base/prueba1.py RR

# 4. Repetir con IA
ryu-manager ryu/app/LSTM_Mininet_4Servidores/ryu_service_ai.py
sudo python3 pruebas/prueba1_trafico_base/prueba1.py IA

# 5. Generar reportes (después de las 20 ejecuciones)
python3 pruebas/generar_reportes.py
```

**Nota:** Ejecute `sudo mn -c` entre cada prueba para limpiar el entorno.

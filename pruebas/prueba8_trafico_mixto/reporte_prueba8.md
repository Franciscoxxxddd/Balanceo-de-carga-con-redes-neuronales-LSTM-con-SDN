# Reporte Técnico: Prueba 8 - Tráfico Mixto Concurrente

## 1. Descripción de la Prueba
**Objetivo:** Mezcla agresiva de HTTP, UDP, ICMP y FTP concurrentemente, saturando colas en múltiples puertos.

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
- **Criterio Principal:** Equidad en la distribución de CPU/RAM; ancho de banda distribuido justamente.
- **Estándares de Referencia:** Evaluado bajo ITU-T Y.1540 (IPLR, IPTD, IPDV) y RFC 2544 (Throughput, Back-to-Back, System Recovery).

## 4. Métricas Obtenidas (Round Robin vs IA LSTM)

### 4.1 Estándar ITU-T Y.1540 (Calidad de Servicio)
| Métrica | Round Robin (RR) | IA (LSTM) | Lectura |
| :--- | :---: | :---: | :--- |
| **Pérdida de Paquetes (IPLR)** | 0.00% | 0.00% | Menor a 5% es óptimo. |
| **Latencia Promedio (IPTD)** | 1.44 ms | 1.07 ms | Menor es mejor. |
| **Jitter Promedio (IPDV)** | 2.86 ms | 1.91 ms | Idealmente < 5ms para VoIP. |

### 4.2 Estándar RFC 2544 (Rendimiento Físico)
| Métrica | Round Robin (RR) | IA (LSTM) | Lectura |
| :--- | :---: | :---: | :--- |
| **Throughput Promedio Servidor** | 10.03 Mbps | 9.89 Mbps | Mayor es mejor (límite: 10Mbps total). |
| **Tiempo de Recuperación (Recovery)** | 60 s | 60 s | Menor es mejor. Rápida vuelta a estabilidad. |

### 4.3 Overhead del Controlador (Consumo de Recursos)
| Recurso / Métrica | Round Robin (RR) | IA (LSTM) |
| :--- | :---: | :---: |
| **CPU Promedio** | 1.79% | 8.18% |
| **CPU Pico (Max)** | 3.00% | 28.30% |
| **RAM Promedio** | 0.70% | 6.70% |
| **Total de Decisiones Tomadas** | 26 | 31 |
| **Tiempo Respuesta por Decisión** | 8227.44 ms | 6858.17 ms |

## 5. Análisis Técnico Explicativo
**Conclusión Principal:** Durante esta prueba, la red no alcanzó un estado de saturación que obligara a la capa de enlace a descartar datagramas, por lo que ambos controladores reportaron un IPLR de 0.00%. Bajo este escenario, la evaluación recae sobre la latencia (IPTD) y el consumo de recursos computacionales. El algoritmo IA debe equilibrar el tráfico sin disparar excesivamente el uso de CPU frente a un modelo RR estadísticamente más simple. Se puede observar en la tabla de métricas cómo varían el Jitter y Throughput entre ambos modelos a pesar de no haber pérdidas.

---
*Reporte generado automáticamente para la validación del Framework de SDN y Machine Learning. Parámetros estandarizados.*
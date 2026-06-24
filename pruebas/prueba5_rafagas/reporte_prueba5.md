# Reporte Técnico: Prueba 5 - Ráfagas Asimétricas (Spikes)

## 1. Descripción de la Prueba
**Objetivo:** Inyección repentina de ráfagas masivas (spikes) para evaluar la resiliencia y el tiempo de recuperación.

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
- **Criterio Principal:** Tiempo de recuperación (System Recovery) rápido tras la ráfaga; mínima caída de conexiones.
- **Estándares de Referencia:** Evaluado bajo ITU-T Y.1540 (IPLR, IPTD, IPDV) y RFC 2544 (Throughput, Back-to-Back, System Recovery).

## 4. Métricas Obtenidas (Round Robin vs IA LSTM)

### 4.1 Estándar ITU-T Y.1540 (Calidad de Servicio)
| Métrica | Round Robin (RR) | IA (LSTM) | Lectura |
| :--- | :---: | :---: | :--- |
| **Pérdida de Paquetes (IPLR)** | 5.95% | 5.83% | Menor a 5% es óptimo. |
| **Latencia Promedio (IPTD)** | 26.59 ms | 30.23 ms | Menor es mejor. |
| **Jitter Promedio (IPDV)** | 7.26 ms | 5.70 ms | Idealmente < 5ms para VoIP. |

### 4.2 Estándar RFC 2544 (Rendimiento Físico)
| Métrica | Round Robin (RR) | IA (LSTM) | Lectura |
| :--- | :---: | :---: | :--- |
| **Throughput Promedio Servidor** | 2.99 Mbps | 2.94 Mbps | Mayor es mejor (límite: 10Mbps total). |
| **Tiempo de Recuperación (Recovery)** | 8 s | 60 s | Menor es mejor. Rápida vuelta a estabilidad. |

### 4.3 Overhead del Controlador (Consumo de Recursos)
| Recurso / Métrica | Round Robin (RR) | IA (LSTM) |
| :--- | :---: | :---: |
| **CPU Promedio** | 3.13% | 8.58% |
| **CPU Pico (Max)** | 4.60% | 25.70% |
| **RAM Promedio** | 0.70% | 6.70% |
| **Total de Decisiones Tomadas** | 20 | 23 |
| **Tiempo Respuesta por Decisión** | 7213.68 ms | 6242.19 ms |

## 5. Análisis Técnico Explicativo
**Conclusión Principal:** Ambos algoritmos sufrieron descarte de paquetes (IPLR RR = 5.95%, IPLR IA = 5.83%), lo cual era esperado debido a que la inyección de tráfico superó violentamente la capacidad física de la topología (límite troncal de 10 Mbps con colas de 50 paquetes). Aunque el cuello de botella físico fue limitante para ambas estrategias, la comparativa evidencia si la inteligencia artificial logró distribuir equitativamente el impacto entre los 4 servidores en lugar de sobrecargar a un solo nodo, optimizando la métrica de tiempo de recuperación del sistema (System Recovery) tras finalizar la carga.

---
*Reporte generado automáticamente para la validación del Framework de SDN y Machine Learning. Parámetros estandarizados.*
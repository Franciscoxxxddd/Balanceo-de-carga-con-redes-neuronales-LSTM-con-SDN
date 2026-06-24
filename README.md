# Balanceo de Carga con Redes Neuronales LSTM en SDN

Este proyecto implementa un sistema de balanceo de carga inteligente para Redes Definidas por Software (SDN) utilizando el controlador **Ryu** y la emulación de red con **Mininet**. El sistema compara dos enfoques de balanceo de carga: el algoritmo clásico **Round Robin** y un modelo de inteligencia artificial basado en redes neuronales **LSTM** (Long Short-Term Memory).

## 🚀 Características Principales
* **Topología SDN Emulada:** Creada con Mininet, simulando 4 servidores web/servicios y múltiples clientes.
* **Controladores Intercambiables:**
  * **Round Robin (`ryu_service_rr.py`):** Balanceo tradicional secuencial.
  * **IA con LSTM (`ryu_service_ai.py`):** Balanceo predictivo que analiza el estado de la red para decidir el mejor servidor.
* **Dashboard en Tiempo Real:** Interfaz web construida con **Streamlit** (`dashboard_tesis.py`) para monitorizar las métricas de la red (Throughput, Latencia, Pérdida de Paquetes) y visualizar las decisiones del controlador.
* **Batería de Pruebas:** Scripts automatizados en la carpeta `/pruebas` para someter la red a diferentes cargas de tráfico y generar reportes de rendimiento.

## 📁 Estructura del Proyecto

* `topo_gns3_full.py`: Script de Mininet que genera la topología de la red (Switches, Hosts, Enlaces).
* `ryu_service_ai.py`: Controlador SDN de Ryu con el agente inteligente LSTM integrado.
* `ryu_service_rr.py`: Controlador SDN de Ryu con el algoritmo Round Robin.
* `ai_brain.py`: Módulo que maneja las predicciones del modelo LSTM.
* `train_4srv.py`: Script para entrenar la red neuronal utilizando el dataset.
* `dashboard_tesis.py`: Panel de control interactivo (Streamlit).
* `modelo_gns3.h5` / `*.joblib`: Modelos de IA pre-entrenados y sus respectivos codificadores/escaladores.
* `/pruebas`: Directorio con los escenarios de prueba para medir el rendimiento de los controladores.

## 🛠️ Requisitos Previos

Para ejecutar este proyecto necesitas tener instalados los siguientes componentes en un entorno Linux (preferiblemente Ubuntu):

* **Mininet**
* **Controlador Ryu** (`ryu-manager`)
* **Python 3.x** y pip
* Librerías de Python:
  ```bash
  pip install tensorflow keras scikit-learn pandas numpy streamlit matplotlib
  ```

## ⚙️ Cómo Ejecutar el Proyecto

El proyecto consta de 3 partes que deben ejecutarse en terminales separadas:

### 1. Iniciar la Topología (Mininet)
Limpia cualquier topología previa y ejecuta el script de creación de red:
```bash
sudo mn -c
sudo python3 topo_gns3_full.py
```

### 2. Iniciar el Controlador SDN (Ryu)
Elige **uno** de los dos controladores.

Para el controlador con Inteligencia Artificial (LSTM):
```bash
ryu-manager ryu_service_ai.py
```

Para el controlador Round Robin tradicional:
```bash
ryu-manager ryu_service_rr.py
```

### 3. Iniciar el Dashboard de Monitorización
Para ver las métricas de la red en tiempo real en tu navegador:
```bash
streamlit run dashboard_tesis.py
```

---
**Nota para el autor**: Este código fue desarrollado como parte de un proyecto de tesis orientado a mejorar el rendimiento y la eficiencia de las redes SDN frente a tráfico variable.

import numpy as np # Importar NumPy para operaciones numéricas con arrays y matrices
import pandas as pd # Importar Pandas para la manipulación de datos tabulares (DataFrames)
import joblib # Importar Joblib para cargar objetos serializados (scaler, encoders)
import os # Importar os para interactuar con el sistema operativo (variables de entorno)
import logging # Importar logging para el manejo de mensajes de log (no se usa directamente aquí)

# Silenciar los mensajes informativos y de advertencia de TensorFlow en consola
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import tensorflow as tf # Importar TensorFlow, el framework de deep learning para usar el modelo LSTM
from tensorflow.keras.models import load_model # Importar la función load_model de Keras para cargar modelos entrenados desde archivos .h5

# Definición de la clase SDN_Brain que encapsula el cerebro de IA para balanceo de carga
class SDN_Brain:
    # Constructor de la clase: se ejecuta al crear una instancia de SDN_Brain
    def __init__(self):
        # Imprimir mensaje indicando que el cerebro de IA se está inicializando
        print(">>> [AI BRAIN] Inicializando...")
        # Definir la lista de características (features) en el orden EXACTO usado durante el entrenamiento
        self.features = [
            'srv1_cpu', 'srv1_ram', 'srv2_cpu', 'srv2_ram', 
            'srv3_cpu', 'srv3_ram', 'bw_solicitado', 'jitter', 'loss', 'etapa_trafico'
        ]
        
        # Bloque try-except para manejar errores al cargar los archivos del modelo
        try:
            # Cargar el modelo LSTM entrenado desde el archivo .h5
            self.model = load_model('modelo_lstm_pro.h5')
            # Cargar el escalador MinMax previamente entrenado para normalizar las features
            self.scaler = joblib.load('scaler_lstm.joblib')
            # Cargar el encoder del target para convertir índices numéricos a nombres de servidor
            self.encoder_target = joblib.load('encoder_target_lstm.joblib')
            # Cargar el encoder de etapa de tráfico para convertir texto ('BAJO','MEDIO','ALTO') a número
            self.encoder_etapa = joblib.load('encoder_etapa_lstm.joblib')
            # Imprimir mensaje de éxito al cargar todos los archivos
            print(">>> [AI BRAIN] Modelo y objetos cargados correctamente.")
        # Capturar cualquier excepción que ocurra durante la carga
        except Exception as e:
            # Imprimir mensaje de error crítico indicando qué falló
            print(f"!!! [AI BRAIN] Error crítico cargando modelo: {e}")
            # Establecer el modelo como None para indicar que no está disponible
            self.model = None

    # Método privado para inferir la etapa de tráfico basada en el ancho de banda solicitado
    def _inferir_etapa(self, bw):
        """Regla simple para inferir la etapa basada en BW si no viene en los datos"""
        # Si el ancho de banda es menor a 10 Mbps, la etapa es 'BAJO'
        if bw < 10: return 'BAJO'
        # Si el ancho de banda es menor a 20 Mbps (pero >= 10), la etapa es 'MEDIO'
        elif bw < 20: return 'MEDIO'
        # Si el ancho de banda es 20 Mbps o más, la etapa es 'ALTO'
        else: return 'ALTO'

    # Método principal para realizar la predicción del servidor óptimo usando el modelo LSTM
    def predecir(self, metricas):
        """
        metricas: Diccionario con todos los valores.
        Ej: {'srv1_cpu': 50, ... 'bw_solicitado': 10, ...}
        """
        # Si el modelo no fue cargado correctamente, usar fallback al servidor 1
        if not self.model: 
            # Imprimir advertencia de que se está usando el servidor por defecto
            print("⚠️ [IA] Modelo no cargado, usando fallback 'srv1'")
            # Retornar 'srv1' como servidor por defecto
            return 'srv1' 

        # Paso 1: Preparar los datos de entrada para el modelo
        # Verificar si la etapa de tráfico no está presente en las métricas
        if 'etapa_trafico' not in metricas:
            # Inferir la etapa de tráfico usando el ancho de banda (5 Mbps como default)
            etapa_str = self._inferir_etapa(metricas.get('bw_solicitado', 5))
            # Bloque try-except para codificar la etapa de texto a número
            try:
                # Usar el encoder para transformar el texto de etapa a su valor numérico
                metricas['etapa_trafico'] = self.encoder_etapa.transform([etapa_str])[0]
            # Si falla la codificación, asignar 0 como valor por defecto
            except:
                metricas['etapa_trafico'] = 0

        # Crear un DataFrame de Pandas con las métricas en el orden correcto de columnas
        df = pd.DataFrame([metricas], columns=self.features)
        
        # Paso 2: Escalar (normalizar) los datos usando el scaler entrenado
        X_scaled = self.scaler.transform(df)
        
        # Paso 3: Redimensionar el array para que sea compatible con la entrada LSTM
        # Formato: (1 muestra, 1 paso de tiempo, 10 features)
        X_ready = X_scaled.reshape(1, 1, 10)
        
        # Paso 4: Realizar la predicción con el modelo LSTM (verbose=0 para no imprimir progreso)
        probs = self.model.predict(X_ready, verbose=0)
        # Obtener el índice de la clase con la mayor probabilidad (el servidor más probable)
        idx = np.argmax(probs, axis=1)[0]
        
        # Decodificar el índice numérico al nombre del servidor (ej: 0 -> 'srv1')
        servidor = self.encoder_target.inverse_transform([idx])[0]
        
        # Calcular el porcentaje de confianza multiplicando la probabilidad máxima por 100
        confianza = np.max(probs) * 100
        # Imprimir la decisión tomada por la IA junto con el porcentaje de confianza
        print(f"🧠 [IA] Decisión: {servidor} (Confianza: {confianza:.1f}%)")
        # Retornar el nombre del servidor elegido
        return servidor

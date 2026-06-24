import pandas as pd # Importar Pandas para la manipulación de datos tabulares (DataFrames)
import numpy as np # Importar NumPy para operaciones numéricas con arrays y matrices
import matplotlib.pyplot as plt # Importar Matplotlib para crear gráficas de rendimiento del entrenamiento
import seaborn as sns # Importar Seaborn para crear la matriz de confusión con estilo visual mejorado
import joblib # Importar Joblib para serializar (guardar) objetos como el scaler y los encoders
import os # Importar os para configurar variables de entorno del sistema operativo

from sklearn.model_selection import train_test_split # Importar la función para dividir datos en conjuntos de entrenamiento y prueba
# Importar LabelEncoder para convertir etiquetas de texto a números
from sklearn.preprocessing import LabelEncoder, MinMaxScaler # Importar MinMaxScaler para normalizar las features al rango [0, 1]
from sklearn.metrics import classification_report, confusion_matrix # Importar funciones para evaluar el rendimiento del modelo (reporte y matriz de confusión)

import tensorflow as tf # Importar TensorFlow, el framework de deep learning
from tensorflow.keras.models import Sequential # Importar Sequential para crear un modelo de red neuronal capa por capa
# Importar las capas que compondrán la arquitectura del modelo
# LSTM: capa recurrente para secuencias; Dense: capa densa fully-connected
# BatchNormalization: normaliza activaciones; Bidirectional: LSTM en ambas direcciones
from tensorflow.keras.layers import LSTM, Dense, BatchNormalization, Bidirectional, Dropout # Dropout: desactiva neuronas aleatoriamente para evitar overfitting
from tensorflow.keras.utils import to_categorical # Importar to_categorical para convertir etiquetas a formato one-hot encoding
# Importar callbacks para controlar el entrenamiento dinámicamente
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau # EarlyStopping: detiene el entrenamiento si no mejora; ReduceLROnPlateau: reduce learning rate

# Configurar variable de entorno para suprimir mensajes de advertencia de TensorFlow
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# --- PASO 1: CARGA Y FUSIÓN DE DATASETS ---
# Imprimir mensaje indicando el inicio de la carga de datos
print(">>> [1/6] Cargando y fusionando datasets...")

# Bloque A: Cargar el dataset nuevo con 4 servidores
try:
    # Leer el archivo CSV con los datos de entrenamiento de 4 servidores
    df_new = pd.read_csv('dataset_gns3_4srv.csv')
    # Imprimir las dimensiones del dataset cargado (filas x columnas)
    print(f"   - Datos GNS3 (4 srv): {df_new.shape}")
# Si el archivo no existe o hay error de lectura
except:
    # Imprimir mensaje de error indicando que el archivo es necesario
    print("!!! Error: No encuentro dataset_gns3_4srv.csv. Generalo primero con gen_4_srv.py")
    # Terminar la ejecución del script
    exit()

# Bloque B: Intentar cargar el dataset antiguo de 3 servidores para fusionarlo
try:
    # Leer el archivo CSV con los datos aumentados del dataset original de tesis
    df_old = pd.read_csv('dataset_tesis_augmented.csv')
    # Imprimir las dimensiones del dataset antiguo
    print(f"   - Datos Tesis (3 srv): {df_old.shape}")
    
    # Bloque C: ADAPTACIÓN del dataset viejo que no tiene datos del servidor 4
    # Fijar semilla aleatoria para reproducibilidad de los valores generados
    np.random.seed(42)
    # Generar valores aleatorios de CPU para srv4 (simula datos del 4to servidor)
    df_old['srv4_cpu'] = np.random.uniform(10, 90, df_old.shape[0])
    # Generar valores aleatorios de RAM para srv4 (simula datos del 4to servidor)
    df_old['srv4_ram'] = np.random.uniform(20, 80, df_old.shape[0])
    
    # Definir el orden exacto de las columnas que deben tener ambos datasets
    features_order = [
        'srv1_cpu','srv1_ram', 'srv2_cpu','srv2_ram', 'srv3_cpu','srv3_ram', 'srv4_cpu','srv4_ram',
        'bw_solicitado','jitter','loss','etapa_trafico', 'TARGET_IDEAL'
    ]
    
    # Reordenar las columnas del dataset nuevo para que coincidan con el orden definido
    df_new = df_new[features_order]
    # Reordenar las columnas del dataset antiguo para que coincidan con el orden definido
    df_old = df_old[features_order]
    
    # Fusionar ambos datasets verticalmente (uno encima del otro) y resetear el índice
    df_final = pd.concat([df_old, df_new], axis=0).reset_index(drop=True)
    # Imprimir las dimensiones del dataset fusionado
    print(f"   -> DATASET TOTAL FUSIONADO: {df_final.shape}")

# Capturar la excepción si el dataset antiguo no se puede cargar
except Exception as e:
    # Imprimir advertencia indicando que se usará solo el dataset nuevo
    print(f"⚠️ Advertencia: No se pudo cargar el dataset antiguo ({e}). Usando solo el nuevo.")
    # Usar solamente el dataset nuevo como dataset final
    df_final = df_new

# --- PASO 2: PRE-PROCESAMIENTO DE DATOS ---
# Imprimir mensaje indicando el inicio del pre-procesamiento
print(">>> [2/6] Preparando datos para LSTM...")

# Definir la lista de las 12 columnas de features (características de entrada)
features = [
    'srv1_cpu','srv1_ram', 'srv2_cpu','srv2_ram', 'srv3_cpu','srv3_ram', 'srv4_cpu','srv4_ram',
    'bw_solicitado','jitter','loss','etapa_trafico'
]
# Definir el nombre de la columna objetivo (etiqueta): el servidor ideal a elegir
target = 'TARGET_IDEAL'

# Crear un encoder para convertir las etapas de tráfico de texto a números
le_etapa = LabelEncoder()
# Aplicar el encoder a la columna 'etapa_trafico': 'BAJO'->0, 'MEDIO'->1, 'ALTO'->2
df_final['etapa_trafico'] = le_etapa.fit_transform(df_final['etapa_trafico'])

# Crear un encoder para convertir los nombres de servidores a números
le_target = LabelEncoder()
# Aplicar el encoder al target: 'srv1'->0, 'srv2'->1, 'srv3'->2, 'srv4'->3
y_integers = le_target.fit_transform(df_final[target])
# Convertir los enteros a formato One-Hot Encoding para clasificación multiclase
y_onehot = to_categorical(y_integers) # One-Hot para 4 clases

# Crear un escalador MinMax para normalizar las features al rango [0, 1]
scaler = MinMaxScaler()
# Ajustar el scaler a los datos y transformar las features de golpe
df_final[features] = scaler.fit_transform(df_final[features])

# Extraer los valores de las features como un array de NumPy
X = df_final[features].values
# Redimensionar el array para la entrada del LSTM: (num_muestras, 1 paso temporal, 12 features)
X = X.reshape(X.shape[0], 1, 12)

# Dividir los datos en conjuntos de entrenamiento (80%) y prueba (20%)
# random_state=42 asegura reproducibilidad; shuffle=True mezcla los datos antes de dividir
X_train, X_test, y_train, y_test = train_test_split(X, y_onehot, test_size=0.2, random_state=42, shuffle=True)

# --- PASO 3: DEFINICIÓN DE LA ARQUITECTURA DE LA RED NEURONAL ---
# Imprimir mensaje indicando la construcción del modelo
print(">>> [3/6] Construyendo Red Neuronal Profunda...")

# Crear un modelo secuencial (capas apiladas una tras otra)
model = Sequential([
    # Capa LSTM Bidireccional con 128 unidades: procesa la secuencia en ambas direcciones
    # input_shape=(1, 12): 1 paso de tiempo con 12 features
    Bidirectional(LSTM(128, return_sequences=False), input_shape=(1, 12)),
    # Capa de normalización por lotes para estabilizar y acelerar el entrenamiento
    BatchNormalization(),
    
    # Capa densa con 128 neuronas y activación ReLU para aprender patrones no lineales
    Dense(128, activation='relu'),
    # Capa Dropout que desactiva el 30% de las neuronas aleatoriamente para evitar overfitting
    Dropout(0.3), # Evitar overfitting ya que tenemos muchos datos
    
    # Capa densa intermedia con 64 neuronas y activación ReLU
    Dense(64, activation='relu'),
    
    # Capa de salida con 4 neuronas (una por servidor) y activación softmax
    # Softmax convierte las salidas en probabilidades que suman 1.0
    Dense(4, activation='softmax')
])

# Definir la función de pérdida con Label Smoothing de 0.1 para mejorar generalización
# Label Smoothing suaviza las etiquetas (de [1,0,0,0] a [0.925, 0.025, 0.025, 0.025])
loss_fn = tf.keras.losses.CategoricalCrossentropy(label_smoothing=0.1)
# Crear el optimizador Adam con tasa de aprendizaje de 0.001
optimizer = tf.keras.optimizers.Adam(learning_rate=0.001)

# Compilar el modelo con el optimizador, función de pérdida y métrica de accuracy
model.compile(optimizer=optimizer, loss=loss_fn, metrics=['accuracy'])

# --- PASO 4: ENTRENAMIENTO DEL MODELO ---
# Imprimir mensaje indicando el inicio del entrenamiento
print(">>> [4/6] Iniciando entrenamiento (100 Epochs)...")

# Definir los callbacks que controlan el entrenamiento dinámicamente
callbacks = [
    # EarlyStopping: detiene el entrenamiento si val_loss no mejora en 12 epochs consecutivas
    # restore_best_weights=True: restaura los pesos del mejor epoch al finalizar
    EarlyStopping(monitor='val_loss', patience=12, restore_best_weights=True, verbose=1),
    # ReduceLROnPlateau: reduce la tasa de aprendizaje a la mitad si val_loss no mejora en 5 epochs
    # min_lr=0.00001: límite mínimo para la tasa de aprendizaje
    ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=0.00001, verbose=1)
]

# Ejecutar el entrenamiento del modelo
history = model.fit(
    # Datos de entrada de entrenamiento
    X_train, y_train,
    # Número máximo de epochs (iteraciones completas sobre los datos)
    epochs=100, 
    # Tamaño del lote: 128 muestras procesadas antes de actualizar los pesos
    batch_size=128, # Batch size más grande para acelerar
    # Datos de validación para evaluar el rendimiento tras cada epoch
    validation_data=(X_test, y_test),
    # Callbacks para controlar el entrenamiento
    callbacks=callbacks,
    # Mostrar barra de progreso durante el entrenamiento
    verbose=1
)

# --- PASO 5: VISUALIZACIÓN DE RESULTADOS ---
# Imprimir mensaje indicando la generación de gráficas
print(">>> [5/6] Generando gráficas de rendimiento...")

# Extraer el historial de accuracy de entrenamiento por epoch
acc = history.history['accuracy']
# Extraer el historial de accuracy de validación por epoch
val_acc = history.history['val_accuracy']
# Extraer el historial de loss de entrenamiento por epoch
loss = history.history['loss']
# Extraer el historial de loss de validación por epoch
val_loss = history.history['val_loss']
# Crear un rango de epochs para el eje X de las gráficas
epochs_range = range(len(acc))

# Crear una figura de 14x6 pulgadas para las gráficas
plt.figure(figsize=(14, 6))

# Seleccionar el primer subplot (1 fila, 2 columnas, posición 1)
plt.subplot(1, 2, 1)
# Graficar la curva de accuracy de entrenamiento
plt.plot(epochs_range, acc, label='Training Accuracy')
# Graficar la curva de accuracy de validación
plt.plot(epochs_range, val_acc, label='Validation Accuracy')
# Establecer el título de la gráfica de accuracy
plt.title('Precisión del Modelo (Accuracy)')
# Agregar la leyenda en la esquina inferior derecha
plt.legend(loc='lower right')
# Activar la cuadrícula para mejor lectura
plt.grid(True)

# Seleccionar el segundo subplot (1 fila, 2 columnas, posición 2)
plt.subplot(1, 2, 2)
# Graficar la curva de loss de entrenamiento
plt.plot(epochs_range, loss, label='Training Loss')
# Graficar la curva de loss de validación
plt.plot(epochs_range, val_loss, label='Validation Loss')
# Establecer el título de la gráfica de loss
plt.title('Pérdida (Loss) - Entropía Cruzada')
# Agregar la leyenda en la esquina superior derecha
plt.legend(loc='upper right')
# Activar la cuadrícula para mejor lectura
plt.grid(True)

# Ajustar automáticamente el layout para que no se superpongan los subplots
plt.tight_layout()
# Guardar la figura completa como archivo PNG
plt.savefig('grafica_entrenamiento_4srv.png')
# Imprimir mensaje confirmando que la gráfica fue guardada
print("✅ Gráfica guardada: grafica_entrenamiento_4srv.png")

# --- PASO 6: EVALUACIÓN FINAL Y REPORTE ---
# Imprimir mensaje indicando la evaluación final
print(">>> [6/6] Evaluando precisión final...")

# Evaluar el modelo con los datos de prueba y obtener loss y accuracy finales
loss_final, acc_final = model.evaluate(X_test, y_test)
# Imprimir el accuracy final como porcentaje
print(f"\n🏆 ACCURACY FINAL (4 SRV): {acc_final*100:.2f}% 🏆")

# Obtener las predicciones del modelo para los datos de prueba y extraer la clase predicha
y_pred = np.argmax(model.predict(X_test), axis=1)
# Obtener las clases reales de los datos de prueba
y_true = np.argmax(y_test, axis=1)
# Obtener los nombres de las clases del encoder (ej: ['srv1', 'srv2', 'srv3', 'srv4'])
target_names = le_target.classes_

# Imprimir el encabezado del reporte de clasificación
print("\n--- REPORTE DE CLASIFICACIÓN ---")
# Imprimir el reporte con precisión, recall y f1-score por clase
print(classification_report(y_true, y_pred, target_names=target_names))

# Crear una nueva figura de 8x6 pulgadas para la matriz de confusión
plt.figure(figsize=(8, 6))
# Calcular la matriz de confusión comparando predicciones vs valores reales
cm = confusion_matrix(y_true, y_pred)
# Dibujar la matriz como un mapa de calor con anotaciones numéricas
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
            xticklabels=target_names, yticklabels=target_names)
# Establecer el título de la matriz de confusión
plt.title('Matriz de Confusión (4 Servidores)')
# Etiquetar el eje Y como "Real" (valores verdaderos)
plt.ylabel('Real')
# Etiquetar el eje X como "Predicho" (valores predichos por el modelo)
plt.xlabel('Predicho')
# Guardar la matriz de confusión como archivo PNG
plt.savefig('matriz_confusion_4srv.png')

# Guardar el modelo entrenado completo en formato HDF5
model.save('modelo_gns3.h5')
# Guardar el escalador entrenado como archivo serializado .joblib
joblib.dump(scaler, 'scaler_gns3.joblib')
# Guardar el encoder del target (servidores) como archivo serializado .joblib
joblib.dump(le_target, 'encoder_target_gns3.joblib')
# Guardar el encoder de etapa de tráfico como archivo serializado .joblib
joblib.dump(le_etapa, 'encoder_etapa_gns3.joblib')

# Imprimir mensaje final confirmando que todo se completó exitosamente
print("\n>>> ✅ TODO LISTO. Modelo guardado como 'modelo_gns3.h5'")

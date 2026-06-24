import streamlit as st # Importar Streamlit para dashboards web interactivos
import pandas as pd # Importar Pandas para DataFrames
import json # Importar json para leer/escribir archivos JSON
import time # Importar time para timestamps y pausas
import os # Importar os para verificar existencia de archivos
import subprocess # Importar subprocess para ejecutar comandos del sistema
import graphviz # Importar graphviz para diagramas de topología
import statistics # Importar statistics para cálculos estadísticos
import plotly.graph_objects as go # Importar Plotly para gráficos avanzados con anotaciones

# Configurar la página de Streamlit: título, ícono y layout amplio
st.set_page_config(
    page_title="SDN Dashboard - RR vs IA",
    page_icon="🧠",
    layout="wide"
)

# ═══════════════════════════════════════════════
# CONSTANTES Y CONFIGURACIÓN
# ═══════════════════════════════════════════════
DATA_FILE = 'estado_red.json'
LOG_FILE_RR = 'estado_red_log_rr.json'
LOG_FILE_IA = 'estado_red_log_ia.json'
LOG_FILE = 'estado_red_log.json'

PRUEBAS = {
    0: "🔴 En Vivo (Tiempo Real)",
    1: "P1: Tráfico Base (Control)",
    2: "P2: Operación Diaria (Normal)",
    3: "P3: Saturación y Estrés Crítico",
    4: "P4: Tráfico Pesado (Streaming)",
    5: "P5: Ráfagas Asimétricas (Spikes)",
    6: "P6: Degradación de Enlace (Jitter)",
    7: "P7: Congestión en Switches",
    8: "P8: Tráfico Mixto Concurrente",
    9: "P9: Simulación de Caída",
    10: "P10: Resiliencia (15 min)"
}

METRICAS_POR_PRUEBA = {
    1: ["IPLR", "IPTD", "IPDV", "Throughput", "Equidad"],
    2: ["IPLR", "IPTD", "IPDV", "Throughput", "Back-to-Back", "Equidad"],
    3: ["IPLR", "IPTD", "IPDV", "Throughput", "Back-to-Back", "Recovery"],
    4: ["IPLR", "IPTD", "IPDV", "Throughput", "Back-to-Back", "Equidad"],
    5: ["IPLR", "IPTD", "IPDV", "Throughput", "Recovery"],
    6: ["IPLR", "IPTD", "IPDV (Streaming/VoIP)", "Throughput"],
    7: ["IPLR", "IPTD", "IPDV", "Throughput", "Back-to-Back"],
    8: ["IPLR", "IPTD", "IPDV", "Throughput", "Back-to-Back", "Equidad"],
    9: ["IPLR", "IPTD", "Throughput", "Recovery", "Equidad"],
    10: ["IPLR", "IPTD", "Throughput", "Recovery", "Equidad temporal"]
}

METRIC_HELP = {
    'IPLR': {'nombre': 'IP Packet Loss Ratio (ITU-T Y.1540)', 'desc': 'Porcentaje de paquetes perdidos en la red.', 'lectura': '⬇️ Menor = Mejor. 0% es ideal. >5% indica congestión severa.', 'icono': '📉'},
    'IPTD': {'nombre': 'IP Packet Transfer Delay (ITU-T Y.1540)', 'desc': 'Tiempo que tarda un paquete en llegar del origen al destino (latencia).', 'lectura': '⬇️ Menor = Mejor. <10ms es excelente, >100ms es problemático.', 'icono': '⏱️'},
    'IPDV': {'nombre': 'IP Packet Delay Variation (ITU-T Y.1540)', 'desc': 'Variación en el retardo de paquetes (Jitter). Afecta streaming y VoIP.', 'lectura': '⬇️ Menor = Mejor. <5ms es aceptable para VoIP. Alto jitter causa cortes.', 'icono': '📶'},
    'Throughput': {'nombre': 'Throughput (RFC 2544)', 'desc': 'Ancho de banda real efectivo entre cliente y servidor.', 'lectura': '⬆️ Mayor = Mejor. Indica cuántos datos puede transferir la red.', 'icono': '📈'},
    'Back-to-Back': {'nombre': 'Back-to-Back Frames (RFC 2544)', 'desc': 'Capacidad de absorber ráfagas de paquetes sin pérdida.', 'lectura': '⬇️ Menor pérdida = Mejor. Mide la resiliencia ante tráfico explosivo.', 'icono': '📦'},
    'Recovery': {'nombre': 'System Recovery (RFC 2544)', 'desc': 'Tiempo que tarda el sistema en estabilizarse tras una sobrecarga.', 'lectura': '⬇️ Menor = Mejor. <10s excelente, >30s problemático.', 'icono': '🔄'},
    'Equidad': {'nombre': 'Equidad de Carga (Desviación Estándar)', 'desc': 'Distribución de CPU/RAM entre los 4 servidores.', 'lectura': '⬇️ Menor desviación = Mejor. Indica carga balanceada uniformemente.', 'icono': '⚖️'},
}

def render_metric_help():
    """Muestra guía de métricas en un expander no invasivo"""
    with st.expander('📖 ¿Cómo leer las métricas?', expanded=False):
        for key, info in METRIC_HELP.items():
            st.markdown(f"{info['icono']} **{key}** — {info['nombre']}")
            st.caption(f"{info['desc']}  \n{info['lectura']}")

def render_eviction_table(prueba_num):
    """Muestra tabla de evicción (cuando la IA detectó saturación y desvió tráfico)"""
    res_ia = load_resultado(prueba_num, 'IA')
    if not res_ia:
        st.info('Sin datos IA para mostrar evicción.')
        return
    decisiones = res_ia.get('decisiones', [])
    eventos = []
    for d in decisiones:
        mets = d.get('mets', {})
        for i in range(1, 5):
            cpu = mets.get(f'srv{i}_cpu', 0)
            if cpu > 90:
                import time as tm
                ts = d.get('timestamp', 0)
                eventos.append({
                    'Hora': tm.strftime('%H:%M:%S', tm.localtime(ts)) if ts else '',
                    'Cliente': d.get('cliente', ''),
                    'Servicio': d.get('servicio', ''),
                    'Servidor Saturado': f'SRV{i}',
                    'CPU Detectada': f'{cpu:.1f}%',
                    'Desviado a': d.get('servidor', '').upper(),
                    '¿Evitó?': '✅ Sí' if d.get('servidor', '') != f'srv{i}' else '❌ No'
                })
    if eventos:
        st.markdown(f'**{len(eventos)} eventos de evicción detectados**')
        st.dataframe(pd.DataFrame(eventos), use_container_width=True, hide_index=True, height=400)
    else:
        st.info('La IA no detectó servidores saturados (>90% CPU) en esta prueba.')

def render_reports_tab():
    """Muestra los 3 reportes generados en la pestaña de Reportes"""
    report_dir = os.path.join('pruebas', 'reportes')
    st.header('📋 Reportes Comparativos Generados')
    st.caption('Ejecuta `python3 pruebas/generar_reportes.py` después de las 20 pruebas para generar estos reportes.')
    # Reporte 1: Métricas Globales
    r1_path = os.path.join(report_dir, 'reporte_metricas_globales.json')
    if os.path.exists(r1_path):
        with open(r1_path) as f: r1 = json.load(f)
        st.subheader('1️⃣ Métricas Globales (ITU-T Y.1540 + RFC 2544)')
        rows = []
        for p in r1.get('pruebas', []):
            rr = p.get('RR', {})
            ia = p.get('IA', {})
            if isinstance(rr, str): rr = {}
            if isinstance(ia, str): ia = {}
            rows.append({
                'Prueba': f"P{p['prueba']}", 'Nombre': p['nombre'],
                'IPLR RR': f"{rr.get('iplr_percent','-')}%" if rr else 'N/A',
                'IPLR IA': f"{ia.get('iplr_percent','-')}%" if ia else 'N/A',
                'IPTD RR': f"{rr.get('iptd_avg_ms','-')}ms" if rr else 'N/A',
                'IPTD IA': f"{ia.get('iptd_avg_ms','-')}ms" if ia else 'N/A',
                'IPDV RR': f"{rr.get('ipdv_jitter_ms','-')}ms" if rr else 'N/A',
                'IPDV IA': f"{ia.get('ipdv_jitter_ms','-')}ms" if ia else 'N/A',
            })
        if rows: st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.warning('Reporte de métricas globales no encontrado. Ejecuta generar_reportes.py')
    st.markdown('---')
    # Reporte 2: Asignación Comparativa
    r2_path = os.path.join(report_dir, 'reporte_asignacion_comparativa.json')
    if os.path.exists(r2_path):
        with open(r2_path) as f: r2 = json.load(f)
        st.subheader('2️⃣ Asignación Comparativa (RR vs IA)')
        rows2 = []
        for p in r2.get('pruebas', []):
            rows2.append({'Prueba': f"P{p['prueba']}", 'Nombre': p['nombre'],
                'Decisiones Comparadas': p.get('total_comparadas', 0),
                'Coincidencias': p.get('coincidencias', 0),
                '% Coincidencia': f"{p.get('porcentaje_coincidencia', 0)}%"})
        if rows2: st.dataframe(pd.DataFrame(rows2), use_container_width=True, hide_index=True)
        st.caption('% bajo = la IA toma decisiones DIFERENTES al Round Robin (esperable).')
    else:
        st.warning('Reporte de asignación no encontrado.')
    st.markdown('---')
    # Reporte 3: Conmutación IA
    r3_path = os.path.join(report_dir, 'reporte_conmutacion_ia.json')
    if os.path.exists(r3_path):
        with open(r3_path) as f: r3 = json.load(f)
        st.subheader('3️⃣ Conmutación por Saturación (Solo IA)')
        st.metric('Total Eventos de Evicción', r3.get('total_eventos_globales', 0))
        for ep in r3.get('eventos_por_prueba', []):
            with st.expander(f"P{ep['prueba']}: {ep['nombre']} ({ep['total_eventos']} eventos)"):
                ev_rows = []
                for e in ep.get('eventos', []):
                    import time as tm
                    ts = e.get('timestamp', 0)
                    ev_rows.append({'Hora': tm.strftime('%H:%M:%S', tm.localtime(ts)) if ts else '',
                        'Cliente': e.get('cliente',''), 'Servidor Saturado': e.get('servidor_original',''),
                        'CPU': f"{e.get('cpu_detectada',0)}%", 'Desviado a': e.get('nuevo_servidor',''),
                        '¿Evitó?': '✅' if e.get('fue_desviado') else '❌'})
                if ev_rows: st.dataframe(pd.DataFrame(ev_rows), use_container_width=True, hide_index=True)
    else:
        st.warning('Reporte de conmutación IA no encontrado.')

# ═══════════════════════════════════════════════
# FUNCIONES AUXILIARES
# ═══════════════════════════════════════════════
def load_data():
    """Carga el estado actual de la red desde estado_red.json"""
    if not os.path.exists(DATA_FILE):
        return None
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        return None

def load_resultado(prueba_num, modo):
    """Carga resultado guardado de una prueba para un modo (RR o IA)"""
    carpetas = {
        1: "prueba1_trafico_base", 2: "prueba2_operacion_diaria",
        3: "prueba3_saturacion", 4: "prueba4_streaming",
        5: "prueba5_rafagas", 6: "prueba6_jitter",
        7: "prueba7_packet_loss", 8: "prueba8_trafico_mixto",
        9: "prueba9_caida", 10: "prueba10_resiliencia"
    }
    carpeta = carpetas.get(prueba_num, "")
    fname = os.path.join("pruebas", carpeta, f"resultado_prueba{prueba_num}_{modo}.json")
    if not os.path.exists(fname):
        fname = f"resultado_prueba{prueba_num}_{modo}.json"
        if not os.path.exists(fname):
            return None
    try:
        with open(fname, 'r') as f:
            return json.load(f)
    except:
        return None

def get_controller_stats():
    """Obtiene CPU y RAM del proceso ryu-manager en tiempo real"""
    try:
        result = subprocess.run(
            ['bash', '-c', "ps aux | grep '[r]yu-manager' | head -1 | awk '{print $3, $4, $6}'"],
            capture_output=True, text=True, timeout=5
        )
        parts = result.stdout.strip().split()
        if len(parts) >= 3:
            return {'cpu': float(parts[0]), 'ram': float(parts[1]), 'ram_kb': int(parts[2])}
    except:
        pass
    return {'cpu': 0, 'ram': 0, 'ram_kb': 0}

def read_log_events(log_file, session_key, mode_filter=None):
    """Lee eventos de un archivo de log append-only, filtrando por modo (RR o IA)"""
    if session_key not in st.session_state:
        st.session_state[session_key] = []
    lines_key = f"{session_key}_lines"
    if lines_key not in st.session_state:
        st.session_state[lines_key] = 0

    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                all_lines = f.readlines()
            new_lines = all_lines[st.session_state[lines_key]:]
            st.session_state[lines_key] = len(all_lines)
            for line in new_lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                    ts = ev.get('t', 0)
                    evt = ev.get('e', {})
                    mets = evt.get('metricas', {})
                    # Filtrar por modo: si se especifica, solo aceptar eventos de ese modo
                    event_mode = evt.get('modo', '')
                    if mode_filter and event_mode and event_mode != mode_filter:
                        continue  # Saltar eventos que no corresponden a este modo
                    st.session_state[session_key].insert(0, {
                        "Hora": time.strftime('%H:%M:%S', time.localtime(ts)),
                        "Modo": event_mode if event_mode else "?",
                        "Cliente": evt.get('cliente', ''),
                        "Servicio": evt.get('servicio', ''),
                        "Servidor": evt.get('servidor_elegido', '').upper(),
                        "CPU S1": f"{mets.get('srv1_cpu',0):.1f}%",
                        "CPU S2": f"{mets.get('srv2_cpu',0):.1f}%",
                        "CPU S3": f"{mets.get('srv3_cpu',0):.1f}%",
                        "CPU S4": f"{mets.get('srv4_cpu',0):.1f}%",
                        "BW": f"{mets.get('bw_solicitado',0):.1f} Mbps",
                        "Loss": f"{mets.get('loss',0)}%"
                    })
                except:
                    pass
            st.session_state[session_key] = st.session_state[session_key][:200]
        except:
            pass
    return st.session_state[session_key]

def render_topology(chosen_server, client_ip, title, color_active='lightgreen'):
    """Dibuja la topología de red con Graphviz, resaltando el servidor activo"""
    graph = graphviz.Digraph()
    graph.attr(rankdir='LR', bgcolor='transparent', size='8,5')
    graph.node('C', f"Cliente\n{client_ip}", shape='ellipse', style='filled', fillcolor='lightblue', fontsize='11')
    graph.node('SW', 'Switch SDN', shape='box', style='filled', fillcolor='gold', fontsize='11')
    for i in range(1, 5):
        sname = f'srv{i}'
        is_active = (chosen_server == sname)
        fill = color_active if is_active else 'white'
        border = 'green' if is_active else 'gray'
        pw = '3' if is_active else '1'
        graph.node(f'S{i}', f'SRV{i}', shape='component', style='filled', fillcolor=fill, fontsize='11')
        graph.edge('SW', f'S{i}', color=border, penwidth=pw)
    graph.edge('C', 'SW')
    st.graphviz_chart(graph)


def crear_grafico_lineas(categorias, valores_dict, titulo, unidad='', height=350):
    fig = go.Figure()
    colores = ['#1E90FF', '#32CD32', '#FF6B35', '#FFD700']
    for i, (nombre, vals) in enumerate(valores_dict.items()):
        color = colores[i % len(colores)]
        fig.add_trace(go.Scatter(x=categorias, y=vals, mode='lines+markers', name=nombre, line=dict(color=color, width=3)))
    fig.update_layout(title=dict(text=titulo, font=dict(size=14)), height=height, margin=dict(l=40, r=40, t=50, b=40), legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1), yaxis=dict(title=unidad), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
    fig.update_yaxes(gridcolor='rgba(128,128,128,0.2)')
    return fig

def crear_gauge_chart(valor, titulo, max_val=100, color='#1E90FF'):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = valor,
        title = {'text': titulo, 'font': {'size': 14}},
        gauge = {
            'axis': {'range': [0, max_val], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': color},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, max_val*0.1], 'color': 'rgba(0, 255, 0, 0.1)'},
                {'range': [max_val*0.1, max_val*0.5], 'color': 'rgba(255, 255, 0, 0.1)'},
                {'range': [max_val*0.5, max_val], 'color': 'rgba(255, 0, 0, 0.1)'}
            ]
        }
    ))
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor='rgba(0,0,0,0)', font={'color': "white", 'family': "Arial"})
    return fig

def crear_histograma(valores, titulo, color='#1E90FF'):
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=valores, marker_color=color, opacity=0.75))
    fig.update_layout(title=dict(text=titulo, font=dict(size=14)), height=300, margin=dict(l=40, r=40, t=50, b=40), yaxis=dict(title='Frecuencia'), xaxis=dict(title='ms'), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
    fig.update_yaxes(gridcolor='rgba(128,128,128,0.2)')
    return fig

def crear_grafico_barras(categorias, valores_dict, titulo, unidad='%', height=350):
    """Crea un gráfico de barras agrupadas con Plotly, con valores sobre cada barra"""
    colores = ['#1E90FF', '#32CD32', '#FF6B35', '#FFD700', '#FF4B8B', '#9B59B6']
    fig = go.Figure()
    for i, (nombre, vals) in enumerate(valores_dict.items()):
        color = colores[i % len(colores)]
        fig.add_trace(go.Bar(
            name=nombre,
            x=categorias,
            y=vals,
            marker_color=color,
            text=[f'{v:.1f}{unidad}' for v in vals],
            textposition='outside',
            textfont=dict(size=11, color=color)
        ))
    fig.update_layout(
        title=dict(text=titulo, font=dict(size=14)),
        barmode='group',
        height=height,
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        yaxis=dict(title=unidad),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    fig.update_yaxes(gridcolor='rgba(128,128,128,0.2)')
    return fig

def render_server_charts(mets, key_prefix='srv'):
    """Dibuja las gráficas de barras de CPU y RAM de los 4 servidores con Plotly"""
    servidores = ['SRV1', 'SRV2', 'SRV3', 'SRV4']
    cpus = [mets.get(f'srv{i}_cpu', 0) for i in range(1, 5)]
    rams = [mets.get(f'srv{i}_ram', 0) for i in range(1, 5)]
    fig = crear_grafico_barras(servidores, {'CPU (%)': cpus, 'RAM (%)': rams}, 'CPU y RAM de Servidores', '%')
    st.plotly_chart(fig, use_container_width=True, key=f'chart_{key_prefix}_cpuram')

def render_controller_panel(mode_name, res):
    """Muestra las métricas del controlador para un resultado de prueba"""
    if res and 'controlador_stats' in res:
        cs = res['controlador_stats']
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("CPU Avg", f"{cs.get('cpu_avg',0):.2f}%")
        c2.metric("CPU Max", f"{cs.get('cpu_max',0):.2f}%")
        c3.metric("RAM Avg", f"{cs.get('ram_avg',0):.2f}%")
        c4.metric("RAM Max", f"{cs.get('ram_max',0):.2f}%")
        # Tiempo de respuesta promedio y total de decisiones
        rt1, rt2 = st.columns(2)
        rt_avg = res.get('response_time_avg_ms', 0)
        rt_total = res.get('response_time_total_decisions', 0)
        rt1.metric("⏱️ Tiempo Respuesta Avg", f"{rt_avg:.2f} ms")
        rt2.metric("📊 Total Decisiones", f"{rt_total}")
    else:
        st.info(f"Sin datos de controlador para {mode_name}")

def render_metrics_table(res, mode_name, key_prefix='metrics'):
    """Muestra las métricas de una prueba como tablas formateadas"""
    if not res:
        st.warning(f"No se encontraron resultados para {mode_name}. Ejecuta la prueba primero.")
        return
    mets = res.get('metricas', {})

    # Latencia estándar (dict de hosts)
    lat = mets.get('latencia', mets.get('iptd', mets.get('latencia_base', mets.get('latencia_degradada', {}))))
    if lat and isinstance(lat, dict):
        st.markdown("##### ⏱️ Latencia")
        lat_rows = []
        for host, val in lat.items():
            if isinstance(val, dict):
                lat_rows.append({'Host': host, 'Avg (ms)': f"{val.get('avg',0):.2f}", 'Min (ms)': f"{val.get('min',0):.2f}", 'Max (ms)': f"{val.get('max',0):.2f}"})
        if lat_rows:
            st.dataframe(pd.DataFrame(lat_rows), use_container_width=True, hide_index=True)

    # Latencia temporal (P10: lista de muestras en el tiempo)
    lat_temp = mets.get('latencia_temporal', [])
    if lat_temp and isinstance(lat_temp, list):
        st.markdown("##### ⏱️ Latencia en el Tiempo")
        lat_t_rows = []
        for s in lat_temp:
            avg_val = s.get('latencia_avg', 0)
            if isinstance(avg_val, dict):
                avg_val = avg_val.get('avg', 0)
            lat_t_rows.append({'Ciclo': s.get('ciclo', 0), 'Tiempo (s)': s.get('tiempo_s', 0), 'Latencia Avg (ms)': round(avg_val, 2)})
        if lat_t_rows:
            df_lt = pd.DataFrame(lat_t_rows)
            st.dataframe(df_lt, use_container_width=True, hide_index=True)
            fig_lt = go.Figure()
            fig_lt.add_trace(go.Bar(x=df_lt['Tiempo (s)'], y=df_lt['Latencia Avg (ms)'],
                name='Latencia', marker_color='#FF6B35',
                text=[f"{v:.2f}ms" for v in df_lt['Latencia Avg (ms)']], textposition='outside'))
            fig_lt.update_layout(title='Latencia en el Tiempo', xaxis_title='Tiempo (s)', xaxis=dict(type='category'),
                yaxis_title='ms', height=300, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            fig_lt.update_yaxes(gridcolor='rgba(128,128,128,0.2)')
            st.plotly_chart(fig_lt, use_container_width=True, key=f'chart_{key_prefix}_lat_temp')

    # Throughput
    tp = mets.get('throughput', mets.get('throughput_streaming', {}))
    if tp and isinstance(tp, dict):
        st.markdown("##### 📈 Throughput")
        tp_rows = [{'Host': k, 'Mbps': f"{v:.2f}" if isinstance(v, (int, float)) else v} for k, v in tp.items()]
        if tp_rows:
            st.dataframe(pd.DataFrame(tp_rows), use_container_width=True, hide_index=True)

    # IPLR detallado (nuevo formato)
    iplr = mets.get('iplr', {})
    if iplr and isinstance(iplr, dict):
        st.markdown("##### 📉 IPLR - IP Packet Loss Ratio (ITU-T Y.1540)")
        iplr_rows = []
        for host, val in iplr.items():
            if isinstance(val, dict):
                iplr_rows.append({'Host': host, 'Enviados': val.get('enviados', 0),
                    'Recibidos': val.get('recibidos', 0), 'Perdidos': val.get('perdidos', 0),
                    'Pérdida (%)': f"{val.get('porcentaje', 0):.2f}%"})
        if iplr_rows:
            st.dataframe(pd.DataFrame(iplr_rows), use_container_width=True, hide_index=True)

    # Pérdida de paquetes general
    perdida_gen = mets.get('perdida_general', None)
    if perdida_gen is not None:
        st.markdown("##### 📉 Pérdida de Paquetes General")
        color = '🟢' if perdida_gen < 5 else ('🟡' if perdida_gen < 15 else '🔴')
        st.metric(f"{color} IPLR General", f"{perdida_gen:.1f}%")
        st.caption("Promedio de pérdida de paquetes (ping) entre todos los clientes")

    # Jitter
    jitter = mets.get('jitter', {})
    if jitter and isinstance(jitter, dict):
        st.markdown("##### 📶 Jitter (Variación de Latencia)")
        j_rows = [{'Host': k, 'Jitter (ms)': f"{v:.2f}"} for k, v in jitter.items()]
        if j_rows:
            st.dataframe(pd.DataFrame(j_rows), use_container_width=True, hide_index=True)
        j_avg = mets.get('jitter_avg', 0)
        st.metric("Jitter Promedio", f"{j_avg:.2f} ms")

    # IPDV Streaming (8080) y VoIP (5060)
    ipdv_s = mets.get('ipdv_streaming', {})
    ipdv_v = mets.get('ipdv_voip', {})
    if (ipdv_s and isinstance(ipdv_s, dict)) or (ipdv_v and isinstance(ipdv_v, dict)):
        st.markdown("##### 📶 IPDV - Streaming (8080) / VoIP (5060)")
        st.caption("⬇️ Menor jitter = Mejor. <5ms aceptable para VoIP, <10ms para streaming.")
        ipdv_rows = []
        hosts_s = sorted(set(list(ipdv_s.keys()) + list(ipdv_v.keys())))
        for h in hosts_s:
            s_val = ipdv_s.get(h, {})
            v_val = ipdv_v.get(h, {})
            ipdv_rows.append({
                'Host': h,
                'Streaming (ms)': f"{s_val.get('jitter_mdev', 0):.2f}" if isinstance(s_val, dict) else 'N/A',
                'VoIP (ms)': f"{v_val.get('jitter_mdev', 0):.2f}" if isinstance(v_val, dict) else 'N/A'
            })
        if ipdv_rows:
            st.dataframe(pd.DataFrame(ipdv_rows), use_container_width=True, hide_index=True)

    # Equidad CPU estándar (soporta formato viejo y nuevo)
    eq = mets.get('equidad', {})
    eq_cpu = eq.get('cpu', mets.get('equidad_cpu', {})) if isinstance(eq, dict) else mets.get('equidad_cpu', {})
    eq_ram = eq.get('ram', mets.get('equidad_ram', {})) if isinstance(eq, dict) else mets.get('equidad_ram', {})
    if eq_cpu and isinstance(eq_cpu, dict) and ('promedio' in eq_cpu or 'desviacion_std' in eq_cpu):
        st.markdown("##### ⚖️ Equidad CPU / RAM")
        ec1, ec2, ec3, ec4 = st.columns(4)
        ec1.metric("CPU Promedio", f"{eq_cpu.get('promedio', 0):.2f}%")
        ec2.metric("CPU Desv. Std", f"{eq_cpu.get('desviacion_std', 0):.2f}%")
        ec3.metric("RAM Promedio", f"{eq_ram.get('promedio', 0):.2f}%")
        ec4.metric("RAM Desv. Std", f"{eq_ram.get('desviacion_std', 0):.2f}%")

    # Equidad temporal (P10: lista de muestras en el tiempo)
    eq_temp = mets.get('equidad_temporal', [])
    if eq_temp and isinstance(eq_temp, list):
        st.markdown("##### ⚖️ Equidad CPU/RAM en el Tiempo")
        eq_rows = []
        for s in eq_temp:
            eq_rows.append({'Tiempo (s)': s.get('tiempo', 0),
                'CPU StdDev': round(s.get('cpu_std', 0), 2),
                'RAM StdDev': round(s.get('ram_std', 0), 2)})
        if eq_rows:
            df_eq = pd.DataFrame(eq_rows)
            st.dataframe(df_eq, use_container_width=True, hide_index=True)
            fig_eq = go.Figure()
            fig_eq.add_trace(go.Bar(x=df_eq['Tiempo (s)'], y=df_eq['CPU StdDev'],
                name='CPU StdDev', marker_color='#FF6B35'))
            fig_eq.add_trace(go.Bar(x=df_eq['Tiempo (s)'], y=df_eq['RAM StdDev'],
                name='RAM StdDev', marker_color='#1E90FF'))
            fig_eq.update_layout(title='Desviación Estándar en el Tiempo (Menor = Mejor)', barmode='group',
                xaxis_title='Tiempo (s)', xaxis=dict(type='category'), yaxis_title='StdDev (%)', height=300,
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1))
            fig_eq.update_yaxes(gridcolor='rgba(128,128,128,0.2)')
            st.plotly_chart(fig_eq, use_container_width=True, key=f'chart_{key_prefix}_eq_temp')

    # Info de P10
    if 'total_ciclos' in mets:
        c1, c2 = st.columns(2)
        c1.metric("🔄 Total Ciclos", mets.get('total_ciclos', 0))
        c2.metric("⏱️ Duración Real", f"{mets.get('duracion_real_s', 0)}s")
        
        # Calcular y mostrar métricas globales de estabilidad (StdDev)
        if eq_temp:
            import statistics
            all_cpu_std = [s.get('cpu_std', 0) for s in eq_temp]
            all_ram_std = [s.get('ram_std', 0) for s in eq_temp]
            avg_cpu_std = statistics.mean(all_cpu_std) if all_cpu_std else 0
            avg_ram_std = statistics.mean(all_ram_std) if all_ram_std else 0
            st.markdown("##### 🛡️ Estabilidad Global de la Red")
            sc1, sc2 = st.columns(2)
            sc1.metric("Desviación CPU (Promedio)", f"{avg_cpu_std:.2f}%")
            sc2.metric("Desviación RAM (Promedio)", f"{avg_ram_std:.2f}%")

    # Recovery Time (P3, P5, P9) - soporta formato viejo y nuevo
    recovery = mets.get('recovery', {})
    rt = recovery.get('recovery_s', mets.get('recovery_time_s', 0)) if isinstance(recovery, dict) else mets.get('recovery_time_s', 0)
    if rt:
        st.markdown("##### 🔄 System Recovery (RFC 2544)")
        color = '🟢' if rt < 10 else ('🟡' if rt < 30 else '🔴')
        st.metric(f"{color} Tiempo de Recuperación", f"{rt} segundos")
        if isinstance(recovery, dict) and recovery.get('estable') is not None:
            st.caption(f"{'✅ Sistema estabilizado' if recovery['estable'] else '⚠️ No se alcanzó estabilidad'} "
                       f"(latencia final: {recovery.get('latencia_final', 0):.2f}ms)")
        else:
            st.caption("Tiempo que tardó el controlador en estabilizar la red tras la sobrecarga")

    # Back-to-Back Frames (RFC 2544)
    b2b = mets.get('back_to_back', {})
    if b2b and isinstance(b2b, dict):
        st.markdown("##### 📦 Back-to-Back Frames (RFC 2544)")
        b2b_rows = []
        for burst_key, val in b2b.items():
            if isinstance(val, dict):
                b2b_rows.append({'Ráfaga': burst_key, 'Frames': val.get('frames_enviados', 0),
                    'Pérdida (%)': f"{val.get('loss_percent', 0):.1f}%", 'Detalle': val.get('detalle', 'N/A')})
        if b2b_rows:
            st.dataframe(pd.DataFrame(b2b_rows), use_container_width=True, hide_index=True)

def render_decision_table(res, mode_name, key_suffix=''):
    """Muestra la tabla de decisiones del controlador para un resultado de prueba"""
    decisiones = res.get('decisiones', [])
    if not decisiones:
        st.info(f"Sin decisiones registradas para {mode_name}. Ejecuta la prueba nuevamente para capturar las decisiones.")
        return
    st.markdown(f"**{len(decisiones)} decisiones registradas**")
    import time as time_mod
    dec_rows = []
    for d in decisiones:
        ts = d.get('timestamp', 0)
        mets = d.get('mets', {})
        dec_rows.append({
            'Hora': time_mod.strftime('%H:%M:%S', time_mod.localtime(ts)) if ts else '',
            'Cliente': d.get('cliente', ''),
            'Servicio': d.get('servicio', ''),
            'Servidor Elegido': d.get('servidor', '').upper(),
            'CPU S1': f"{mets.get('srv1_cpu', 0):.1f}%",
            'CPU S2': f"{mets.get('srv2_cpu', 0):.1f}%",
            'CPU S3': f"{mets.get('srv3_cpu', 0):.1f}%",
            'CPU S4': f"{mets.get('srv4_cpu', 0):.1f}%"
        })
    st.dataframe(pd.DataFrame(dec_rows), use_container_width=True, height=400, hide_index=True)

# ═══════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════
st.sidebar.title("⚙️ Configuración")
prueba_sel = st.sidebar.selectbox("Seleccionar Prueba:", list(PRUEBAS.keys()), format_func=lambda x: PRUEBAS[x])

if prueba_sel > 0:
    st.sidebar.markdown("---")
    st.sidebar.subheader("📋 Métricas de esta prueba:")
    for m in METRICAS_POR_PRUEBA.get(prueba_sel, []):
        base_key = m.split(' ')[0].split('(')[0]
        info = METRIC_HELP.get(base_key, {})
        tip = info.get('lectura', '') if info else ''
        st.sidebar.markdown(f"  ✅ {m}")
        if tip:
            st.sidebar.caption(f"    {tip}")

# ═══════════════════════════════════════════════
# TÍTULO PRINCIPAL
# ═══════════════════════════════════════════════
st.title("🧠 Panel de Control SDN - RR vs IA")
if prueba_sel > 0:
    st.markdown(f"### 📌 {PRUEBAS[prueba_sel]}")
render_metric_help()
st.markdown("---")

# ═══════════════════════════════════════════════
# 4 PESTAÑAS PRINCIPALES
# ═══════════════════════════════════════════════
tab_rr, tab_ia, tab_comp, tab_reports = st.tabs(["🔄 Round Robin", "🧠 IA (LSTM)", "📊 Comparativa", "📋 Reportes"])

# ─────────────────────────────────────────────
# TAB 1: ROUND ROBIN
# ─────────────────────────────────────────────
with tab_rr:
    st.header("🔄 Decisiones Round Robin")

    if prueba_sel > 0:
        # === MODO RESULTADOS DE PRUEBA ===
        res_rr = load_resultado(prueba_sel, "RR")
        if not res_rr:
            st.warning(f"No se encontraron resultados RR para la Prueba {prueba_sel}. Ejecuta la prueba primero.")
        else:
            st.subheader("🖥️ Controlador Round Robin")
            render_controller_panel("RR", res_rr)
            st.markdown("---")
            st.subheader("📊 Métricas de la Prueba")
            render_metrics_table(res_rr, "Round Robin", key_prefix='rr_res')
            st.markdown("---")
            st.subheader("📝 Decisiones del Controlador Round Robin")
            render_decision_table(res_rr, "Round Robin", key_suffix='rr')
    else:
        # === MODO EN VIVO ===
        st.subheader("🔴 Modo En Vivo - Round Robin")
        # Leer eventos del log (archivo dedicado RR o genérico)
        history_rr = read_log_events(LOG_FILE, 'history_rr', mode_filter='RR')

        data = load_data()
        if data and 'ultimo_evento' in data:
            evt = data['ultimo_evento']
            mets = evt.get('metricas', {})

            col_topo, col_stats = st.columns([1, 1])
            with col_topo:
                st.markdown("##### 🕸️ Topología RR")
                render_topology(evt.get('servidor_elegido', ''), evt.get('cliente', ''), "RR", color_active='#90EE90')
            with col_stats:
                st.markdown("##### 📊 Estado de Servidores (RR)")
                render_server_charts(mets, key_prefix='rr_live')

            st.markdown("---")
            # Métricas de red
            nc1, nc2, nc3 = st.columns(3)
            nc1.metric("Ancho de Banda", f"{mets.get('bw_solicitado',0):.1f} Mbps")
            nc2.metric("Jitter", f"{mets.get('jitter',0):.1f} ms")
            nc3.metric("Pérdida", f"{mets.get('loss', 0)}%")

        st.markdown("---")
        st.subheader(f"📜 Historial de Decisiones RR ({len(history_rr)} eventos)")
        if history_rr:
            st.dataframe(pd.DataFrame(history_rr), use_container_width=True, height=400, hide_index=True)
        else:
            st.info("Esperando eventos del controlador Round Robin...")

        if st.button("🗑️ Limpiar Historial RR", key="clear_rr"):
            st.session_state['history_rr'] = []
            st.session_state['history_rr_lines'] = 0
            st.rerun()

# ─────────────────────────────────────────────
# TAB 2: IA (LSTM)
# ─────────────────────────────────────────────
with tab_ia:
    st.header("🧠 Decisiones IA (LSTM)")

    if prueba_sel > 0:
        # === MODO RESULTADOS DE PRUEBA ===
        res_ia = load_resultado(prueba_sel, "IA")
        if not res_ia:
            st.warning(f"No se encontraron resultados IA para la Prueba {prueba_sel}. Ejecuta la prueba primero.")
        else:
            st.subheader("🖥️ Controlador IA (LSTM)")
            render_controller_panel("IA", res_ia)
            st.markdown("---")
            st.subheader("📊 Métricas de la Prueba")
            render_metrics_table(res_ia, "IA (LSTM)", key_prefix='ia_res')
            st.markdown("---")
            st.subheader("📝 Decisiones del Controlador IA (LSTM)")
            render_decision_table(res_ia, "IA (LSTM)", key_suffix='ia')
            st.markdown("---")
            st.subheader("🚨 Tabla de Evicción por Saturación (IA)")
            st.caption("Eventos donde la IA detectó un servidor con CPU >90% y desvió tráfico a otro servidor.")
            render_eviction_table(prueba_sel)
    else:
        # === MODO EN VIVO ===
        st.subheader("🔴 Modo En Vivo - IA (LSTM)")
        history_ia = read_log_events(LOG_FILE, 'history_ia', mode_filter='IA')

        data = load_data()
        if data and 'ultimo_evento' in data:
            evt = data['ultimo_evento']
            mets = evt.get('metricas', {})

            col_topo, col_stats = st.columns([1, 1])
            with col_topo:
                st.markdown("##### 🕸️ Topología IA")
                render_topology(evt.get('servidor_elegido', ''), evt.get('cliente', ''), "IA", color_active='#87CEEB')
            with col_stats:
                st.markdown("##### 📊 Estado de Servidores (IA)")
                render_server_charts(mets, key_prefix='ia_live')

            st.markdown("---")
            nc1, nc2, nc3 = st.columns(3)
            nc1.metric("Ancho de Banda", f"{mets.get('bw_solicitado',0):.1f} Mbps")
            nc2.metric("Jitter", f"{mets.get('jitter',0):.1f} ms")
            nc3.metric("Pérdida", f"{mets.get('loss', 0)}%")

        st.markdown("---")
        st.subheader(f"📜 Historial de Decisiones IA ({len(history_ia)} eventos)")
        if history_ia:
            st.dataframe(pd.DataFrame(history_ia), use_container_width=True, height=400, hide_index=True)
        else:
            st.info("Esperando eventos del controlador IA (LSTM)...")

        if st.button("🗑️ Limpiar Historial IA", key="clear_ia"):
            st.session_state['history_ia'] = []
            st.session_state['history_ia_lines'] = 0
            st.rerun()

# ─────────────────────────────────────────────
# TAB 3: COMPARATIVA
# ─────────────────────────────────────────────
with tab_comp:
    st.header("📊 Comparativa Round Robin vs IA (LSTM) - Y.1540 & RFC 2544")

    if prueba_sel > 0:
        res_rr = load_resultado(prueba_sel, "RR")
        res_ia = load_resultado(prueba_sel, "IA")

        if not res_rr and not res_ia:
            st.warning("No se encontraron resultados para esta prueba. Ejecuta ambas versiones primero (RR e IA).")
        else:
            mets_rr = res_rr.get('metricas', {}) if res_rr else {}
            mets_ia = res_ia.get('metricas', {}) if res_ia else {}

            # ── RESUMEN EJECUTIVO ──
            st.markdown("### 🏆 Resumen Ejecutivo de Mejoras (IA vs RR)")
            
            lat_rr_d = mets_rr.get('latencia', mets_rr.get('iptd', mets_rr.get('latencia_congestion', mets_rr.get('latencia_base', {}))))
            lat_ia_d = mets_ia.get('latencia', mets_ia.get('iptd', mets_ia.get('latencia_congestion', mets_ia.get('latencia_base', {}))))
            lat_rr_avg = list(lat_rr_d.values())[0].get('avg', 1) if lat_rr_d and isinstance(list(lat_rr_d.values())[0], dict) else 1
            lat_ia_avg = list(lat_ia_d.values())[0].get('avg', 1) if lat_ia_d and isinstance(list(lat_ia_d.values())[0], dict) else 1
            lat_imp = ((lat_rr_avg - lat_ia_avg) / lat_rr_avg) * 100 if lat_rr_avg > 0 else 0

            loss_rr_gen = mets_rr.get('perdida_general', 0)
            loss_ia_gen = mets_ia.get('perdida_general', 0)
            loss_imp = ((loss_rr_gen - loss_ia_gen) / max(loss_rr_gen, 0.01)) * 100 if loss_rr_gen > 0 else (0 if loss_ia_gen == 0 else -100)

            jit_rr_avg = mets_rr.get('jitter_avg', 0)
            jit_ia_avg = mets_ia.get('jitter_avg', 0)
            jit_imp = ((jit_rr_avg - jit_ia_avg) / max(jit_rr_avg, 0.01)) * 100 if jit_rr_avg > 0 else 0

            tp_rr_list = list(mets_rr.get('throughput', mets_rr.get('throughput_streaming', {})).values())
            tp_ia_list = list(mets_ia.get('throughput', mets_ia.get('throughput_streaming', {})).values())
            tp_rr_avg = sum(tp_rr_list)/len(tp_rr_list) if tp_rr_list else 1
            tp_ia_avg = sum(tp_ia_list)/len(tp_ia_list) if tp_ia_list else 1
            tp_imp = ((tp_ia_avg - tp_rr_avg) / tp_rr_avg) * 100 if tp_rr_avg > 0 else 0

            ex1, ex2, ex3, ex4 = st.columns(4)
            ex1.metric("Latencia (IPTD)", f"{lat_imp:.1f}%", f"{lat_imp:.1f}%" if lat_imp > 0 else f"{lat_imp:.1f}%")
            ex2.metric("Pérdida (IPLR)", f"{loss_imp:.1f}%", f"{loss_imp:.1f}%" if loss_imp > 0 else f"{loss_imp:.1f}%")
            ex3.metric("Jitter (IPDV)", f"{jit_imp:.1f}%", f"{jit_imp:.1f}%" if jit_imp > 0 else f"{jit_imp:.1f}%")
            ex4.metric("Throughput", f"{tp_imp:.1f}%", f"{tp_imp:.1f}%" if tp_imp > 0 else f"{tp_imp:.1f}%")
            st.markdown("---")

            # ── ITU-T Y.1540 ──
            st.subheader("🌐 Estándar ITU-T Y.1540 (Calidad de Experiencia)")
            
            # IPTD (Latencia y Tiempo de Inferencia)
            st.markdown("#### 1. IP Packet Transfer Delay (IPTD)")
            st.markdown("Comprende el retardo de transmisión más el **tiempo de respuesta/inferencia** del controlador SDN.")
            
            rt_rr = res_rr.get('response_time_avg_ms', 0) if res_rr else 0
            rt_ia = res_ia.get('response_time_avg_ms', 0) if res_ia else 0
            
            lat_rr_dict = mets_rr.get('latencia', mets_rr.get('iptd', mets_rr.get('latencia_congestion', mets_rr.get('latencia_base', {}))))
            lat_ia_dict = mets_ia.get('latencia', mets_ia.get('iptd', mets_ia.get('latencia_congestion', mets_ia.get('latencia_base', {}))))
            hosts = sorted(set(list(lat_rr_dict.keys()) + list(lat_ia_dict.keys())))
            
            lat_data_rr = [lat_rr_dict.get(h, {}).get('avg', 0) if isinstance(lat_rr_dict.get(h, {}), dict) else 0 for h in hosts]
            lat_data_ia = [lat_ia_dict.get(h, {}).get('avg', 0) if isinstance(lat_ia_dict.get(h, {}), dict) else 0 for h in hosts]
            
            if hosts:
                fig_iptd = crear_grafico_lineas(hosts, {'Round Robin (Red)': lat_data_rr, 'IA LSTM (Red)': lat_data_ia}, 'Latencia Extremo a Extremo (IPTD)', 'ms', 350)
                st.plotly_chart(fig_iptd, use_container_width=True, key='iptd_chart')
            else:
                st.info("Sin datos de latencia para graficar.")
            
            rc1, rc2 = st.columns(2)
            rc1.metric("Tiempo de Respuesta RR", f"{rt_rr:.2f} ms")
            rc2.metric("Tiempo de Inferencia IA", f"{rt_ia:.2f} ms")

            # IPLR (Packet Loss)
            st.markdown("#### 2. IP Packet Loss Ratio (IPLR)")
            gl1, gl2 = st.columns(2)
            with gl1:
                st.plotly_chart(crear_gauge_chart(loss_rr_gen, "Pérdida Round Robin (%)", 100, '#1E90FF'), use_container_width=True, key='gauge_rr')
            with gl2:
                st.plotly_chart(crear_gauge_chart(loss_ia_gen, "Pérdida IA LSTM (%)", 100, '#32CD32'), use_container_width=True, key='gauge_ia')

            # IPDV (Jitter)
            st.markdown("#### 3. IP Packet Delay Variation (IPDV) - Streaming 8080 / VoIP 5060")
            st.caption("⬇️ Menor jitter = Mejor. <5ms aceptable para VoIP, <10ms para streaming.")

            # Leer ipdv_streaming y ipdv_voip
            ipdv_s_rr = mets_rr.get('ipdv_streaming', {})
            ipdv_s_ia = mets_ia.get('ipdv_streaming', {})
            ipdv_v_rr = mets_rr.get('ipdv_voip', {})
            ipdv_v_ia = mets_ia.get('ipdv_voip', {})

            if ipdv_s_rr or ipdv_s_ia or ipdv_v_rr or ipdv_v_ia:
                # Tabla comparativa
                hosts_ipdv = sorted(set(
                    list(ipdv_s_rr.keys()) + list(ipdv_s_ia.keys()) +
                    list(ipdv_v_rr.keys()) + list(ipdv_v_ia.keys())
                ))
                ipdv_rows = []
                for h in hosts_ipdv:
                    ipdv_rows.append({
                        'Host': h,
                        'Streaming RR (ms)': f"{ipdv_s_rr.get(h, {}).get('jitter_mdev', 0):.2f}" if isinstance(ipdv_s_rr.get(h), dict) else 'N/A',
                        'Streaming IA (ms)': f"{ipdv_s_ia.get(h, {}).get('jitter_mdev', 0):.2f}" if isinstance(ipdv_s_ia.get(h), dict) else 'N/A',
                        'VoIP RR (ms)': f"{ipdv_v_rr.get(h, {}).get('jitter_mdev', 0):.2f}" if isinstance(ipdv_v_rr.get(h), dict) else 'N/A',
                        'VoIP IA (ms)': f"{ipdv_v_ia.get(h, {}).get('jitter_mdev', 0):.2f}" if isinstance(ipdv_v_ia.get(h), dict) else 'N/A',
                    })
                if ipdv_rows:
                    st.dataframe(pd.DataFrame(ipdv_rows), use_container_width=True, hide_index=True)

                # Histogramas
                jit_s_rr_vals = [v.get('jitter_mdev', 0) for v in ipdv_s_rr.values() if isinstance(v, dict)]
                jit_s_ia_vals = [v.get('jitter_mdev', 0) for v in ipdv_s_ia.values() if isinstance(v, dict)]
                jit_v_rr_vals = [v.get('jitter_mdev', 0) for v in ipdv_v_rr.values() if isinstance(v, dict)]
                jit_v_ia_vals = [v.get('jitter_mdev', 0) for v in ipdv_v_ia.values() if isinstance(v, dict)]

                jh1, jh2 = st.columns(2)
                with jh1:
                    all_rr = jit_s_rr_vals + jit_v_rr_vals
                    if all_rr: st.plotly_chart(crear_histograma(all_rr, "Jitter RR (Streaming+VoIP)", '#1E90FF'), use_container_width=True, key='hist_rr')
                    else: st.info('Sin datos de Jitter RR')
                with jh2:
                    all_ia = jit_s_ia_vals + jit_v_ia_vals
                    if all_ia: st.plotly_chart(crear_histograma(all_ia, "Jitter IA (Streaming+VoIP)", '#32CD32'), use_container_width=True, key='hist_ia')
                    else: st.info('Sin datos de Jitter IA')
            else:
                # Fallback: usar ipdv general
                ipdv_rr = mets_rr.get('ipdv', {})
                ipdv_ia = mets_ia.get('ipdv', {})
                jit_rr_vals = [v.get('jitter_mdev', 0) for v in ipdv_rr.values() if isinstance(v, dict)]
                jit_ia_vals = [v.get('jitter_mdev', 0) for v in ipdv_ia.values() if isinstance(v, dict)]
                jh1, jh2 = st.columns(2)
                with jh1:
                    if jit_rr_vals: st.plotly_chart(crear_histograma(jit_rr_vals, "Histograma Jitter RR", '#1E90FF'), use_container_width=True, key='hist_rr')
                    else: st.info('Sin datos de Jitter RR')
                with jh2:
                    if jit_ia_vals: st.plotly_chart(crear_histograma(jit_ia_vals, "Histograma Jitter IA", '#32CD32'), use_container_width=True, key='hist_ia')
                    else: st.info('Sin datos de Jitter IA')

            st.markdown("---")

            # ── RFC 2544 ──
            st.subheader("🚀 Estándar RFC 2544 (Benchmarking)")
            
            # Throughput
            st.markdown("#### 1. Throughput (Tasa Máxima Efectiva)")
            tp_rr_d = mets_rr.get('throughput', mets_rr.get('throughput_streaming', {}))
            tp_ia_d = mets_ia.get('throughput', mets_ia.get('throughput_streaming', {}))
            hosts_tp = sorted(set(list(tp_rr_d.keys()) + list(tp_ia_d.keys())))
            tp_data_rr = [tp_rr_d.get(h, 0) for h in hosts_tp]
            tp_data_ia = [tp_ia_d.get(h, 0) for h in hosts_tp]
            
            if hosts_tp:
                fig_tp = crear_grafico_barras(hosts_tp, {'Round Robin': tp_data_rr, 'IA LSTM': tp_data_ia}, 'Throughput por Servidor', 'Mbps', 300)
                st.plotly_chart(fig_tp, use_container_width=True, key='tp_chart')
            else:
                st.info("Sin datos de throughput para graficar.")

            # Back to Back / Recovery
            b2b1, b2b2 = st.columns(2)
            with b2b1:
                st.markdown("#### 2. Back-to-Back Frames (RFC 2544)")
                st.markdown("Capacidad de absorción de ráfagas UDP antes de la primera pérdida.")
                b2b_rr_data = mets_rr.get('back_to_back', {})
                b2b_ia_data = mets_ia.get('back_to_back', {})
                if b2b_rr_data or b2b_ia_data:
                    bursts = sorted(set(list(b2b_rr_data.keys()) + list(b2b_ia_data.keys())))
                    b2b_rows = []
                    for b in bursts:
                        rr_loss = b2b_rr_data.get(b, {}).get('loss_percent', 'N/A') if b2b_rr_data else 'N/A'
                        ia_loss = b2b_ia_data.get(b, {}).get('loss_percent', 'N/A') if b2b_ia_data else 'N/A'
                        b2b_rows.append({'Ráfaga': b, 'RR Pérdida': f"{rr_loss}%" if isinstance(rr_loss, (int, float)) else rr_loss,
                            'IA Pérdida': f"{ia_loss}%" if isinstance(ia_loss, (int, float)) else ia_loss})
                    st.dataframe(pd.DataFrame(b2b_rows), use_container_width=True, hide_index=True)
                else:
                    st.info("Sin datos de Back-to-Back para esta prueba")
            with b2b2:
                st.markdown("#### 3. System Recovery (Tiempo de Recuperación)")
                rec_rr_d = mets_rr.get('recovery', {})
                rec_ia_d = mets_ia.get('recovery', {})
                rec_rr = rec_rr_d.get('recovery_s', mets_rr.get('recovery_time_s', 0)) if isinstance(rec_rr_d, dict) else mets_rr.get('recovery_time_s', 0)
                rec_ia = rec_ia_d.get('recovery_s', mets_ia.get('recovery_time_s', 0)) if isinstance(rec_ia_d, dict) else mets_ia.get('recovery_time_s', 0)
                rec_rr_ms = rec_rr * 1000 if rec_rr else 0
                rec_ia_ms = rec_ia * 1000 if rec_ia else 0
                st.metric("Cronómetro Estabilización RR", f"{rec_rr_ms:.0f} ms" if rec_rr_ms else "N/A")
                st.metric("Cronómetro Estabilización IA", f"{rec_ia_ms:.0f} ms" if rec_ia_ms else "N/A")

            st.markdown("---")

            # ── SECCIÓN 3: Topologías y Tablas de Decisiones ──
            st.subheader("🕸️ Topología y Tablas de Decisiones")
            topo1, topo2 = st.columns(2)
            with topo1:
                st.markdown("#### 🔄 Round Robin")
                if res_rr and 'metricas' in res_rr:
                    eq_vals = mets_rr.get('equidad_cpu', {}).get('valores', [25]*4)
                    if eq_vals:
                        max_idx = eq_vals.index(max(eq_vals))
                        chosen_rr = f"srv{max_idx + 1}"
                    else:
                        chosen_rr = "srv1"
                    render_topology(chosen_rr, "Clientes", "Activo")
                else:
                    st.info("Sin datos de topología RR")
            with topo2:
                st.markdown("#### 🧠 IA (LSTM)")
                if res_ia and 'metricas' in res_ia:
                    eq_vals_ia = mets_ia.get('equidad_cpu', {}).get('valores', [0]*4)
                    if eq_vals_ia and any(v > 0 for v in eq_vals_ia):
                        min_idx = eq_vals_ia.index(min(eq_vals_ia))
                        chosen_ia = f"srv{min_idx + 1}"
                    else:
                        chosen_ia = "srv1"
                    render_topology(chosen_ia, "Clientes", "Activo")
                else:
                    st.info("Sin datos de topología IA")

            st.markdown("---")
            
            # ── OVERHEAD DEL CONTROLADOR ──
            st.subheader("🧠 Overhead del Controlador (Consumo de Recursos)")
            st.markdown("Comparativa del impacto en recursos computacionales del sistema operativo entre ambos algoritmos.")
            
            c_rr = res_rr.get('controlador_stats', {}) if res_rr else {}
            c_ia = res_ia.get('controlador_stats', {}) if res_ia else {}
            
            c_col1, c_col2, c_col3, c_col4 = st.columns(4)
            c_col1.metric("CPU Avg RR", f"{c_rr.get('cpu_avg', 0):.2f}%")
            c_col1.metric("CPU Avg IA", f"{c_ia.get('cpu_avg', 0):.2f}%", 
                         f"{c_ia.get('cpu_avg', 0) - c_rr.get('cpu_avg', 0):.2f}%", delta_color="inverse")
            
            c_col2.metric("CPU Pico RR", f"{c_rr.get('cpu_max', 0):.2f}%")
            c_col2.metric("CPU Pico IA", f"{c_ia.get('cpu_max', 0):.2f}%",
                         f"{c_ia.get('cpu_max', 0) - c_rr.get('cpu_max', 0):.2f}%", delta_color="inverse")
            
            c_col3.metric("RAM Avg RR", f"{c_rr.get('ram_avg', 0):.2f}%")
            c_col3.metric("RAM Avg IA", f"{c_ia.get('ram_avg', 0):.2f}%",
                         f"{c_ia.get('ram_avg', 0) - c_rr.get('ram_avg', 0):.2f}%", delta_color="inverse")
            
            c_col4.metric("Decisiones RR", res_rr.get('response_time_total_decisions', 0) if res_rr else 0)
            c_col4.metric("Decisiones IA", res_ia.get('response_time_total_decisions', 0) if res_ia else 0,
                         (res_ia.get('response_time_total_decisions', 0) if res_ia else 0) - 
                         (res_rr.get('response_time_total_decisions', 0) if res_rr else 0), delta_color="off")

            st.markdown("---")
            dec_col1, dec_col2 = st.columns(2)
            with dec_col1:
                st.markdown("#### 🔄 Decisiones Round Robin")
                if res_rr:
                    render_decision_table(res_rr, "Round Robin", key_suffix='comp_rr')
            with dec_col2:
                st.markdown("#### 🧠 Decisiones IA (LSTM)")
                if res_ia:
                    render_decision_table(res_ia, "IA (LSTM)", key_suffix='comp_ia')


            # ── SECCIÓN P10: Métricas temporales (Resiliencia) ──
            if res_rr and res_ia:
                mets_rr_t = res_rr.get('metricas', {})
                mets_ia_t = res_ia.get('metricas', {})
                lat_rr_t = mets_rr_t.get('latencia_temporal', [])
                lat_ia_t = mets_ia_t.get('latencia_temporal', [])
                if lat_rr_t or lat_ia_t:
                    st.markdown("---")
                    st.subheader("📈 Métricas Temporales (P10 Resiliencia)")
                    st.markdown("#### ⏱️ Latencia en el Tiempo")
                    fig_lat_comp = go.Figure()
                    if lat_rr_t:
                        times_rr = [s.get('tiempo_s', 0) for s in lat_rr_t]
                        vals_rr = [s.get('latencia_avg', 0) if not isinstance(s.get('latencia_avg', 0), dict) else s.get('latencia_avg', {}).get('avg', 0) for s in lat_rr_t]
                        fig_lat_comp.add_trace(go.Bar(x=times_rr, y=vals_rr, name='Round Robin', marker_color='#1E90FF'))
                    if lat_ia_t:
                        times_ia = [s.get('tiempo_s', 0) for s in lat_ia_t]
                        vals_ia = [s.get('latencia_avg', 0) if not isinstance(s.get('latencia_avg', 0), dict) else s.get('latencia_avg', {}).get('avg', 0) for s in lat_ia_t]
                        fig_lat_comp.add_trace(go.Bar(x=times_ia, y=vals_ia, name='IA (LSTM)', marker_color='#32CD32'))
                    fig_lat_comp.update_layout(title='Latencia Comparativa en el Tiempo', barmode='group', xaxis_title='Tiempo (s)', xaxis=dict(type='category'), yaxis_title='ms', height=350,
                        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1))
                    fig_lat_comp.update_yaxes(gridcolor='rgba(128,128,128,0.2)')
                    st.plotly_chart(fig_lat_comp, use_container_width=True, key='chart_comp_lat_temporal')

                eq_rr_t = mets_rr_t.get('equidad_temporal', [])
                eq_ia_t = mets_ia_t.get('equidad_temporal', [])
                if eq_rr_t or eq_ia_t:
                    st.markdown("#### ⚖️ Equidad CPU en el Tiempo")
                    fig_eq_comp = go.Figure()
                    if eq_rr_t:
                        t_rr = [s.get('tiempo', 0) for s in eq_rr_t]
                        std_rr = [s.get('cpu_std', 0) for s in eq_rr_t]
                        fig_eq_comp.add_trace(go.Bar(x=t_rr, y=std_rr, name='RR CPU StdDev', marker_color='#1E90FF'))
                    if eq_ia_t:
                        t_ia = [s.get('tiempo', 0) for s in eq_ia_t]
                        std_ia = [s.get('cpu_std', 0) for s in eq_ia_t]
                        fig_eq_comp.add_trace(go.Bar(x=t_ia, y=std_ia, name='IA CPU StdDev', marker_color='#32CD32'))
                    fig_eq_comp.update_layout(title='Desviación Estándar CPU Comparativa (Menor = Mejor)', barmode='group', xaxis_title='Tiempo (s)', xaxis=dict(type='category'), yaxis_title='StdDev (%)', height=350,
                        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1))
                    fig_eq_comp.update_yaxes(gridcolor='rgba(128,128,128,0.2)')
                    st.plotly_chart(fig_eq_comp, use_container_width=True, key='chart_comp_eq_temporal')

    else:
        # === MODO EN VIVO: Comparativa lado a lado ===
        # === MODO EN VIVO: Comparativa lado a lado ===
        st.subheader("🔴 Comparativa En Vivo")
        data = load_data()
        ctrl = get_controller_stats()

        if data and 'ultimo_evento' in data:
            evt = data['ultimo_evento']
            mets = evt.get('metricas', {})

            # Estado del controlador activo
            st.markdown("##### 🖥️ Controlador Activo")
            cm1, cm2, cm3, cm4 = st.columns(4)
            cpu_st = "🟢" if ctrl['cpu'] < 50 else ("🟡" if ctrl['cpu'] < 80 else "🔴")
            ram_st = "🟢" if ctrl['ram'] < 50 else ("🟡" if ctrl['ram'] < 80 else "🔴")
            cm1.metric("CPU", f"{ctrl['cpu']:.1f}%", delta=cpu_st, delta_color="off")
            cm2.metric("RAM", f"{ctrl['ram']:.1f}%", delta=ram_st, delta_color="off")
            cm3.metric("Servidor Elegido", evt.get('servidor_elegido', '').upper())
            etapa = "BAJO 🟢"
            if mets.get('bw_solicitado', 0) > 20: etapa = "ALTO 🔴"
            elif mets.get('bw_solicitado', 0) > 10: etapa = "MEDIO 🟡"
            cm4.metric("Tráfico", etapa)

            st.markdown("---")

            # Topología y gráficos
            col1, col2 = st.columns([1, 1])
            with col1:
                st.markdown("##### 🕸️ Topología en Tiempo Real")
                render_topology(evt.get('servidor_elegido', ''), evt.get('cliente', ''), "Activo")
            with col2:
                st.markdown("##### 📊 CPU y RAM de Servidores")
                render_server_charts(mets, key_prefix='comp_live')

            st.markdown("---")
            nc1, nc2, nc3 = st.columns(3)
            nc1.metric("Ancho de Banda", f"{mets.get('bw_solicitado',0):.1f} Mbps")
            nc2.metric("Jitter", f"{mets.get('jitter',0):.1f} ms")
            nc3.metric("Pérdida", f"{mets.get('loss', 0)}%")

            # Tablas de historial lado a lado
            st.markdown("---")
            st.subheader("📜 Historiales de Decisiones")
            hist_col1, hist_col2 = st.columns(2)
            with hist_col1:
                h_rr = read_log_events(LOG_FILE, 'history_rr_comp', mode_filter='RR')
                st.markdown(f"**🔄 Round Robin** ({len(h_rr)} eventos)")
                if h_rr:
                    st.dataframe(pd.DataFrame(h_rr), use_container_width=True, height=350, hide_index=True)
                else:
                    st.info("Sin eventos RR")
            with hist_col2:
                h_ia = read_log_events(LOG_FILE, 'history_ia_comp', mode_filter='IA')
                st.markdown(f"**🧠 IA (LSTM)** ({len(h_ia)} eventos)")
                if h_ia:
                    st.dataframe(pd.DataFrame(h_ia), use_container_width=True, height=350, hide_index=True)
                else:
                    st.info("Sin eventos IA")
        else:
            st.warning("⏳ Esperando datos del controlador RYU...")

# ─────────────────────────────────────────────
# TAB 4: REPORTES
# ─────────────────────────────────────────────
with tab_reports:
    render_reports_tab()

# ═══════════════════════════════════════════════
# SIDEBAR: Controles adicionales
# ═══════════════════════════════════════════════
st.sidebar.markdown("---")
if st.sidebar.button("🗑️ Limpiar Todos los Historiales"):
    for key in list(st.session_state.keys()):
        if 'history' in key or 'lines' in key:
            del st.session_state[key]
    for lf in [LOG_FILE, LOG_FILE_RR, LOG_FILE_IA]:
        if os.path.exists(lf):
            open(lf, 'w').close()
    st.rerun()

# Auto-rerun para modo en vivo
if prueba_sel == 0:
    time.sleep(0.5)
    st.rerun()

import numpy as np # Importar NumPy para operaciones numéricas y conversión de tipos
import json # Importar json para serializar datos al formato JSON (para el dashboard)
import time # Importar time para obtener marcas de tiempo Unix
import random # Importar random para generar métricas simuladas aleatorias
import os # Importar os para interacciones con el sistema operativo
from ryu.base import app_manager # Importar app_manager de Ryu, la clase base para crear aplicaciones del controlador Ryu
from ryu.controller import ofp_event # Importar ofp_event para manejar eventos del protocolo OpenFlow
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls # Importar los decoradores para registrar handlers en fases CONFIG y MAIN del protocolo
from ryu.ofproto import ofproto_v1_3 # Importar la definición del protocolo OpenFlow versión 1.3
from ryu.lib.packet import packet, ethernet, arp, ipv4, tcp, udp, ether_types # Importar clases para parsear protocolos de red: Ethernet, ARP, IPv4, TCP, UDP

# Definición de la clase del controlador SDN con balanceo Round Robin
class GNS3RoundRobinLoadBalancer(app_manager.RyuApp):
    # Especificar que esta aplicación usa OpenFlow versión 1.3
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    # Constructor del controlador: inicializa el estado de Round Robin, VIPs y servidores
    def __init__(self, *args, **kwargs):
        # Llamar al constructor de la clase padre RyuApp
        super(GNS3RoundRobinLoadBalancer, self).__init__(*args, **kwargs)
        # Registrar mensaje de inicio del controlador Round Robin en el log
        self.logger.info(">>> [INIT] Iniciando Controlador GNS3 (Round Robin)...")
        
        # Inicializar el contador de Round Robin en 0 (para rotar entre servidores)
        self.rr_counter = 0

        # Ruta del archivo JSON donde se exporta el estado actual para el dashboard
        self.DASHBOARD_FILE = 'estado_red.json'
        # Marca de tiempo de la última escritura al dashboard
        self.last_write = 0
        
        # Diccionario para sesiones sticky: mapea (IP_cliente, servicio) -> servidor asignado
        self.sticky_sessions = {}
        self.mac_to_port = {}

        # Definición de las IPs Virtuales (VIPs) para cada servicio con sus MACs virtuales
        self.SERVICES = {
            # VIP del servicio WEB en el puerto 80 con su MAC virtual
            '10.0.0.100': {'name': 'WEB',       'mac': '00:00:00:00:FE:80', 'port': 80},
            # VIP del servicio STREAMING en el puerto 8080 con su MAC virtual
            '10.0.0.101': {'name': 'STREAMING', 'mac': '00:00:00:00:FE:81', 'port': 8080},
            # VIP del servicio DATABASE en el puerto 3306 con su MAC virtual
            '10.0.0.200': {'name': 'DATABASE',  'mac': '00:00:00:00:FE:33', 'port': 3306},
            # VIP del servicio VOIP en el puerto 5060 con su MAC virtual
            '10.0.0.201': {'name': 'VOIP',      'mac': '00:00:00:00:FE:50', 'port': 5060}
        }
        
        # Definición de los 4 servidores reales con sus IPs y MACs
        self.servers = {
            # Servidor 1 con su IP y dirección MAC
            'srv1': {'ip': '10.0.0.1', 'mac': '00:00:00:00:00:01'},
            # Servidor 2 con su IP y dirección MAC
            'srv2': {'ip': '10.0.0.2', 'mac': '00:00:00:00:00:02'},
            # Servidor 3 con su IP y dirección MAC
            'srv3': {'ip': '10.0.0.3', 'mac': '00:00:00:00:00:03'},
            # Servidor 4 con su IP y dirección MAC
            'srv4': {'ip': '10.0.0.4', 'mac': '00:00:00:00:00:04'} 
        }

    # Método que selecciona el próximo servidor usando el algoritmo Round Robin
    def get_round_robin_server(self):
        # Obtener la lista ordenada de claves de servidores: ['srv1', 'srv2', 'srv3', 'srv4']
        server_keys = list(self.servers.keys()) # ['srv1', 'srv2', 'srv3', 'srv4']
        # Seleccionar el servidor usando el módulo del contador para rotar circularmente
        chosen = server_keys[self.rr_counter % len(server_keys)]
        # Incrementar el contador para que la próxima vez se elija el siguiente servidor
        self.rr_counter += 1
        # Retornar la clave del servidor elegido (ej: 'srv2')
        return chosen

    # Método que genera métricas simuladas con distribución Gaussiana y semilla determinista (seed=42)
    def _get_live_metrics(self):
        import random
        # Inicializar el generador con semilla fija para asegurar sincronización con RR/IA
        if not hasattr(self, 'rng'):
            self.rng = random.Random(42)
            
        # Crear diccionario con métricas de red simuladas usando Gaussiana
        m = {'bw_solicitado': max(0.0, self.rng.gauss(20, 10)), 'jitter': max(0.0, self.rng.gauss(2, 1)), 'loss':0}
        # Iterar del 1 al 4 para generar métricas de CPU y RAM de cada servidor
        for i in range(1, 5): # srv1 a srv4
            # Generar un valor Gaussiano de CPU (media 50, std 15) limitado entre 0 y 100
            m[f'srv{i}_cpu'] = max(0.0, min(100.0, self.rng.gauss(50, 15)))
            # Generar un valor Gaussiano de RAM (media 40, std 10) limitado entre 0 y 100
            m[f'srv{i}_ram'] = max(0.0, min(100.0, self.rng.gauss(40, 10)))
            
        import os
        if os.path.exists('force_crash.txt'):
            m['srv4_cpu'] = 100.0
            m['srv4_ram'] = 100.0
            
        return m

    # Método que exporta el estado actual de la red al archivo JSON para el dashboard
    def export_dashboard(self, src, svc, chosen, mets):
        # Bloque try para manejar errores de escritura en disco
        try:
            # Limpiar las métricas: convertir valores numpy float32 a float nativo de Python
            clean_mets = {k: float(v) if isinstance(v, (np.float32, float)) else v for k,v in mets.items()}
            # Crear el diccionario del evento con cliente, servicio, servidor elegido y métricas
            evento = {'cliente': src, 'servicio': svc, 'servidor_elegido': chosen, 'metricas': clean_mets, 'modo': 'RR'}
            # Crear el diccionario de datos completo con timestamp, modo y el último evento
            data = {
                'timestamp': time.time(),
                'modo': 'RR',
                'ultimo_evento': evento
            }
            # Escribir el estado actual en el archivo JSON del dashboard (sobreescribe)
            with open(self.DASHBOARD_FILE, 'w') as f: json.dump(data, f)
            # Crear una línea de log con timestamp y evento para el archivo de log append-only
            log_entry = json.dumps({'t': time.time(), 'e': evento})
            # Agregar la línea al archivo de log sin sobreescribir (modo append)
            with open('estado_red_log.json', 'a') as f: f.write(log_entry + '\n')
            # Actualizar la marca de tiempo de la última escritura
            self.last_write = time.time()
        # Ignorar cualquier error de escritura silenciosamente
        except: pass

    # Handler que se ejecuta cuando un switch se conecta al controlador (fase CONFIG)
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        # Obtener el datapath (representación del switch) del evento
        datapath = ev.msg.datapath
        # Obtener las constantes del protocolo OpenFlow
        ofproto = datapath.ofproto
        # Obtener el parser para construir mensajes OpenFlow
        parser = datapath.ofproto_parser
        # Crear un match vacío que coincide con TODOS los paquetes (regla catch-all)
        match = parser.OFPMatch()
        # Definir la acción: enviar el paquete al controlador sin buffer
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        # Instalar esta regla con prioridad 0 (la más baja) como table-miss entry
        self.add_flow(datapath, 0, match, actions)

    # Método auxiliar para instalar una regla de flujo en un switch OpenFlow
    def add_flow(self, datapath, priority, match, actions, idle_timeout=0, hard_timeout=0):
        # Obtener las constantes del protocolo OpenFlow
        ofproto = datapath.ofproto
        # Obtener el parser para construir mensajes OpenFlow
        parser = datapath.ofproto_parser
        # Crear una instrucción que aplica las acciones especificadas
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        # Crear el mensaje FlowMod para instalar la regla en el switch
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, instructions=inst, idle_timeout=idle_timeout, hard_timeout=hard_timeout)
        # Enviar el mensaje FlowMod al switch para instalar la regla
        datapath.send_msg(mod)

    # Handler principal que se ejecuta cada vez que un paquete llega al controlador (PacketIn)
    def _get_out_port(self, datapath, dst_mac):
        dpid = datapath.id
        port = self.mac_to_port.get(dpid, {}).get(dst_mac)
        if port is not None:
            return port
        
        # Fallback: if dst_mac is a server, use any VIP's path (since they are all behind the same logical path)
        is_server = False
        for s_data in self.servers.values():
            if dst_mac == s_data['mac']:
                is_server = True
                break
                
        if is_server:
            for svc in self.SERVICES.values():
                vmac = svc['mac']
                port = self.mac_to_port.get(dpid, {}).get(vmac)
                if port is not None:
                    return port
                    
        return datapath.ofproto.OFPP_FLOOD

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        # Obtener el mensaje OpenFlow del evento
        msg = ev.msg
        # Obtener el datapath (switch) que envió el paquete
        datapath = msg.datapath
        # Obtener el puerto de entrada por donde llegó el paquete al switch
        in_port = msg.match['in_port']
        # Parsear los datos binarios del paquete para extraer los protocolos
        pkt = packet.Packet(msg.data)
        # Extraer la cabecera Ethernet del paquete
        eth = pkt.get_protocol(ethernet.ethernet)
        
        # Ignorar paquetes IPv6 ya que no son relevantes para este balanceador
        if eth.ethertype == ether_types.ETH_TYPE_IPV6: return

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][eth.src] = in_port

        # SECCIÓN 1: Manejo de paquetes ARP (resolución de direcciones)
        # Intentar extraer el protocolo ARP del paquete
        arp_pkt = pkt.get_protocol(arp.arp)
        # Si es un paquete ARP y la IP destino es una de nuestras VIPs
        if arp_pkt and arp_pkt.dst_ip in self.SERVICES:
            # Obtener la información del servicio correspondiente a la VIP
            svc = self.SERVICES[arp_pkt.dst_ip]
            # Enviar una respuesta ARP con la MAC virtual del servicio
            self._handle_arp_reply(datapath, in_port, arp_pkt, svc['mac'])
            # Terminar el procesamiento de este paquete
            return

        # SECCIÓN 2: Manejo de paquetes IP (balanceo de carga)
        # Intentar extraer el protocolo IPv4 del paquete
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        # Si el paquete contiene una cabecera IPv4
        if ip_pkt:
            # Caso IDA: el paquete va del Cliente hacia una VIP
            if ip_pkt.dst in self.SERVICES:
                # Obtener la información del servicio destino
                svc = self.SERVICES[ip_pkt.dst]
                # Ejecutar el balanceo de carga Round Robin para este paquete
                self._balancear(datapath, msg, pkt, ip_pkt, in_port, svc)
                # Terminar el procesamiento
                return
            
            # Caso VUELTA: el paquete va del Servidor hacia el Cliente (requiere Reverse NAT)
            # Iterar sobre todos los servidores para ver si el origen coincide
            for s_name, s_data in self.servers.items():
                # Si la IP origen del paquete es la de uno de nuestros servidores
                if ip_pkt.src == s_data['ip']:
                    # Intentar extraer el protocolo TCP del paquete
                    tcp_pkt = pkt.get_protocol(tcp.tcp)
                    # Intentar extraer el protocolo UDP del paquete
                    udp_pkt = pkt.get_protocol(udp.udp)
                    # Inicializar el puerto origen en 0
                    sport = 0
                    # Si es TCP, obtener el puerto origen TCP
                    if tcp_pkt: sport = tcp_pkt.src_port
                    # Si es UDP, obtener el puerto origen UDP
                    elif udp_pkt: sport = udp_pkt.src_port
                    # Si no es TCP ni UDP (ej: ICMP), usar 80 como puerto por defecto
                    else: sport = 80 # Default ICMP/Web
                    
                    # Buscar qué VIP corresponde al puerto origen del servidor
                    for vip, info in self.SERVICES.items():
                        # Si el puerto del servicio coincide con el puerto origen (o es 80)
                        if info['port'] == sport or sport == 80: # Simplificación
                             # Aplicar Reverse NAT: cambiar la IP origen del servidor por la VIP
                             self._reverse_nat(datapath, msg, in_port, vip, info['mac'])
                             # Terminar el procesamiento
                             return
        # Si el paquete no fue manejado por ninguna regla anterior, hacer flood
        out_port = self._get_out_port(datapath, eth.dst)
        actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
        if out_port != datapath.ofproto.OFPP_FLOOD:
            match = datapath.ofproto_parser.OFPMatch(in_port=in_port, eth_dst=eth.dst, eth_src=eth.src)
            self.add_flow(datapath, 1, match, actions, idle_timeout=10)
        out = datapath.ofproto_parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port, actions=actions, data=msg.data)
        datapath.send_msg(out)

    # Método que construye y envía una respuesta ARP con una MAC virtual
    def _handle_arp_reply(self, datapath, port, arp_pkt, vmac):
        # Crear un nuevo paquete vacío para construir la respuesta
        pkt = packet.Packet()
        # Agregar la cabecera Ethernet con la MAC virtual como origen y tipo ARP
        pkt.add_protocol(ethernet.ethernet(ethertype=ether_types.ETH_TYPE_ARP, dst=arp_pkt.src_mac, src=vmac))
        # Agregar el protocolo ARP como respuesta (ARP_REPLY) con las MACs e IPs correspondientes
        pkt.add_protocol(arp.arp(opcode=arp.ARP_REPLY, src_mac=vmac, src_ip=arp_pkt.dst_ip, dst_mac=arp_pkt.src_mac, dst_ip=arp_pkt.src_ip))
        # Enviar el paquete de respuesta ARP de vuelta al puerto de entrada
        self._send_packet(datapath, port, pkt)

    # Método que realiza el balanceo Round Robin: asigna servidores en orden circular
    def _balancear(self, datapath, msg, pkt, ip_pkt, in_port, svc):
        # Crear la clave de sesión usando la IP del cliente y el nombre del servicio
        session_key = (ip_pkt.src, svc['name'])
        
        # Verificar si ya existe una sesión sticky para esta combinación cliente+servicio
        # NOTA: En Round Robin TAMBIÉN se necesitan sticky sessions para mantener conexiones TCP
        # Si no, cada paquete iría a un servidor diferente y rompería la conexión
        if session_key in self.sticky_sessions:
            # Reusar el servidor previamente asignado a esta sesión
            chosen = self.sticky_sessions[session_key]
        # Si no existe sesión previa, es una nueva conexión
        else:
            # Obtener métricas simuladas (solo se usan para mostrar en el dashboard)
            metrics = self._get_live_metrics() # Solo para el dashboard
            # Seleccionar el próximo servidor usando el algoritmo Round Robin
            chosen = self.get_round_robin_server()
            # Guardar la asignación en la tabla de sesiones sticky
            self.sticky_sessions[session_key] = chosen
            # Imprimir la decisión de Round Robin para esta nueva sesión
            print(f"--> [{svc['name']}] -> RoundRobin eligió {chosen} (Nueva Sesión: {ip_pkt.src})")
            # Exportar la decisión al dashboard para visualización
            self.export_dashboard(ip_pkt.src, svc['name'], chosen, metrics)

        # Obtener los datos (IP y MAC) del servidor elegido
        srv_data = self.servers[chosen]
        
        # Obtener el parser de OpenFlow para construir las acciones
        parser = datapath.ofproto_parser
        # Definir las acciones para modificar el paquete y reenviarlo
        out_port = self._get_out_port(datapath, srv_data['mac'])
        actions = [
            parser.OFPActionSetField(eth_dst=srv_data['mac']),
            parser.OFPActionSetField(ipv4_dst=srv_data['ip']),
            parser.OFPActionOutput(out_port)
        ]
        # Instalar flujo para evitar saturar el controlador
        tcp_pkt = pkt.get_protocol(tcp.tcp)
        udp_pkt = pkt.get_protocol(udp.udp)
        if out_port != datapath.ofproto.OFPP_FLOOD:
            if tcp_pkt:
                m = parser.OFPMatch(eth_type=0x0800, ip_proto=6, ipv4_src=ip_pkt.src, ipv4_dst=ip_pkt.dst, tcp_src=tcp_pkt.src_port, tcp_dst=tcp_pkt.dst_port)
                self.add_flow(datapath, 10, m, actions, idle_timeout=10)
            elif udp_pkt:
                m = parser.OFPMatch(eth_type=0x0800, ip_proto=17, ipv4_src=ip_pkt.src, ipv4_dst=ip_pkt.dst, udp_src=udp_pkt.src_port, udp_dst=udp_pkt.dst_port)
                self.add_flow(datapath, 10, m, actions, idle_timeout=10)
            else:
                m = parser.OFPMatch(eth_type=0x0800, ipv4_src=ip_pkt.src, ipv4_dst=ip_pkt.dst)
                self.add_flow(datapath, 10, m, actions, idle_timeout=10)

        # Crear el mensaje PacketOut con las acciones de NAT y reenvío
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port, actions=actions, data=msg.data)
        # Enviar el paquete modificado al switch
        datapath.send_msg(out)

    # Método que aplica Reverse NAT: cambia la IP del servidor por la VIP en las respuestas
    def _reverse_nat(self, datapath, msg, in_port, vip, vmac):
        # Obtener el parser de OpenFlow para construir las acciones
        parser = datapath.ofproto_parser
        # Definir las acciones para el Reverse NAT
        eth_in = packet.Packet(msg.data).get_protocols(ethernet.ethernet)[0]
        out_port = self._get_out_port(datapath, eth_in.dst)
        actions = [
            parser.OFPActionSetField(eth_src=vmac),
            parser.OFPActionSetField(ipv4_src=vip),
            parser.OFPActionOutput(out_port)
        ]
        # Instalar flujo inverso
        pkt = packet.Packet(msg.data)
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        if ip_pkt:
            tcp_pkt = pkt.get_protocol(tcp.tcp)
            udp_pkt = pkt.get_protocol(udp.udp)
            if out_port != datapath.ofproto.OFPP_FLOOD:
                if tcp_pkt:
                    m = parser.OFPMatch(eth_type=0x0800, ip_proto=6, ipv4_src=ip_pkt.src, ipv4_dst=ip_pkt.dst, tcp_src=tcp_pkt.src_port, tcp_dst=tcp_pkt.dst_port)
                    self.add_flow(datapath, 10, m, actions, idle_timeout=10)
                elif udp_pkt:
                    m = parser.OFPMatch(eth_type=0x0800, ip_proto=17, ipv4_src=ip_pkt.src, ipv4_dst=ip_pkt.dst, udp_src=udp_pkt.src_port, udp_dst=udp_pkt.dst_port)
                    self.add_flow(datapath, 10, m, actions, idle_timeout=10)
                else:
                    m = parser.OFPMatch(eth_type=0x0800, ipv4_src=ip_pkt.src, ipv4_dst=ip_pkt.dst)
                    self.add_flow(datapath, 10, m, actions, idle_timeout=10)

        # Crear el mensaje PacketOut con las acciones de Reverse NAT
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port, actions=actions, data=msg.data)
        # Enviar el paquete modificado al switch
        datapath.send_msg(out)

    # Método auxiliar para serializar y enviar un paquete construido programáticamente
    def _send_packet(self, datapath, port, pkt):
        # Serializar el paquete (convertir los protocolos agregados a bytes binarios)
        pkt.serialize()
        # Crear un PacketOut con el paquete serializado, indicando que viene del controlador
        out = datapath.ofproto_parser.OFPPacketOut(datapath=datapath, buffer_id=datapath.ofproto.OFP_NO_BUFFER, in_port=datapath.ofproto.OFPP_CONTROLLER, actions=[datapath.ofproto_parser.OFPActionOutput(port)], data=pkt.data)
        # Enviar el paquete al switch para que lo reenvíe por el puerto especificado
        datapath.send_msg(out)

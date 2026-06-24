from mininet.net import Mininet # Importar la clase Mininet para crear y gestionar la red virtual
# Importar RemoteController para conectar con un controlador SDN externo (Ryu)
from mininet.node import RemoteController, OVSKernelSwitch # Importar OVSKernelSwitch para usar switches Open vSwitch en modo kernel
from mininet.cli import CLI # Importar CLI para abrir la consola interactiva de Mininet
from mininet.log import setLogLevel # Importar setLogLevel para configurar el nivel de detalle de los logs de Mininet
import os # Importar os para interactuar con el sistema operativo (crear directorios, etc.)

# Función para iniciar un servicio simulado (HTTP) en un host de Mininet
def start_service(host, name, port, proto='TCP'):
    """Simula un servicio escuchando en un puerto (HTTP Compatible)"""
    # Crear la ruta del directorio temporal para este servicio específico
    svc_dir = f"/tmp/{host.name}_{name}_{port}"
    # Crear el directorio temporal en el host (con -p para crear padres si no existen)
    host.cmd(f"mkdir -p {svc_dir}")
    
    # Crear el mensaje HTML que el servicio responderá a los clientes
    msg = f"<h1>Respuesta de {name} desde el SERVIDOR {host.name}</h1>"
    # Escribir el mensaje HTML en un archivo index.html dentro del directorio del servicio
    host.cmd(f"echo '{msg}' > {svc_dir}/index.html")

    # Verificar si el protocolo es TCP (el único implementado actualmente)
    if proto == 'TCP':
        # Construir el comando para iniciar un servidor HTTP en Python en segundo plano
        # Redirige stdout y stderr al log y el '&' final lo ejecuta en background
        cmd = f"cd {svc_dir} && python3 -m http.server {port} > {svc_dir}/http.log 2>&1 &"
        # Ejecutar el comando en el host de Mininet para iniciar el servicio
        host.cmd(cmd)

# Función para iniciar un servicio web (puerto 80) en un host
def start_web(host):
    # Crear la ruta del directorio temporal para el servicio web
    web_dir = f"/tmp/web_{host.name}"
    # Crear el directorio temporal para el servicio web
    host.cmd(f"mkdir -p {web_dir}")
    # Construir un comando compuesto: crear directorio, crear página HTML y levantar servidor HTTP
    # Todo se ejecuta en background con '&' al final
    cmd = (f"cd {web_dir} && "
           f"echo '<h1>Hola desde {host.name} (WEB)</h1>' > index.html && "
           f"python3 -m http.server 80 > {web_dir}/http.log 2>&1 &")
    # Ejecutar el comando compuesto en el host de Mininet
    host.cmd(cmd)

# Función principal que crea y ejecuta toda la topología de red
def run():
    # Crear la instancia de Mininet con controlador remoto y switches OVS en modo kernel
    net = Mininet(controller=RemoteController, switch=OVSKernelSwitch)
    
    # Imprimir mensaje indicando la creación de la topología
    print(">>> Creando Topología GNS3 (4 Servicios)...")
    # Agregar el controlador remoto c0 conectado a localhost (127.0.0.1) en el puerto 6633
    c0 = net.addController('c0', ip='127.0.0.1', port=6633)
    
    # Agregar el switch s1 con protocolo OpenFlow 1.3 (conecta a los servidores)
    s1 = net.addSwitch('s1', protocols='OpenFlow13') # Servidores
    # Agregar el switch s3 con protocolo OpenFlow 1.3 (switch central/core)
    s3 = net.addSwitch('s3', protocols='OpenFlow13') # Core
    # Agregar el switch s4 con protocolo OpenFlow 1.3 (conecta a los clientes)
    s4 = net.addSwitch('s4', protocols='OpenFlow13') # Clientes

    # Agregar el servidor 1 con IP 10.0.0.1 y dirección MAC específica
    srv1 = net.addHost('srv1', ip='10.0.0.1', mac='00:00:00:00:00:01')
    # Agregar el servidor 2 con IP 10.0.0.2 y dirección MAC específica
    srv2 = net.addHost('srv2', ip='10.0.0.2', mac='00:00:00:00:00:02')
    # Agregar el servidor 3 con IP 10.0.0.3 y dirección MAC específica
    srv3 = net.addHost('srv3', ip='10.0.0.3', mac='00:00:00:00:00:03')
    # Agregar el servidor 4 con IP 10.0.0.4 y dirección MAC específica
    srv4 = net.addHost('srv4', ip='10.0.0.4', mac='00:00:00:00:00:04')

    # Agregar el cliente 1 con IP 10.0.0.11
    cli1 = net.addHost('cli1', ip='10.0.0.11')
    # Agregar el cliente 2 con IP 10.0.0.12
    cli2 = net.addHost('cli2', ip='10.0.0.12')
    # Agregar el cliente 3 con IP 10.0.0.13
    cli3 = net.addHost('cli3', ip='10.0.0.13')
    # Agregar el cliente 4 con IP 10.0.0.14
    cli4 = net.addHost('cli4', ip='10.0.0.14')
    # Agregar el cliente 5 con IP 10.0.0.15
    cli5 = net.addHost('cli5', ip='10.0.0.15')
    # Agregar el cliente 6 con IP 10.0.0.16
    cli6 = net.addHost('cli6', ip='10.0.0.16')
    # Agregar el cliente 7 con IP 10.0.0.17
    cli7 = net.addHost('cli7', ip='10.0.0.17')
    cli8 = net.addHost('cli8', ip='10.0.0.18')
    cli9 = net.addHost('cli9', ip='10.0.0.19')
    cli10 = net.addHost('cli10', ip='10.0.0.20')
    cli11 = net.addHost('cli11', ip='10.0.0.21')
    cli12 = net.addHost('cli12', ip='10.0.0.22')

    # Crear enlaces entre cada servidor y el switch s1 (switch de servidores)
    for h in [srv1, srv2, srv3, srv4]:
        # Agregar un enlace de red entre el switch s1 y cada servidor
        net.addLink(s1, h)
        
    # Crear enlaces entre cada cliente y el switch s4 (switch de clientes)
    for h in [cli1, cli2, cli3, cli4, cli5, cli6, cli7, cli8, cli9, cli10, cli11, cli12]:
        # Agregar un enlace de red entre el switch s4 y cada cliente
        net.addLink(s4, h)
        
    # Crear enlace troncal entre el switch de servidores (s1) y el switch core (s3)
    net.addLink(s1, s3)
    # Crear enlace troncal entre el switch de clientes (s4) y el switch core (s3)
    net.addLink(s4, s3)

    # Iniciar toda la red Mininet (activa switches, hosts y conexiones)
    net.start()

    # Imprimir mensaje indicando que se están iniciando los servicios en cada servidor
    print(">>> 🟢 INICIANDO 4 SERVICIOS EN CADA NODO...")
    # Iterar sobre los 4 servidores para iniciar los servicios en cada uno
    for srv in [srv1, srv2, srv3, srv4]:
        # Iniciar el servicio WEB en el puerto 80 del servidor
        start_web(srv)                      # Port 80
        # Iniciar el servicio de STREAMING en el puerto 8080 del servidor
        start_service(srv, "STREAMING", 8080) # Port 8080
        # Iniciar el servicio de DATABASE en el puerto 3306 del servidor
        start_service(srv, "DATABASE", 3306)  # Port 3306
        # Iniciar el servicio de VOIP en el puerto 5060 del servidor
        start_service(srv, "VOIP", 5060)      # Port 5060

    # Imprimir mensaje de depuración indicando verificación de puertos
    print(">>> Verificando puertos en srv1...")
    # Ejecutar netstat en srv1 para mostrar los puertos TCP/UDP en escucha
    print(srv1.cmd("netstat -tuln"))

    # Imprimir un separador visual de 60 caracteres '='
    print("\n" + "="*60)
    # Imprimir el título del resumen de la topología
    print("   TOPOLOGÍA MIGRADA A MININET")
    # Mostrar la IP virtual (VIP) del servicio WEB en el puerto 80
    print("   VIP WEB:       10.0.0.100 (Port 80)")
    # Mostrar la IP virtual (VIP) del servicio de STREAMING en el puerto 8080
    print("   VIP STREAMING: 10.0.0.101 (Port 8080)")
    # Mostrar la IP virtual (VIP) del servicio de DATABASE en el puerto 3306
    print("   VIP DATABASE:  10.0.0.200 (Port 3306)")
    # Mostrar la IP virtual (VIP) del servicio de VOIP en el puerto 5060
    print("   VIP VOIP:      10.0.0.201 (Port 5060)")
    # Imprimir el separador visual de cierre con un salto de línea adicional
    print("="*60 + "\n")
    
    # Abrir la consola interactiva de Mininet (CLI) para que el usuario ejecute comandos
    CLI(net)
    # Detener y limpiar toda la red Mininet al salir de la CLI
    net.stop()

# Punto de entrada del script: se ejecuta solo si el archivo se corre directamente
if __name__ == '__main__':
    # Configurar el nivel de log de Mininet a 'info' para mostrar información relevante
    setLogLevel('info')
    # Llamar a la función principal que crea y ejecuta la topología
    run()

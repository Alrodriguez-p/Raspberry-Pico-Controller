# Watchdog en MicroPython para Home miners
Diseñado para ejecutarse en microcontroladores (Raspberry Pi Pico W). Consulta los datos del equipo vía API, monitoriza la temperatura del ASIC, las revoluciones del ventilador y el hash rate. Cuenta con integración multicanal en Discord mediante webhooks para enviar alertas y asegura la disponibilidad del sistema enviando heartbeats a Healthchecks.io.

## Entorno y Requisitos
- **Hardware:** Raspberry Pi Pico W
- **Firmware:** MicroPython `v1.29.0` (compilación del 2024-08-24)
- **Despliegue / Gestión:** 
  - *Thonny IDE* (para pruebas y depuración local).


## Características

### Conexión Wi-Fi 2.4GHz:

Conecta la Raspberry Pi Pico W a la banda 2.4GHz, al igual que el minero.

### Lectura directa y eficiente

Diseñado para consultar los datos del minero de forma ligera, evitando que el microcontrolador se quede sin memoria.

### Resiliente

Si el minero da un fallo puntual de lectura o el Wi-Fi parpadea, el sistema reintenta conectar solo y evita enviar falsas alarmas.

### Integración multicanal con Discord

Separa la lógica operativa en canales independientes de tu servidor:

**Alertas Térmicas:** Avisos en tiempo real cuando el chip ASIC o reguladores VRM superan los límites de seguridad.

**Logs:** Captura fallos de conexión, reconexión automática, caídas del hashrate, disminución excesiva en las RPM del ventilador y shutdown manual del equipo.

**Informe de estado:** Establece cada cuánto quieres recibir un informe para tener controlada la salud del minero estés donde estés. Siempre que tengas conexión a internet.

### Vigilancia externa

Envía heartbeats (pings) a https://healthchecks.io/ para detectar caídas repentinas del microcontrolador o cortes de energía.

### Pensado para correr 24/7

El script limpia la memoria RAM de forma periódica (gc.collect()) para asegurarse de que el microcontrolador no se sature ni se cuelgue con el paso de los días.


## Estructura del Proyecto

El proyecto consta de un único archivo $\rightarrow$ main.py


## Configuración e instalación

1. Clona o descarga este repositorio.
2. Recuerda rellenar las variables con los datos correctos:

``` Python
# ==========================================
# CONFIGURACIÓN
# ==========================================
WIFI_SSID = "SSID"          # Nombre exacto de tu Wi-Fi de 2.4 GHz
WIFI_PASS = "PASS"          # Contraseña de tu Wi-Fi
MINER_IP = "IP"             # IP local del minero

# CANALES DE DISCORD SEPARADOS
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/..."      # Alertas de temperatura
DISCORD_WEBHOOK_ERRORS = "https://discord.com/api/webhooks/..."   # Errores de conexión
DISCORD_WEBHOOK_RESUMEN = "https://discord.com/api/webhooks/..."  # Webhook para el informe de estado
```
3. Flashea los archivos en tu Raspberry Pi Pico W  usando Thonny.
4. **Recomendación:**

Es preferible asignar IPs estáticas tanto al minero como a la Raspberry Pi Pico W, para simplificar la reconexión en caso de que haya microcortes o una caída momentánea de la red. También desconectar el Smart Wi-Fi o Band Steering para evitar que el router elija automáticamente a qué banda se conectan los dispositivos. 


##  Consideraciones de Seguridad

**Texto plano:**

Los datos de telemetría viajan en texto plano (HTTP) dentro de la red local (LAN). Se recomienda mantener tu hardware de minería, junto con la Pico dentro de una VLAN aislada.

**Protección Externa:**

Aunque la comunicación local no está cifrada, todas las notificaciones enviadas a Discord están aseguradas mediante HTTPS (TLS de extremo a extremo).

**Sin Exposición Pública:**

La API nunca se expone directamente a internet.


## Contribuciones

Si ves algo que se pueda mejorar, se te ocurre una función nueva o encuentras algún fallo, ¡no dudes en colaborar y házmelo saber, mil gracias!

import network
import time
import urequests
import socket
import ujson
import gc

# ==========================================
# CONFIGURACIÓN
# ==========================================
WIFI_SSID = "SSID"          # Nombre exacto de tu Wi-Fi de 2.4 GHz
WIFI_PASS = "PASS"          # Contraseña de tu Wi-Fi
MINER_IP = "IP"             # IP local del minero

# CANALES DE DISCORD SEPARADOS
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/..."       # Alertas de temperatura
DISCORD_WEBHOOK_ERRORS = "https://discord.com/api/webhooks/..."    # Errores de conexión
DISCORD_WEBHOOK_RESUMEN = "https://discord.com/api/webhooks/..."   # Webhook para el resumen de estado

# ==========================================
# UMBRALES DE SEGURIDAD
# ==========================================
TEMP_THRESHOLD_ASIC = 70             # Límite para el chip ASIC (°C)
TEMP_THRESHOLD_VRM = 85.0            # Límite para el regulador VRM (°C)
FAN_RPM_MIN = 1000                   # Mínimo de RPMs aceptables del ventilador
CHECK_INTERVAL = 30                  # Consulta cada 30 segundos
ALERT_COOLDOWN = 120                 # Espera entre avisos de sobrecalentamiento (2 min)
ERROR_COOLDOWN = 300                 # Espera entre alertas de error en Discord (5 min)
HASHRATE_COOLDOWN = 120

MAX_FALLOS_CONSECUTIVOS = 3          # Número de fallos seguidos antes de avisar a Discord
RESUMEN_INTERVALO = 3600            # Tiempo entre resúmenes diarios en segundos (3600s = 1 hora)

# HEALTHCHECK
HEALTHCHECKS_URL = "https://hc-ping.com/TU-UUID-AQUI" # <-- Pega tu URL de Healthchecks.io
PING_INTERVALO = 900  # 900 segundos = 15 minutos

# ==========================================
# FUNCIONES AUXILIARES
# ==========================================
def conectar_wifi():
    """
    Inicializa la interfaz Wi-Fi de la Raspberry Pi Pico W en modo estación,
    desactiva el ahorro de energía para evitar cortes y establece la conexión
    con la red de 2.4 GHz especificada.
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    # Desactivar ahorro de energía Wi-Fi para evitar caídas de red y lecturas corruptas
    try:
        wlan.config(pm=0xa11140)
    except Exception:
        pass

    if not wlan.isconnected():
        print("Conectando al Wi-Fi...")
        wlan.connect(WIFI_SSID, WIFI_PASS)
        intentos = 0
        while not wlan.isconnected() and intentos < 15:
            time.sleep(1)
            intentos += 1

    if wlan.isconnected():
        print("✅ Wi-Fi conectado. IP:", wlan.ifconfig()[0])
        return True
    else:
        print("❌ Error al conectar al Wi-Fi.")
        return False

def enviar_confirmacion_arranque(url_webhook):
    """
    Envía un reporte instantáneo a Discord confirmando que la placa
    Raspberry Pi Pico W se ha encendido y ha iniciado el monitoreo.
    """
    
    payload = (
        "\u200b\n🟢 **MONITOREO INICIADO** 🟢\n\n"
    )

    try:
        enviar_discord(payload, url_webhook=url_webhook)
        print("✅ Confirmación de arranque enviada a Discord.")
    except Exception as e:
        print("❌ Fallo al enviar confirmación de arranque:", e)


def obtener_json_minero(ip_minero, timeout=5, reintentos=3):
    """
    Consulta la API REST del minero utilizando sockets de bajo nivel de Python.
    Separa correctamente las cabeceras HTTP del cuerpo JSON para evitar fallos de análisis.
    """
    for intento in range(reintentos):
        s = None
        try:
            addr = socket.getaddrinfo(ip_minero, 80)[0][-1]
            s = socket.socket()
            s.settimeout(timeout)
            s.connect(addr)
            
            peticion = f"GET /api/system/info HTTP/1.1\r\nHost: {ip_minero}\r\nConnection: close\r\n\r\n"
            s.send(peticion.encode())
            
            # Pequeña pausa para que el servidor llene el búfer de red
            time.sleep_ms(150)
            
            respuesta = b""
            while True:
                bloque = s.recv(1024)
                if not bloque:
                    break
                respuesta += bloque
            
            # SEPARAR CABECERAS HTTP DEL CUERPO (BODY)
            if b"\r\n\r\n" in respuesta:
                cabeceras, cuerpo = respuesta.split(b"\r\n\r\n", 1)
            else:
                cuerpo = respuesta
            
            # Buscar el JSON exclusivamente dentro del cuerpo de la respuesta
            inicio = cuerpo.find(b"{")
            fin = cuerpo.rfind(b"}")
            
            if inicio != -1 and fin != -1 and fin > inicio:
                json_bytes = cuerpo[inicio:fin + 1]
                return ujson.loads(json_bytes.decode("utf-8"))
            else:
                print(f"[Intento {intento + 1}/{reintentos}] Cuerpo HTTP sin estructura JSON válida")
                
        except Exception as e:
            print(f"[Intento {intento + 1}/{reintentos}] Error de socket/lectura: {e}")
            time.sleep(1)
        finally:
            if s:
                s.close()
                
    raise ValueError("Respuesta JSON inválida o incompleta tras varios reintentos")

def enviar_discord(mensaje, url_webhook=DISCORD_WEBHOOK_URL):
    """
    Envía notificaciones formateadas mediante peticiones POST HTTP en formato JSON
    hacia los webhooks configurados de Discord de forma segura.
    """
    headers = {"Content-Type": "application/json"}
    payload = ujson.dumps({"content": mensaje}).encode("utf-8")
    try:
        res = urequests.post(url_webhook, data=payload, headers=headers, timeout=10)
        if res.status_code in (200, 204):
            print("📩 Notificación enviada a Discord con ÉXITO.")
        else:
            print(f"⚠️ Discord rechazó la notificación. Código HTTP: {res.status_code}")
        res.close()
    except Exception as e:
        print(f"❌ No se pudo enviar la petición a Discord: {e}")
        
        
def realizar_ping_healthcheck():
    """
    Envía una señal de vida (heartbeat) mediante petición GET HTTPS al servicio
    externo Healthchecks.io para vigilar la disponibilidad continua del dispositivo.
    """
    try:
        # Petición HTTPS
        res = urequests.get(HEALTHCHECKS_URL, timeout=5)
        res.close() # Importante cerrar la conexión para liberar memoria en Pico
        print("💓 Ping de vida enviado con éxito a Healthchecks.io")
    except Exception as e:
        print("⚠️ No se pudo enviar el ping a Healthchecks:", e)
    finally:
        gc.collect() # Limpieza de RAM tras la llamada HTTPS

# ==========================================
# BUCLE PRINCIPAL
# ==========================================
def main():
    """
    Bucle de ejecución principal que coordina la verificación de red,
    las peticiones periódicas al minero, la evaluación de umbrales térmicos/hashrate,
    la gestión de errores y el envío de pings de disponibilidad.
    """
    if not conectar_wifi():
        return

    # ---NOTIFICACIÓN DE ARRANQUE ---
    wlan = network.WLAN(network.STA_IF)
    enviar_confirmacion_arranque(DISCORD_WEBHOOK_RESUMEN)
    # --------------------------------------
    
    ultimo_aviso_temp = 0
    ultimo_aviso_error = 0
    estaba_en_error = False
    fallos_consecutivos = 0
    ultimo_resumen = time.time()
    ultimo_aviso_hashrate = 0
    ultimo_ping = time.time() - PING_INTERVALO  # Para que envíe un primer ping al arrancar

    while True:
        ahora = time.time()
        gc.collect() # Limpieza de RAM al inicio del bucle
        
        try:
            # 1. Verificar Wi-Fi
            wlan = network.WLAN(network.STA_IF)
            if not wlan.isconnected():
                print("⚠️ Wi-Fi desconectado. Intentando reconectar...")
                if not conectar_wifi():
                    raise OSError("No hay conexión con el router Wi-Fi")

            # 2. Consultar la API del NerdAxe mediante socket directo (con 3 reintentos)
            datos = obtener_json_minero(MINER_IP, timeout=5, reintentos=3)

            # Si llega aquí, la lectura ha sido exitosa
            fallos_consecutivos = 0

            # Extraer temperaturas, ventilador y Hashrate
            temp_asic = float(datos.get("temp", datos.get("temp1", 0)))
            temp_vrm = float(datos.get("vrTemp", datos.get("temp2", 0)))
            fan_rpm = int(datos.get("fanrpm", 0))
            hashrate = datos.get("hashRate", datos.get("hashrate", "N/A"))

            # Mostrar lecturas en la consola de Thonny
            print(f"[OK] ASIC: {temp_asic} °C | VRM: {temp_vrm} °C | Fan: {fan_rpm} RPM | Hashrate: {hashrate} GH/s")
            
            # =========================================================================
            # FILTRO 127.5 °C (SHUTDOWN / ERROR DE LECTURA DEL SENSOR)
            # =========================================================================
            if temp_asic >= 120.0:
                print("🛑 Detección de Shutdown")
                if (ahora - ultimo_aviso_error) >= ERROR_COOLDOWN or not estaba_en_error:
                    msg_shutdown = (
                        "\u200b\n💤 **SHUTDOWN** 💤\n\n"
                        f"Se ha apagado el minero manualmente.\n"
                        f"• **Lectura ASIC:** `{temp_asic} °C`\n"
                        f"• **Lectura VRM:** `{temp_vrm} °C`\n"
                        "• **Estado:** `Proceso detenido, se puede apagar el dispositivo.`"
                    )
                    enviar_discord(msg_shutdown, url_webhook=DISCORD_WEBHOOK_ERRORS)
                    ultimo_aviso_error = ahora
                    estaba_en_error = True

                # Pausamos este ciclo y saltamos al siguiente para evitar falsas alarmas de temperatura
                time.sleep(CHECK_INTERVAL)
                continue
            # =========================================================================

            # Aviso de recuperación solo si venía de un fallo confirmado enviado a Discord
            if estaba_en_error:
                enviar_discord("\u200b\n✅ **RECONEXIÓN:** Pico ha vuelto a conectar con el NerdAxe correctamente.", url_webhook=DISCORD_WEBHOOK_ERRORS)
                estaba_en_error = False
                
            try:
                val_hashrate = float(hashrate)
            except (ValueError, TypeError):
                val_hashrate = 0.0

            if val_hashrate <= 0:
                if (ahora - ultimo_aviso_hashrate) >= HASHRATE_COOLDOWN:
                    mensaje_hash = (
                        "\u200b\n🚨 **¡ALERTA CRÍTICA!** 🚨\n\n"
                        "El minero responde pero el hashrate ha caído a 0 GH/s (posible bloqueo del proceso).\n\n"
                        f"• **ASIC:** `{temp_asic} °C`\n"
                        f"• **VRM:** `{temp_vrm} °C`\n"
                        f"• **Hashrate:** `{hashrate} GH/s`"
                    )
                    # Lo enviamos al canal de errores (puedes cambiar el webhook si prefieres otro)
                    enviar_discord(mensaje_hash, url_webhook=DISCORD_WEBHOOK_ERRORS)
                    ultimo_aviso_hashrate = ahora
            
                
            if (ahora - ultimo_resumen) >= RESUMEN_INTERVALO:
                mensaje_resumen = (
                    "\u200b\n📊 **RESUMEN DE ESTADO**\n\n"
                    f"• **ASIC:** `{temp_asic} °C`\n"
                    f"• **VRM:** `{temp_vrm} °C`\n"
                    f"• **FAN:** `{fan_rpm} RPM`\n"
                    f"• **Hashrate:** `{hashrate} GH/s`\n"
                    f"• **Estado:** `🟢 Operativo y estable`"
                )
                enviar_discord(mensaje_resumen, url_webhook=DISCORD_WEBHOOK_RESUMEN)
                ultimo_resumen += RESUMEN_INTERVALO

            # 3. Evaluar alertas independientes
            alerta_asic = temp_asic >= TEMP_THRESHOLD_ASIC
            alerta_vrm = temp_vrm >= TEMP_THRESHOLD_VRM
            alerta_fan = fan_rpm < FAN_RPM_MIN and fan_rpm > 0

            if alerta_asic or alerta_vrm or alerta_fan:
                if (ahora - ultimo_aviso_temp) >= ALERT_COOLDOWN:
                    detalles = []
                    if alerta_asic:
                        detalles.append(f"• **ASIC:** `{temp_asic} °C` (Límite: {TEMP_THRESHOLD_ASIC} °C)")
                    if alerta_vrm:
                        detalles.append(f"• **VRM:** `{temp_vrm} °C` (Límite: {TEMP_THRESHOLD_VRM} °C)")
                    if alerta_fan:
                        detalles.append(f"• **FAN:** `{fan_rpm} RPM` (Mínimo: {FAN_RPM_MIN} RPM)")

                    mensaje_alerta = (
                        "\u200b\n🔥 **¡ALERTA TÉRMICA!** 🔥\n\n"
                        + "\n".join(detalles)
                        + f"\n• **Hashrate:** `{hashrate} GH/s`"
                    )
                    
                    enviar_discord(mensaje_alerta, url_webhook=DISCORD_WEBHOOK_URL)
                    ultimo_aviso_temp = ahora

        except Exception as e:
            fallos_consecutivos += 1
            tipo_error = type(e).__name__
            print(f"[ERROR CAPTURADO ({fallos_consecutivos}/{MAX_FALLOS_CONSECUTIVOS})] {tipo_error}: {e}")

            # Solo notifica a Discord si supera los fallos consecutivos configurados
            if fallos_consecutivos >= MAX_FALLOS_CONSECUTIVOS:
                if (ahora - ultimo_aviso_error) >= ERROR_COOLDOWN or not estaba_en_error:
                    error_msg = f"\u200b\n⚠️ **FALLO EN PICO:**\nNo se pudo leer el NerdAxe tras {MAX_FALLOS_CONSECUTIVOS} intentos.\nDetalle: `{tipo_error}: {e}`"
                    enviar_discord(error_msg, url_webhook=DISCORD_WEBHOOK_ERRORS)
                    ultimo_aviso_error = ahora
                    estaba_en_error = True
                    
        # =========================================================================
        # PING DE VIDA A HEALTHCHECKS.IO (INDEPENDIENTE DEL MINERO)
        # =========================================================================
        if (ahora - ultimo_ping) >= PING_INTERVALO:
            realizar_ping_healthcheck()
            ultimo_ping = ahora
        # =========================================================================

        time.sleep(CHECK_INTERVAL)

# Arrancar
main()

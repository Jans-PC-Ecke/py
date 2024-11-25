import subprocess
import tkinter as tk
from tkinter import messagebox
from tkinter import simpledialog
from tkinter import ttk
import time
import psutil  # Psutil-Bibliothek für die Systemüberwachung

class ProgressBar:
    """Eine einfache Fortschrittsanzeige mit tkinter."""
    def __init__(self, master):
        self.label = tk.Label(master, text="", bg='#ffffff', fg='black', font=('Helvetica', 14))
        self.label.pack(pady=10)

    def update(self, message):
        """Aktualisiert die Fortschrittsanzeige mit einer Nachricht."""
        self.label.config(text=message)
        self.label.update_idletasks()

    def stop(self):
        """Stoppt die Fortschrittsanzeige."""
        self.label.config(text="Fortschritt abgeschlossen!")

def ask_password_and_run(command, password):
    """Führt den Befehl mit dem gegebenen Passwort aus."""
    if not password:
        messagebox.showerror("Eingabefehler", "Bitte Passwort eingeben.")
        return False

    command_with_password = f'echo {password} | sudo -S ' + ' '.join(command)

    try:
        result = subprocess.run(command_with_password, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.stdout.decode().strip()  # Ausgabe in der Konsole
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Passwort Fehler", f"Ein Fehler ist aufgetreten:\n{e.stderr.decode().strip()}\n{e.stdout.decode().strip()}")
        return False

def perform_arch_update(password, progress_bar):
    """Führt die Arch-Update-Kommandos aus und aktualisiert die Fortschrittsanzeige."""
    commands = [
        ["pacman", "-Syyu", "--noconfirm"],
        ["pamac", "remove", "-o", "--noconfirm"],
        ["pacman", "-Sc", "--noconfirm"],
        ["snap", "refresh"],
        ["flatpak", "update", "-y"]
    ]

    try:
        output = ask_password_and_run(commands[0], password)
        if output and "keine Pakete zum Aktualisieren" not in output:
            progress_bar.update(f"Führe aus: {' '.join(commands[0])}")
        else:
            progress_bar.update("Keine Pakete zu aktualisieren.")

        # Führe den Befehl aus, um nicht mehr benötigte Pakete aufzulisten
        orphaned_packages = ask_password_and_run(["pacman", "-Qdtq"], password)
        if orphaned_packages:
            orphaned_package_list = orphaned_packages.splitlines()
            if orphaned_package_list:
                progress_bar.update(f"Entferne nicht mehr benötigte Pakete: {', '.join(orphaned_package_list)}")
                # Entferne die nicht mehr benötigten Pakete
                ask_password_and_run(["pacman", "-Rns"] + orphaned_package_list, password)

        for command in commands[1:]:
            progress_bar.update(f"Führe aus: {' '.join(command)}")
            if not ask_password_and_run(command, password):
                return
    finally:
        progress_bar.stop()
    messagebox.showinfo("Update", "Arch Linux Update beendet!")

def perform_debian_update(password, progress_bar):
    """Führt die Debian-Update-Kommandos aus und aktualisiert die Fortschrittsanzeige."""
    commands = [
        ["apt", "update"],
        ["apt", "upgrade", "-y"],
        ["apt", "dist-upgrade", "-y"],
        ["apt", "autoremove", "-y"],
        ["flatpak", "update"],
        ["snap", "refresh"]
    ]

    try:
        for command in commands:
            progress_bar.update(f"Führe aus: {' '.join(command)}")
            if not ask_password_and_run(command, password):
                return
    finally:
        progress_bar.stop()
    messagebox.showinfo("Update", "Debian/Ubuntu Update beendet!")

def on_update_button_click():
    """Ereignishandler für den Update-Button."""
    password = simpledialog.askstring("Passwort", "Bitte geben Sie Ihr Passwort ein:", show='*')
    if password:
        progress_bar.update("Updates werden durchgeführt...")
        if current_os == "arch":
            perform_arch_update(password, progress_bar)
        elif current_os == "debian":
            perform_debian_update(password, progress_bar)

def on_exit_button_click():
    """Ereignishandler für den Beenden-Button."""
    root.quit()

def configure_tkinter():
    """Konfiguriert tkinter-Fenster."""
    root = tk.Tk()
    root.title("System Update & Monitor")
    root.geometry("800x600")  # Größe des Fensters
    root.configure(bg='#f7f7f7')  # Heller Hintergrund

    return root

def update_time():
    """Aktualisiert die Uhrzeit-Anzeige."""
    current_time = time.strftime("%H:%M:%S")
    time_label.config(text=current_time)
    # Aktualisiere die Uhrzeit jede Sekunde
    root.after(1000, update_time)

def update_system_info():
    """Aktualisiert die Systemstatistiken."""
    cpu_usage = psutil.cpu_percent(interval=1)
    ram_usage = psutil.virtual_memory().percent
    system_info_label.config(text=f"CPU Auslastung: {cpu_usage}%\nRAM Auslastung: {ram_usage}%")
    # Aktualisiere die Systeminfo jede Sekunde
    root.after(1000, update_system_info)

def get_temperatures():
    """Holt die Temperaturen der Hardwarekomponenten."""
    try:
        output = subprocess.run(['sensors'], capture_output=True, text=True, check=True)
        lines = output.stdout.splitlines()
        temp_info = []

        for line in lines:
            if ':' in line:
                parts = line.split(':')
                label = parts[0].strip()
                value = parts[1].strip().split()[0]  # Nehme nur den Temperaturwert
                temp_info.append(f"{label}: {value}")

        # Temperaturen für das GUI formatieren und anzeigen
        temperature_label.config(text="\n".join(temp_info))
    except Exception as e:
        temperature_label.config(text="Temperaturen konnten nicht abgerufen werden.")
        print(e)

def get_gpu_info():
    """Holt Informationen zur AMD RX 6600 und zur Nvidia RTX 3070 GPU."""
    # AMD RX 6600
    try:
        output = subprocess.run(['sensors'], capture_output=True, text=True, check=True)
        lines = output.stdout.splitlines()
        radeon_temp_info = []

        for line in lines:
            if 'temp1' in line:  # Dies könnte je nach sensoren Konfiguration variieren
                parts = line.split(':')
                label = parts[0].strip()
                value = parts[1].strip().split()[0]  # Nehme nur den Temperaturwert
                radeon_temp_info.append(f"{label}: {value}")

        radeon_temp_text = "\n".join(radeon_temp_info)
        gpu_info_label.config(text=radeon_temp_text)

    except Exception as e:
        gpu_info_label.config(text="AMD GPU-Informationen konnten nicht abgerufen werden.")

    # Nvidia RTX 3070
    try:
        output = subprocess.run(['nvidia-smi'], capture_output=True, text=True, check=True)
        nvidia_info = output.stdout.splitlines()

        nvidia_temp_info = []
        for line in nvidia_info:
            if "Gpu" in line:  # Zeile mit GPU-Temperatur
                nvidia_temp_info.append(line)

        nvidia_temp_text = "\n".join(nvidia_temp_info).replace('|', ' ').replace('    ', ' ').strip()
        nvidia_info_label.config(text=nvidia_temp_text)

    except Exception as e:
        nvidia_info_label.config(text="Nvidia GPU-Informationen konnten nicht abgerufen werden.")

def update_process_list(sort_key=None):
    """Aktualisiert die Prozessliste im Taskmanager."""
    processes = []
    for process in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):  # Hole Prozessinformationen
        try:
            process_info = {
                'pid': process.info['pid'],
                'name': process.info['name'],
                'cpu': process.info['cpu_percent'],
                'memory': process.info['memory_info'].rss / (1024 * 1024)  # in MB
            }
            processes.append(process_info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Sortiere nach dem angegebenen Schlüssel
    if sort_key:
        processes.sort(key=lambda x: x[sort_key], reverse=True)

    # Clearing old widgets from listbox
    process_listbox.delete(0, tk.END)

    for process in processes:
        process_info = f"{process['pid']} - {process['name']} - CPU: {process['cpu']}% - RAM: {process['memory']:.2f} MB"
        process_listbox.insert(tk.END, process_info)  # Füge neuen Prozess zur Listbox hinzu

    # Prozessliste alle 2 Sekunden aktualisieren
    root.after(2000, update_process_list)

def terminate_process():
    """Beendet den ausgewählten Prozess."""
    selected_index = process_listbox.curselection()
    if not selected_index:  # Sicherstellen, dass ein Prozess ausgewählt ist
        messagebox.showwarning("Auswahlfehler", "Bitte wählen Sie einen Prozess aus.")
        return
    selected_text = process_listbox.get(selected_index)
    pid = int(selected_text.split(" - ")[0])  # PID aus dem selektierten Text extrahieren
    try:
        process = psutil.Process(pid)
        process.terminate()
        messagebox.showinfo("Erfolg", f"Prozess mit PID {pid} wurde beendet.")
    except psutil.NoSuchProcess:
        messagebox.showerror("Fehler", "Prozess nicht gefunden.")
    except psutil.AccessDenied:
        messagebox.showerror("Fehler", "Zugriff verweigert. Prozess kann nicht beendet werden.")

def start_process():
    """Startet einen neuen Prozess."""
    command = simpledialog.askstring("Neuen Prozess starten", "Bitte geben Sie den Befehl ein, den Sie ausführen möchten:")
    if command:
        try:
            subprocess.Popen(command, shell=True)
            messagebox.showinfo("Erfolg", f"Prozess '{command}' wurde gestartet.")
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Starten des Prozesses: {e}")

# Hier solltest du bestimmen, welches OS aktuell ist. Dummy-Werte für die Demo:
current_os = "arch"  # oder "debian"

# GUI Setup
root = configure_tkinter()

# Notebook für Tabs
tab_control = ttk.Notebook(root)
tab_control.pack(expand=1, fill='both')

# Tab für Updates
update_tab = ttk.Frame(tab_control)
tab_control.add(update_tab, text='System Update')

progress_bar = ProgressBar(update_tab)

# Update-Button
update_button = tk.Button(update_tab, text="System Update", command=on_update_button_click, bg='#4CAF50', fg='#ffffff', height=2, width=15)
update_button.pack(pady=20)

# Beenden-Button
exit_button = tk.Button(update_tab, text="Beenden", command=on_exit_button_click, bg='#f44336', fg='#ffffff', height=2, width=15)
exit_button.pack(pady=10)

# Tab für Systemmonitor
monitor_tab = ttk.Frame(tab_control)
tab_control.add(monitor_tab, text='System Monitor')

# Uhrzeit-Anzeige
time_label = tk.Label(monitor_tab, text="", bg='#f7f7f7', fg='black', font=('Helvetica', 20))
time_label.pack(pady=20)

# Systeminfo-Anzeige
system_info_label = tk.Label(monitor_tab, text="", bg='#f7f7f7', fg='black', font=('Helvetica', 12))
system_info_label.pack(pady=20)

# Temperaturen-Anzeige
temperature_label = tk.Label(monitor_tab, text="", bg='#f7f7f7', fg='black', font=('Helvetica', 12))
temperature_label.pack(pady=10)

# AMD GPU-Informationen-Anzeige
gpu_info_label = tk.Label(monitor_tab, text="", bg='#f7f7f7', fg='black', font=('Helvetica', 12))
gpu_info_label.pack(pady=10)

# Nvidia GPU-Informationen-Anzeige
nvidia_info_label = tk.Label(monitor_tab, text="", bg='#f7f7f7', fg='black', font=('Helvetica', 12))
nvidia_info_label.pack(pady=10)

# Tab für Taskmanager
task_manager_tab = ttk.Frame(tab_control)
tab_control.add(task_manager_tab, text='Taskmanager')

# Sortierbuttons
sort_frame = tk.Frame(task_manager_tab, bg='#f7f7f7')
sort_frame.pack(pady=5)

sort_cpu_button = tk.Button(sort_frame, text="Nach CPU sortieren", command=lambda: update_process_list(sort_key='cpu'), bg='#2196F3', fg='#ffffff')
sort_cpu_button.pack(side=tk.LEFT, padx=5)

sort_ram_button = tk.Button(sort_frame, text="Nach RAM sortieren", command=lambda: update_process_list(sort_key='memory'), bg='#2196F3', fg='#ffffff')
sort_ram_button.pack(side=tk.LEFT, padx=5)

# Listbox für Prozesse
process_listbox = tk.Listbox(task_manager_tab, bg='#ffffff', font=('Helvetica', 12))
process_listbox.pack(expand=True, fill='both', padx=10, pady=10)

# Buttons zum Beenden und Starten von Prozessen
button_frame = tk.Frame(task_manager_tab, bg='#f7f7f7')
button_frame.pack(pady=5)

terminate_button = tk.Button(button_frame, text="Prozess Beenden", command=terminate_process, bg='#f44336', fg='white')
terminate_button.pack(side=tk.LEFT, padx=5)

start_button = tk.Button(button_frame, text="Neuen Prozess starten", command=start_process, bg='#4CAF50', fg='white')
start_button.pack(side=tk.LEFT, padx=5)

# Start der Zeit- und Systeminfo-Aktualisierung
update_time()
update_system_info()
get_temperatures()
get_gpu_info()
update_process_list()

root.mainloop()
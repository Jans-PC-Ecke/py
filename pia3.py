import json
import os
import subprocess
import pygame
import sys
import requests
from gtts import gTTS
from playsound import playsound
import speech_recognition as sr
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QTabWidget, QFileDialog, QPushButton, QInputDialog, QTextEdit, QSizePolicy,
    QListWidget, QCalendarWidget, QMessageBox, QCheckBox
)
from PyQt5.QtCore import QTimer, QDateTime, Qt, QThread, pyqtSignal
import argparse

# Wetter API Konfiguration
WEATHER_API_KEY = '736a03e3a7c6f1b387dde9fc3e377fc5'
WEATHER_API_URL = 'http://api.openweathermap.org/data/2.5/weather'

# Telegram API Konfiguration
BOT_TOKEN = '7204662701:AAHUtd-aDbum8gymLGG9scfiGomCRK6es3g'  
CHAT_ID = '7412131329'  

def send_telegram_message(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': message,
    }
    response = requests.post(url, data=data)
    return response.json()  

def run_pactl_command(command):
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return "", str(e)

def set_audio_volume(volume):
    if 0 <= volume <= 100:
        command = ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{volume}%"]
        stdout, stderr = run_pactl_command(command)
        if stderr:
            print(f"Fehler beim Setzen der Audiolautstärke: {stderr}")
        else:
            print(f"Audiolautstärke auf {volume}% gesetzt.")
    else:
        print("Die Lautstärke muss zwischen 0 und 100 liegen.")

def mute_audio(mute=True):
    command = ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if mute else "0"]
    stdout, stderr = run_pactl_command(command)
    if stderr:
        print(f"Fehler beim {'Stummschalten' if mute else 'Aktivieren der Audioausgabe'}: {stderr}")
    else:
        print(f"Audio {'stumm' if mute else 'aktiv'}.")

def speak_text(text):
    tts = gTTS(text=text, lang='de', slow=False)
    mp3_file = "output.mp3"
    tts.save(mp3_file)
    playsound(mp3_file)

def get_weather(city):
    params = { 'q': city, 'appid': WEATHER_API_KEY, 'units': 'metric', 'lang': 'de' }
    response = requests.get(WEATHER_API_URL, params=params)
    
    if response.status_code == 200:
        data = response.json()
        temp = data['main']['temp']
        description = data['weather'][0]['description']
        return f"Das aktuelle Wetter in {city} ist {temp} Grad Celsius mit {description}."
    else:
        return "Ich konnte die Wetterdaten nicht abrufen."

def listen_for_wake_word():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print("Bitte sage das Wake-Word.")
        while True:
            try:
                audio = recognizer.listen(source, timeout=3600)
                waking_word = recognizer.recognize_google(audio, language="de-DE")
                print(f"Wake-Word erkannt: {waking_word}")
                if "hey pia" in waking_word.lower():
                    print("Wake-Word erkannt. Sprachaufnahme aktiv.")
                    return True
            except sr.UnknownValueError:
                print("Unbekannter Wert. Bitte wiederhole das Wake-Word.")
            except sr.WaitTimeoutError:
                print("Wartezeit abgelaufen, versuche es erneut ...")
            except sr.RequestError as e:
                print(f"Konnte keine Verbindung zu Google herstellen; {e}")

def transcribe_speech(duration=10):
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source)
        print("Ich höre dir zu...")
        try:
            audio = recognizer.listen(source, timeout=duration)
            text = recognizer.recognize_google(audio, language="de-DE")
            print(f"Erkannter Text: {text}")
            return text
        except sr.UnknownValueError:
            print("Google Speech Recognition konnte die Audio nicht verstehen.")
            return None
        except sr.RequestError as e:
            print(f"Konnte keine Verbindung zu Google herstellen; {e}")
            return None
        except sr.WaitTimeoutError:
            print("Eingabe-Timeout erreicht, versuche es erneut ...")
            return None

class WakeWordThread(QThread):
    speech_input = pyqtSignal(str)
    wake_word_detected = pyqtSignal(bool)
    
    def run(self):
        while True:
            if listen_for_wake_word():
                self.wake_word_detected.emit(True)
                recognized_text = transcribe_speech()
                if recognized_text:
                    self.speech_input.emit(recognized_text)

class ManualRecordingThread(QThread):
    speech_input = pyqtSignal(str)

    def run(self):
        recognized_text = transcribe_speech()
        if recognized_text:
            self.speech_input.emit(recognized_text)

class QTextEditWithEnter(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent  

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.emit_signal()
        else:
            super().keyPressEvent(event)

    def emit_signal(self):
        text = self.toPlainText()
        self.clear()  
        if text:
            if self.parent_widget:  
                self.parent_widget.handle_text_input(text)

class GPT4AllGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.wake_word_thread = None
        self.manual_recording_thread = None
        self.notes = []
        self.events = {}
        self.history_text = []
        self.enable_speech_output = True  
        self.current_volume = 50 

        # Statuslabel zur Anzeige des Modellstatus.
        self.status_label = QLabel("Status: Modell nicht geladen.")
        self.status_label.setStyleSheet("""
            font-weight: bold; 
            color: #000000;  
            padding: 10px; 
            background: #F5F5F5; 
            border-radius: 10px; 
            text-align: center; 
            font-size: 16px;
            border: 2px solid #FFA500; 
            """)

        # Inactivity Timer
        self.inactivity_timer = QTimer()
        self.inactivity_timer.setInterval(3000)  
        self.inactivity_timer.timeout.connect(self.on_inactivity_timeout)

        # Notizendateipfad
        self.notes_file_path = "notes.json"

        pygame.mixer.init()

        # Hier das Attribut für das Wake-Word-Statuslabel definieren
        self.wake_word_status_label = QLabel("Wake Word: Nicht erkannt")
        self.wake_word_status_label.setStyleSheet("""
            color: #FF0000;
            font-weight: bold; 
            font-size: 18px;
            padding: 10px;
            background-color: #F8D7DA;
            border: 2px solid #f5c6cb;
            border-radius: 10px;
            text-align: center;
        """)

        self.initUI()  
        self.load_notes()  
        set_audio_volume(self.current_volume)  

        # Starte den Wake-Word-Thread
        self.wake_word_thread = WakeWordThread()
        self.wake_word_thread.speech_input.connect(self.process_speech_input)
        self.wake_word_thread.wake_word_detected.connect(self.update_wake_word_status)
        self.wake_word_thread.start()

    def closeEvent(self, event):
        if self.wake_word_thread is not None:
            self.wake_word_thread.quit()
            self.wake_word_thread.wait()  

        if self.manual_recording_thread is not None:
            self.manual_recording_thread.quit()
            self.manual_recording_thread.wait()  

        super().closeEvent(event)

    def initUI(self):
        self.setWindowTitle('GPT-4 All GUI')
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        left_layout = QVBoxLayout()
        main_layout.addLayout(left_layout)

        left_layout.addWidget(self.wake_word_status_label)

        left_layout.addWidget(self.create_main_content())

        right_layout = QVBoxLayout()

        self.time_label = QLabel()
        self.time_label.setStyleSheet("""
            color: #000000; 
            background: #F5F5F5;
            border: 1px solid #FFA500;
            border-radius: 8px; 
            padding: 10px;
            font-size: 16px;
        """)
        right_layout.addWidget(self.time_label)

        history_title = QLabel("Verlauf")
        history_title.setStyleSheet("""
            font-weight: bold; 
            color: #000000;  
            padding: 5px; 
            background: #F5F5F5; 
            border-radius: 8px; 
            text-align: center; 
            font-size: 16px;
            border: 1px solid #FFA500;
        """)
        right_layout.addWidget(history_title)

        self.history_view = QTextEdit()
        self.history_view.setReadOnly(True)
        self.history_view.setStyleSheet("""
            background: #F5F5F5; 
            color: #000000;  
            border: 1px solid #FFA500; 
            border-radius: 8px; 
            padding: 5px;
            font-size: 12px;
        """)
        right_layout.addWidget(self.history_view)

        right_layout.addWidget(self.status_label)  

        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        main_layout.addWidget(right_widget)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)

    def create_main_content(self):
        content_layout = QVBoxLayout()

        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            background: #F5F5F5;
            border: 1px solid #FFA500;
            border-radius: 8px; 
        """)
        tab_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Textverarbeitung Tab
        text_tab = QWidget()
        self.text_layout = QVBoxLayout()

        self.text_input = QTextEditWithEnter(parent=self)
        self.text_input.setPlaceholderText("Geben Sie hier Ihren Text ein... (drücken Sie Enter zum Senden)")
        self.text_layout.addWidget(self.text_input)

        self.text_output = QTextEdit()
        self.text_output.setReadOnly(True)
        self.text_layout.addWidget(self.text_output)

        button_style = """
            background-color: #FFA500; 
            color: #FFFFFF; 
            border: none; 
            border-radius: 8px; 
            padding: 10px; 
            font-size: 16px;
        """

        self.load_model_button = QPushButton("Modell laden")
        self.load_model_button.clicked.connect(self.select_model_path)
        self.load_model_button.setStyleSheet(button_style)
        self.text_layout.addWidget(self.load_model_button)

        self.load_file_button = QPushButton("Textdatei einlesen")
        self.load_file_button.clicked.connect(self.load_text_file)
        self.load_file_button.setStyleSheet(button_style)
        self.text_layout.addWidget(self.load_file_button)

        self.speech_output_checkbox = QCheckBox("Sprachausgabe aktivieren")
        self.speech_output_checkbox.setChecked(True)
        self.speech_output_checkbox.setStyleSheet("""
            font-size: 18px; 
            padding: 15px; 
        """)
        self.speech_output_checkbox.stateChanged.connect(self.toggle_speech_output)
        self.text_layout.addWidget(self.speech_output_checkbox)

        self.manual_record_button = QPushButton("Manuelle Spracheingabe starten")
        self.manual_record_button.clicked.connect(self.start_manual_recording)
        self.manual_record_button.setStyleSheet(button_style)
        self.text_layout.addWidget(self.manual_record_button)

        text_tab.setLayout(self.text_layout)
        tab_widget.addTab(text_tab, "Textverarbeitung")

        # Notizen Tab
        notes_tab = QWidget()
        notes_layout = QVBoxLayout()

        self.notes_list = QListWidget()
        self.notes_section = QTextEdit()
        self.notes_section.setReadOnly(True)

        button_style_notes = """
            background-color: #FFA500; 
            color: #FFFFFF; 
            border: none; 
            border-radius: 8px; 
            padding: 12px;  
            font-size: 16px; 
        """

        self.add_note_button = QPushButton("Notiz hinzufügen")
        self.add_note_button.clicked.connect(self.add_note)
        self.add_note_button.setStyleSheet(button_style_notes)

        self.delete_note_button = QPushButton("Notiz löschen")
        self.delete_note_button.clicked.connect(self.delete_note)
        self.delete_note_button.setStyleSheet(button_style_notes)

        self.delete_all_notes_button = QPushButton("Alle Notizen löschen")
        self.delete_all_notes_button.clicked.connect(self.delete_all_notes)
        self.delete_all_notes_button.setStyleSheet(button_style_notes)

        notes_layout.addWidget(self.notes_list)
        notes_layout.addWidget(self.notes_section)
        notes_layout.addWidget(self.add_note_button)
        notes_layout.addWidget(self.delete_note_button)
        notes_layout.addWidget(self.delete_all_notes_button)

        notes_tab.setLayout(notes_layout)
        tab_widget.addTab(notes_tab, "Notizen")

        # Musik Tab
        music_tab = QWidget()
        music_layout = QVBoxLayout()

        self.music_list = QListWidget()
        self.play_music_button = QPushButton("Musik abspielen")
        self.play_music_button.clicked.connect(self.play_music)
        self.stop_music_button = QPushButton("Musik stoppen")
        self.stop_music_button.clicked.connect(self.stop_music)

        music_layout.addWidget(self.music_list)
        music_layout.addWidget(self.play_music_button)
        music_layout.addWidget(self.stop_music_button)
        
        self.load_music_button = QPushButton("Musikdatei laden")
        self.load_music_button.clicked.connect(self.load_music_file)
        music_layout.addWidget(self.load_music_button)

        music_tab.setLayout(music_layout)
        tab_widget.addTab(music_tab, "Musik")

        content_layout.addWidget(tab_widget)
        main_content = QWidget()
        main_content.setLayout(content_layout)
        return main_content

    def toggle_speech_output(self, state):
        """Aktiviert oder deaktiviert die Sprachausgabe."""
        self.enable_speech_output = state == Qt.Checked
        if self.enable_speech_output:
            self.text_output.append("Sprachausgabe aktiviert.")
        else:
            self.text_output.append("Sprachausgabe deaktiviert.")

    def handle_text_input(self, text):
        """Verarbeitet Texteingaben und sendet sie an das lokale KI-Modell."""
        response_text = self.call_local_model(text)
        self.text_output.append(f"Eingegeben: {text}")
        self.text_output.append(f"Antwort vom Modell: {response_text}")
        if self.enable_speech_output:
            speak_text(response_text)

    def call_local_model(self, user_input):
        """Ruft das lokale KI-Modell auf und gibt die Antwort zurück."""
        model_path = "/home/erhardtux/.local/share/nomic.ai/GPT4All/your_model_script.py"  # Beispiel-Pfad, anpassen
        command = f"python {model_path} --input '{user_input}'"
        stdout, stderr = run_pactl_command(command)
        
        if stderr:
            return f"Fehler beim Ausführen des Modells: {stderr}"
        
        response = stdout.strip()  # Antwort des Modells
        return response if response else "Keine Antwort erhalten."

    def select_model_path(self):
        """Wählt den Pfad zum Modell aus und gibt Rückmeldung im Statuslabel."""
        model_dir = "/home/erhardtux/.local/share/nomic.ai/GPT4All/"
        options = QFileDialog.Options()
        model_path, _ = QFileDialog.getOpenFileName(self, "Modell auswählen", model_dir, "Modelle (*.gguf);;Alle Dateien (*)", options=options)

        if model_path and model_path.endswith('.gguf'):
            self.status_label.setText("Status: Modell erfolgreich geladen.")
        else:
            self.status_label.setText("Status: Ungültige Modell-Datei oder keine Datei ausgewählt.")

    def load_text_file(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "Textdatei auswählen", "", "Textdateien (*.txt);;Alle Dateien (*)", options=options)
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                self.text_input.setText(content)

    def load_music_file(self):
        options = QFileDialog.Options()
        music_path, _ = QFileDialog.getOpenFileName(self, "Musikdatei auswählen", "", "Audio Dateien (*.mp3 *.wav);;Alle Dateien (*)", options=options)
        if music_path:
            self.music_list.addItem(music_path)

    def play_music(self):
        current_row = self.music_list.currentRow()
        if current_row >= 0:
            music_file = self.music_list.item(current_row).text()
            pygame.mixer.music.load(music_file)
            pygame.mixer.music.play()
            self.status_label.setText("Status: Musik wird abgespielt.")

    def stop_music(self):
        pygame.mixer.music.stop()
        self.status_label.setText("Status: Musik gestoppt.")

    def update_time(self):
        current_time = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.time_label.setText(f"Uhrzeit: {current_time}")

    def start_manual_recording(self):
        if self.manual_recording_thread is None or not self.manual_recording_thread.isRunning():
            self.manual_recording_thread = ManualRecordingThread()
            self.manual_recording_thread.speech_input.connect(self.process_speech_input)
            self.manual_recording_thread.start()
            self.status_label.setText("Status: Manuelle Sprachaufnahme aktiv.")

    def update_wake_word_status(self, detected):
        if detected:
            self.wake_word_status_label.setText("Wake Word: Ich höre dir zu...")
            self.wake_word_status_label.setStyleSheet("""
                color: #155724;  
                font-weight: bold; 
                font-size: 18px;
                padding: 10px;
                background-color: #D4EDDA;
                border: 2px solid #C3E6CB;
                border-radius: 10px;
                text-align: center;
            """)
        else:
            self.wake_word_status_label.setText("Wake Word: Nicht erkannt")
            self.wake_word_status_label.setStyleSheet("""
                color: #721c24;  
                font-weight: bold; 
                font-size: 18px;
                padding: 10px;
                background-color: #F8D7DA;
                border: 2px solid #f5c6cb;
                border-radius: 10px;
                text-align: center;
            """)

    def on_inactivity_timeout(self):
        """Verarbeitet die Eingabe nach 3 Sekunden der Inaktivität."""
        self.restart_wakeword_listener()

    def delete_all_notes(self):
        """Löscht alle Notizen."""
        self.notes.clear()
        self.notes_list.clear()  # Löscht die angezeigte Liste der Notizen
        self.notes_section.clear()  # Löscht die angezeigte Notiz
        self.save_notes()  # Speichert die Änderungen (leere Notizen)
        if self.enable_speech_output:
            speak_text("Alle Notizen wurden gelöscht.")
        self.text_output.append("Alle Notizen wurden gelöscht.")

    def process_speech_input(self, recognized_text):
        """Verarbeitet die erkannten Sprachbefehle."""
        self.history_text.append(recognized_text)
        self.history_view.setPlainText("\n".join(self.history_text))

        # Hier wird der Timer bei einer neuen Spracheingabe zurückgesetzt
        self.inactivity_timer.start()

        recognized_text = recognized_text.lower()

        # Sprachbefehle für die Musiksteuerung
        if "musik abspielen" in recognized_text:
            self.play_music()

        elif "musik stoppen" in recognized_text:
            self.stop_music()

        elif "musikdatei laden" in recognized_text:
            self.load_music_file()

        # Hier können Sie weitere Sprachbefehle zur Verarbeitung hinzufügen...

        elif "audio lauter" in recognized_text:
            self.current_volume = min(self.current_volume + 10, 100)
            set_audio_volume(self.current_volume)
            response_text = f"Audiolautstärke erhöht auf {self.current_volume} %."
            self.text_output.append(response_text)
            if self.enable_speech_output:
                speak_text(response_text)

        elif "audio leiser" in recognized_text:
            self.current_volume = max(self.current_volume - 10, 0)
            set_audio_volume(self.current_volume)
            response_text = f"Audiolautstärke verringert auf {self.current_volume} %."
            self.text_output.append(response_text)
            if self.enable_speech_output:
                speak_text(response_text)

        # Weitere Sprachbefehle nach Bedarf...

    def load_notes(self):
        """Lädt die Notizen aus der JSON-Datei, falls vorhanden."""
        if os.path.exists(self.notes_file_path):
            with open(self.notes_file_path, 'r', encoding='utf-8') as file:
                self.notes = json.load(file)
                for note in self.notes:
                    self.notes_list.addItem(note)

    def save_notes(self):
        """Speichert die Notizen in einer JSON-Datei."""
        with open(self.notes_file_path, 'w', encoding='utf-8') as file:
            json.dump(self.notes, file)

    def add_note(self):
        note_text, ok = QInputDialog.getText(self, "Notiz hinzufügen", "Geben Sie den Text der Notiz ein:")
        if ok and note_text:
            self.notes.append(note_text)
            self.notes_list.addItem(note_text)
            self.notes_section.setText(note_text)
            self.save_notes()  
            send_telegram_message(BOT_TOKEN, CHAT_ID, note_text)
            if self.enable_speech_output:
                speak_text(f"Notiz hinzugefügt und gesendet: {note_text}")

    def delete_note(self):
        current_row = self.notes_list.currentRow()
        if current_row >= 0:
            deleted_note = self.notes[current_row]
            self.notes_list.takeItem(current_row)
            del self.notes[current_row]
            self.notes_section.clear()
            self.save_notes()  

# CLI-Funktion für den Shell-Modus
def shell_mode():
    """Startet die Anwendung im Shell-Modus."""
    print("Willkommen im Shell-Modus! Geben Sie 'hilfe' ein, um die verfügbaren Befehle anzuzeigen.")
    commands = {
        'hilfe': 'Zeigt alle verfügbaren Befehle an.',
        'wetter <stadt>': 'Zeigt das Wetter für die angegebene Stadt an.',
        'notiz hinzufügen <text>': 'Fügt eine Notiz hinzu.',
        'notiz löschen <index>': 'Löscht die Notiz an der angegebenen Position.',
        'notizen auflisten': 'Listet alle Notizen auf.',
        'beenden': 'Beendet den Shell-Modus.',
        'lautstärke setzen <wert>': 'Setzt die Audiolautstärke auf den angegebenen Wert (0-100).',
        'stumm': 'Mutet die Audioausgabe.',
        'aktivieren': 'Aktiviert die Audioausgabe.',
        'zeit': 'Zeigt die aktuelle Uhrzeit an.',
    }

    notes = []
    current_volume = 50  
    set_audio_volume(current_volume)  

    while True:
        user_input = input("Geben Sie einen Befehl ein: ").strip()

        if user_input.lower() == 'beenden':
            print("Shell-Modus wird beendet.")
            break
        elif user_input.lower() == 'hilfe':
            for cmd, desc in commands.items():
                print(f"{cmd}: {desc}")
        elif user_input.startswith("wetter"):
            parts = user_input.split()
            if len(parts) > 1:
                city = " ".join(parts[1:])
                weather_info = get_weather(city)
                print(weather_info)
            else:
                print("Bitte geben Sie eine Stadt an.")
        elif user_input.startswith("notiz hinzufügen"):
            parts = user_input.split(maxsplit=2)
            if len(parts) > 2:
                note = parts[2]
                notes.append(note)
                send_telegram_message(BOT_TOKEN, CHAT_ID, note)
                print(f"Notiz hinzugefügt: {note}")
            else:
                print("Bitte geben Sie den Text der Notiz an.")
        elif user_input.startswith("notiz löschen"):
            parts = user_input.split()
            if len(parts) > 2 and parts[2].isdigit():
                index = int(parts[2])
                if 0 <= index < len(notes):
                    deleted_note = notes.pop(index)
                    print(f"Notiz gelöscht: {deleted_note}")
                else:
                    print("Ungültiger Notiz-Index.")
            else:
                print("Bitte geben Sie einen gültigen Index an.")
        elif user_input.lower() == "notizen auflisten":
            if notes:
                print("Notizen:")
                for i, note in enumerate(notes):
                    print(f"{i}: {note}")
            else:
                print("Keine Notizen vorhanden.")
        elif user_input.startswith("lautstärke setzen"):
            parts = user_input.split()
            if len(parts) > 2:
                try:
                    volume = int(parts[2])
                    set_audio_volume(volume)
                    current_volume = volume  
                    print(f"Lautstärke auf {current_volume}% gesetzt.")
                except ValueError:
                    print("Bitte geben Sie eine gültige Zahl für die Lautstärke an.")
            else:
                print("Bitte geben Sie den gewünschten Lautstärkegrad an.")
        elif user_input.lower() == "stumm":
            mute_audio(True)
            print("Audiowiedergabe wurde stummgeschaltet.")
        elif user_input.lower() == "aktivieren":
            mute_audio(False)
            print("Audiowiedergabe wurde aktiviert.")
        elif user_input.lower() == "zeit":
            current_time = QDateTime.currentDateTime().toString("HH:mm")
            print(f"Es ist jetzt: {current_time}.")
        else:
            print("Unbekannter Befehl. Geben Sie 'hilfe' ein für eine Liste der Befehle.")

# Hauptausführung
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Starte die Anwendung im GUI- oder Shell-Modus.')
    parser.add_argument('--shell', action='store_true', help='Starte die Anwendung im Shell-Modus.')
    args = parser.parse_args()

    if args.shell:
        shell_mode()  
    else:
        app = QApplication(sys.argv)
        gui = GPT4AllGUI()
        gui.show()
        sys.exit(app.exec_())
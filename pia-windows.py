import sys
import requests
import os
import json
import subprocess
import pygame
from gtts import gTTS
import simpleaudio as sa
import speech_recognition as sr
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QTabWidget, QFileDialog, QPushButton, QInputDialog, QTextEdit, QSizePolicy,
    QListWidget, QCalendarWidget, QMessageBox, QCheckBox
)
from PyQt5.QtCore import QTimer, QDateTime, Qt, QThread, pyqtSignal
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import comtypes.client

# Wetter-API-Konstanten
WEATHER_API_KEY = '736a03e3a7c6f1b387dde9fc3e377fc5'  
WEATHER_API_URL = 'http://api.openweathermap.org/data/2.5/weather'

# Funktion zum Senden einer Telegram-Nachricht
def send_telegram_message(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {'chat_id': chat_id, 'text': message}
    response = requests.post(url, data=data)
    print(response.json())
    return response.json()

# Funktion zum Setzen der Lautstärke
def set_audio_volume(volume):
    if 0 <= volume <= 100:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
        volume_interface = interface.QueryInterface(IAudioEndpointVolume)
        volume_interface.SetMasterVolumeLevelScalar(volume / 100.0, None)
        print(f"Audiolautstärke auf {volume}% gesetzt.")
    else:
        print("Die Lautstärke muss zwischen 0 und 100 liegen.")

# Funktion zum Stummschalten des Audios
def mute_audio(mute=True):
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
    volume_interface = interface.QueryInterface(IAudioEndpointVolume)
    volume_interface.SetMute(mute, None)
    print(f"Audio {'stumm' if mute else 'aktiv'}.")

# Funktion zum Abrufen des Wetters
def get_weather(city):
    params = {
        'q': city,
        'appid': WEATHER_API_KEY,
        'units': 'metric',
        'lang': 'de'
    }
    response = requests.get(WEATHER_API_URL, params=params)
    if response.status_code == 200:
        data = response.json()
        temp = data['main']['temp']
        description = data['weather'][0]['description']
        return f"Das aktuelle Wetter in {city} ist {temp} Grad Celsius mit {description}."
    else:
        return "Ich konnte die Wetterdaten nicht abrufen."

# Funktion zur Sprachausgabe des Textes
def speak_text(text):
    tts = gTTS(text=text, lang='de', slow=False)
    mp3_file = "output.mp3"
    tts.save(mp3_file)
    wave_obj = sa.WaveObject.from_wave_file(mp3_file)
    play_obj = wave_obj.play()
    play_obj.wait_done()

# Wachwort-Erkennung
def listen_for_wake_word():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print("Bitte sage das Wake-Word.")
        while True:
            try:
                audio = recognizer.listen(source, timeout=5)
                waking_word = recognizer.recognize_google(audio, language="de-DE")
                print(f"Wake-Word erkannt: {waking_word}")
                if "hey pia" in waking_word.lower():
                    print("Wake-Word erkannt. Sprachaufnahme aktiv.")
                    return True
            except sr.UnknownValueError:
                print("Unbekannter Wert. Bitte wiederhole das Wake-Word.")
            except sr.WaitTimeoutError:
                print("Wartezeit abgelaufen, bitte versuche es erneut.")
            except sr.RequestError as e:
                print(f"Konnte keine Verbindung zu Google herstellen; {e}")

# Spracheingabe transkribieren
def transcribe_speech(duration=10):
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source)
        print("Ich höre zu...")
        audio = recognizer.listen(source, timeout=duration)
        try:
            text = recognizer.recognize_google(audio, language="de-DE")
            print(f"Erkannter Text: {text}")
            return text
        except sr.UnknownValueError:
            print("Google Speech Recognition konnte die Audio nicht verstehen.")
            return None
        except sr.RequestError as e:
            print(f"Konnte keine Verbindung zu Google herstellen; {e}")
            return None

# Threads für die Sprach- und Aufnahmeregistrierung
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

# Hauptklasse für die GUI
class GPT4AllGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.wake_word_thread = None
        self.notes = []
        self.events = {}
        self.history_text = []
        self.enable_speech_output = True
        self.current_volume = 50
        self.bot_token = '7204662701:AAHUtd-aDbum8gymLGG9scfiGomCRK6es3g'  
        self.chat_id = '7412131329'  

        self.notes_file_path = "notes.json"
        self.todo_list = []  # Liste für To-Do-Elemente

        pygame.mixer.init()

        self.initUI()
        self.load_notes()
        set_audio_volume(self.current_volume)

        self.wake_word_thread = WakeWordThread()
        self.wake_word_thread.speech_input.connect(self.process_speech_input)
        self.wake_word_thread.wake_word_detected.connect(self.update_wake_word_status)
        self.wake_word_thread.start()

    def initUI(self):
        self.setWindowTitle('GPT-4 All GUI')
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        left_layout = QVBoxLayout()
        main_layout.addLayout(left_layout)

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

        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        right_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
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

        # ToDo Tab - Hier wird das Todo Layout definiert
        todo_tab = QWidget()
        self.todo_layout = QVBoxLayout()

        self.todo_list_widget = QListWidget()
        self.todo_input = QTextEditWithEnter(parent=self)
        self.todo_input.setPlaceholderText("Geben Sie hier Ihre To-Do ein... (drücken Sie Enter zum Hinzufügen)")
        self.todo_layout.addWidget(self.todo_list_widget)
        self.todo_layout.addWidget(self.todo_input)

        self.add_todo_button = QPushButton("To-Do hinzufügen")
        self.add_todo_button.clicked.connect(self.add_todo)
        self.add_todo_button.setStyleSheet("""
            background-color: #FFA500; 
            color: #FFFFFF; 
            border: none; 
            border-radius: 8px; 
            padding: 10px; 
            font-size: 16px;
        """)

        self.delete_todo_button = QPushButton("To-Do löschen")
        self.delete_todo_button.clicked.connect(self.delete_todo)
        self.delete_todo_button.setStyleSheet("""
            background-color: #FFA500; 
            color: #FFFFFF; 
            border: none; 
            border-radius: 8px; 
            padding: 10px; 
            font-size: 16px;
        """)

        self.todo_layout.addWidget(self.add_todo_button)
        self.todo_layout.addWidget(self.delete_todo_button)

        todo_tab.setLayout(self.todo_layout)
        tab_widget.addTab(todo_tab, "To-Do Liste")

        # Textverarbeitung Tab
        text_tab = QWidget()
        self.text_layout = QVBoxLayout()

        self.text_input = QTextEditWithEnter(parent=self)
        self.text_input.setPlaceholderText("Geben Sie hier Ihren Text ein... (drücken Sie Enter zum Senden)")
        self.text_layout.addWidget(self.text_input)

        self.text_output = QTextEdit()
        self.text_output.setReadOnly(True)
        self.text_layout.addWidget(self.text_output)

        self.load_model_button = QPushButton("Modell laden")
        self.load_model_button.clicked.connect(self.select_model_path)
        self.load_model_button.setStyleSheet("""
            background-color: #FFA500; 
            color: #FFFFFF; 
            border: none; 
            border-radius: 8px; 
            padding: 10px; 
            font-size: 16px;
        """)
        self.text_layout.addWidget(self.load_model_button)

        self.load_file_button = QPushButton("Textdatei einlesen")
        self.load_file_button.clicked.connect(self.load_text_file)
        self.load_file_button.setStyleSheet("""
            background-color: #FFA500; 
            color: #FFFFFF; 
            border: none; 
            border-radius: 8px; 
            padding: 10px; 
            font-size: 16px;
        """)
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
        self.manual_record_button.setStyleSheet("""
            background-color: #FFA500; 
            color: #FFFFFF; 
            border: none; 
            border-radius: 8px; 
            padding: 10px; 
            font-size: 16px;
        """)
        self.text_layout.addWidget(self.manual_record_button)

        text_tab.setLayout(self.text_layout)
        tab_widget.addTab(text_tab, "Textverarbeitung")

        content_layout.addWidget(tab_widget)
        main_content = QWidget()
        main_content.setLayout(content_layout)
        return main_content

    def toggle_speech_output(self, state):
        self.enable_speech_output = state == Qt.Checked
        if self.enable_speech_output:
            self.text_output.append("Sprachausgabe aktiviert.")
        else:
            self.text_output.append("Sprachausgabe deaktiviert.")

    def handle_text_input(self, text):
        self.text_output.append(f"Eingegeben: {text}")

    def add_todo(self):
        """Fügt ein neues To-Do hinzu."""
        todo_text = self.todo_input.toPlainText().strip()
        if todo_text:
            self.todo_list.append(todo_text)
            self.todo_list_widget.addItem(todo_text)
            self.todo_input.clear()
            send_telegram_message(self.bot_token, self.chat_id, f"Neue To-Do: {todo_text}")
            if self.enable_speech_output:
                speak_text(f"To-Do hinzugefügt: {todo_text}")

    def delete_todo(self):
        """Löscht das aktuell ausgewählte To-Do."""
        current_row = self.todo_list_widget.currentRow()
        if current_row >= 0:
            deleted_todo = self.todo_list_widget.takeItem(current_row).text()
            self.todo_list.remove(deleted_todo)
            if self.enable_speech_output:
                speak_text(f"To-Do gelöscht: {deleted_todo}")

    def update_time(self):
        current_time = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.time_label.setText(f"Uhrzeit: {current_time}")

    def start_manual_recording(self):
        self.manual_recording_thread = ManualRecordingThread()
        self.manual_recording_thread.speech_input.connect(self.process_speech_input)
        self.manual_recording_thread.start()
        self.wake_word_status_label.setText("Status: Manuelle Sprachaufnahme aktiv.")

    def process_speech_input(self, recognized_text):
        self.history_text.append(recognized_text)
        self.history_view.setPlainText("\n".join(self.history_text))

        recognized_text = recognized_text.lower()

        # Wetterabfrage
        if "wetter in" in recognized_text:
            city = recognized_text.replace("wetter in", "").strip()
            if city:
                weather_info = get_weather(city)
                self.text_output.append(weather_info)
                if self.enable_speech_output:
                    speak_text(weather_info)

        # Hier könnten weitere Sprachbefehle hinzugefügt werden...

    def load_notes(self):
        if os.path.exists(self.notes_file_path):
            with open(self.notes_file_path, 'r', encoding='utf-8') as file:
                self.notes = json.load(file)
                for note in self.notes:
                    self.notes_list.addItem(note)

    def save_notes(self):
        with open(self.notes_file_path, 'w', encoding='utf-8') as file:
            json.dump(self.notes, file)

    def select_model_path(self):
        model_dir = "C:\path\to\your\model"
        options = QFileDialog.Options()
        model_path, _ = QFileDialog.getOpenFileName(self, "Modell auswählen", model_dir, "GGUF Modelle (*.gguf);;Alle Dateien (*)", options=options)

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

# Hauptausführung
if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = GPT4AllGUI()
    gui.show()
    sys.exit(app.exec_())

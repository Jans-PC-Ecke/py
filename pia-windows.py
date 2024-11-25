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

# Funktion zum Senden einer Telegram-Nachricht
def send_telegram_message(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {'chat_id': chat_id, 'text': message}
    response = requests.post(url, data=data)
    print(response.json())
    return response.json()

# Wetter-API-Konstanten
WEATHER_API_KEY = 'YOUR_API_KEY'  
WEATHER_API_URL = 'http://api.openweathermap.org/data/2.5/weather'

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

# Medienklasse, um Musik zu steuern
class MusicPlayer:
    def __init__(self):
        pygame.mixer.init()
        self.current_track = None

    def load(self, track_path):
        if self.current_track:
            pygame.mixer.music.load(track_path)
            self.current_track = track_path

    def play(self):
        if self.current_track:
            pygame.mixer.music.play()

    def stop(self):
        pygame.mixer.music.stop()

    def pause(self):
        pygame.mixer.music.pause()

    def unpause(self):
        pygame.mixer.music.unpause()

    def next_track(self):
        # Implementiere Logik zum Wechseln zur nächsten Musikdatei
        pass

    def previous_track(self):
        # Implementiere Logik zum Wechseln zur vorherigen Musikdatei
        pass

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

        self.bot_token = 'YOUR_BOT_TOKEN'  
        self.chat_id = 'YOUR_CHAT_ID'  
        self.music_player = MusicPlayer()

        self.notes_file_path = "notes.json"

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

        status_layout = self.create_status_layout()
        left_layout.addLayout(status_layout)

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

    def create_status_layout(self):
        status_layout = QHBoxLayout()
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
        status_layout.addWidget(self.status_label)
        return status_layout

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

        # Modelle laden
        self.load_model_button = QPushButton("Modell laden")
        self.load_model_button.clicked.connect(self.select_model_path)
        self.load_model_button.setStyleSheet(button_style)
        self.text_layout.addWidget(self.load_model_button)

        self.load_file_button = QPushButton("Textdatei einlesen")
        self.load_file_button.clicked.connect(self.load_text_file)
        self.load_file_button.setStyleSheet(button_style)
        self.text_layout.addWidget(self.load_file_button)

        # Checkbox für Sprachausgabe
        self.speech_output_checkbox = QCheckBox("Sprachausgabe aktivieren")
        self.speech_output_checkbox.setChecked(True)
        self.speech_output_checkbox.setStyleSheet("""
            font-size: 18px; 
            padding: 15px; 
        """)
        self.speech_output_checkbox.stateChanged.connect(self.toggle_speech_output)
        self.text_layout.addWidget(self.speech_output_checkbox)

        # Button für manuelle Spracheingabe
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

        # Kalender Tab
        calendar_tab = QWidget()
        calendar_layout = QVBoxLayout()
        self.calendar = QCalendarWidget()
        self.calendar.clicked.connect(self.calendar_clicked)
        calendar_layout.addWidget(self.calendar)

        self.add_event_button = QPushButton("Ereignis hinzufügen")
        self.add_event_button.setStyleSheet(button_style)
        self.add_event_button.clicked.connect(self.add_event_dialog)

        self.delete_event_button = QPushButton("Ereignis löschen")
        self.delete_event_button.setStyleSheet(button_style)
        self.delete_event_button.clicked.connect(self.delete_event_dialog)

        self.event_view = QTextEdit() 
        self.event_view.setReadOnly(True)

        calendar_layout.addWidget(self.add_event_button)
        calendar_layout.addWidget(self.delete_event_button)
        calendar_layout.addWidget(self.event_view)

        calendar_tab.setLayout(calendar_layout)
        tab_widget.addTab(calendar_tab, "Kalender")

        # Musik Tab
        music_tab = QWidget()
        music_layout = QVBoxLayout()

        self.music_controls_layout = QHBoxLayout()

        self.load_music_button = QPushButton("Musik laden")
        self.load_music_button.setStyleSheet(button_style)
        self.load_music_button.clicked.connect(self.load_music_file)

        self.play_button = QPushButton("Play")
        self.play_button.setStyleSheet(button_style)
        self.play_button.clicked.connect(self.play_music)

        self.pause_button = QPushButton("Pause")
        self.pause_button.setStyleSheet(button_style)
        self.pause_button.clicked.connect(self.pause_music)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setStyleSheet(button_style)
        self.stop_button.clicked.connect(self.stop_music)

        self.music_controls_layout.addWidget(self.load_music_button)
        self.music_controls_layout.addWidget(self.play_button)
        self.music_controls_layout.addWidget(self.pause_button)
        self.music_controls_layout.addWidget(self.stop_button)

        music_layout.addLayout(self.music_controls_layout)

        music_tab.setLayout(music_layout)
        tab_widget.addTab(music_tab, "Musiksteuerung")

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

    def load_music_file(self):
        options = QFileDialog.Options()
        music_file, _ = QFileDialog.getOpenFileName(self, "Musikdatei auswählen", "", "Musikdateien (*.mp3 *.wav);;Alle Dateien (*)", options=options)
        if music_file:
            self.music_player.load(music_file)
            self.text_output.append(f"Musik geladen: {os.path.basename(music_file)}")

    def play_music(self):
        self.music_player.play()
        self.text_output.append("Musik gestartet.")
        if self.enable_speech_output:
            speak_text("Musik gestartet.")

    def pause_music(self):
        self.music_player.pause()
        self.text_output.append("Musik pausiert.")
        if self.enable_speech_output:
            speak_text("Musik pausiert.")

    def stop_music(self):
        self.music_player.stop()
        self.text_output.append("Musik gestoppt.")
        if self.enable_speech_output:
            speak_text("Musik gestoppt.")

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

    def update_time(self):
        current_time = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.time_label.setText(f"Uhrzeit: {current_time}")

    def start_manual_recording(self):
        self.manual_recording_thread = ManualRecordingThread()
        self.manual_recording_thread.speech_input.connect(self.process_speech_input)
        self.manual_recording_thread.start()
        self.status_label.setText("Status: Manuelle Sprachaufnahme aktiv.")

    def update_wake_word_status(self, detected):
        if detected:
            self.wake_word_status_label.setText("Wake Word: Erkannt")
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

    def delete_all_notes(self):
        self.notes.clear()
        self.notes_list.clear()  
        self.notes_section.clear()  
        self.save_notes()  
        if self.enable_speech_output:
            speak_text("Alle Notizen wurden gelöscht.")
        self.text_output.append("Alle Notizen wurden gelöscht.")

    def process_speech_input(self, recognized_text):
        print(f"Erkannter Befehl: {recognized_text}")
        self.history_text.append(recognized_text)
        self.history_view.setPlainText("\n".join(self.history_text))

        recognized_text = recognized_text.lower()

        # Audiosteuerung
        if "audio lauter" in recognized_text:
            self.current_volume = min(self.current_volume + 10, 100)
            set_audio_volume(self.current_volume)
            response_text = f"Audiolautstärke erhöht auf {self.current_volume}%."
            self.text_output.append(response_text)
            if self.enable_speech_output:
                speak_text(response_text)

        elif "audio leiser" in recognized_text:
            self.current_volume = max(self.current_volume - 10, 0)
            set_audio_volume(self.current_volume)
            response_text = f"Audiolautstärke verringert auf {self.current_volume}%."
            self.text_output.append(response_text)
            if self.enable_speech_output:
                speak_text(response_text)

        elif "audio auf" in recognized_text:
            try:
                value = int(recognized_text.split("audio auf")[-1].strip().replace("%", ""))
                set_audio_volume(value)
                self.current_volume = value
                response_text = f"Audiolautstärke auf {self.current_volume}% gesetzt."
                self.text_output.append(response_text)
                if self.enable_speech_output:
                    speak_text(response_text)
            except (ValueError, IndexError):
                error_message = "Bitte geben Sie eine gültige Zahl für die Lautstärke an."
                self.text_output.append(error_message)
                if self.enable_speech_output:
                    speak_text(error_message)

        elif "audio stumm" in recognized_text:
            mute_audio(True)
            response_text = "Audio wurde stummgeschaltet."
            self.text_output.append(response_text)
            if self.enable_speech_output:
                speak_text(response_text)

        elif "audio aktiv" in recognized_text:
            mute_audio(False)
            response_text = "Audio wurde aktiviert."
            self.text_output.append(response_text)
            if self.enable_speech_output:
                speak_text(response_text)

        # Wetterabfrage
        elif "wetter in" in recognized_text:
            city = recognized_text.replace("wetter in", "").strip()
            if city:
                weather_info = get_weather(city)
                self.text_output.append(weather_info)
                if self.enable_speech_output:
                    speak_text(weather_info)

        # Notizen
        elif "notiz hinzufügen" in recognized_text:
            note_text = recognized_text.replace("notiz hinzufügen", "").strip()
            if note_text:
                self.notes.append(note_text)
                self.notes_list.addItem(note_text)
                self.notes_section.setText(note_text)
                self.save_notes()
                send_telegram_message(self.bot_token, self.chat_id, f"Notiz hinzugefügt: {note_text}")  
                if self.enable_speech_output:
                    speak_text(f"Notiz hinzugefügt: {note_text}")

        elif "notiz löschen" in recognized_text:
            current_row = self.notes_list.currentRow()
            if current_row >= 0:
                deleted_note = self.notes[current_row]
                self.notes_list.takeItem(current_row)
                del self.notes[current_row]
                self.notes_section.clear()
                self.save_notes()
                send_telegram_message(self.bot_token, self.chat_id, f"Notiz gelöscht: {deleted_note}")  
                if self.enable_speech_output:
                    speak_text(f"Notiz gelöscht: {deleted_note}")

        elif "alle notizen löschen" in recognized_text:
            self.delete_all_notes()  

        elif "notiz vorlesen" in recognized_text:
            if self.notes:
                for note in self.notes:
                    if self.enable_speech_output:
                        speak_text(f"Notiz: {note}")
            else:
                if self.enable_speech_output:
                    speak_text("Es gibt keine Notizen zum Vorlesen.")

        # Programm starten
        elif "starte" in recognized_text:
            app_name = recognized_text.replace("starte", "").strip()
            if app_name:
                try:
                    subprocess.Popen(app_name + '.exe')  # Ersetzen Sie dies durch den richtigen Programmnamen
                    response_text = f"{app_name} wurde gestartet."
                    self.text_output.append(response_text)
                    if self.enable_speech_output:
                        speak_text(response_text)
                except Exception as e:
                    error_message = f"Konnte {app_name} nicht starten: {e}"
                    self.text_output.append(error_message)
                    if self.enable_speech_output:
                        speak_text(error_message)

        # Programm beenden
        elif "beende" in recognized_text:
            app_name = recognized_text.replace("beende", "").strip()
            if app_name:
                try:
                    subprocess.call(["taskkill", "/IM", f"{app_name}.exe", "/F"])  # Beispiel: taskkill für das Programm
                    response_text = f"{app_name} wurde beendet."
                    self.text_output.append(response_text)
                    if self.enable_speech_output:
                        speak_text(response_text)
                except Exception as e:
                    error_message = f"Konnte {app_name} nicht beenden: {e}"
                    self.text_output.append(error_message)
                    if self.enable_speech_output:
                        speak_text(error_message)

    def add_event(self, date, event_name):
        event_date = date.toString("dd.MM.yyyy")
        if event_name:
            if event_date not in self.events:
                self.events[event_date] = []
            self.events[event_date].append(event_name)
            send_telegram_message(self.bot_token, self.chat_id, f"Neues Ereignis hinzugefügt: {event_name} am {event_date}")
            self.update_event_view(event_date)  
            self.text_output.append(f"Ereignis hinzugefügt: '{event_name}' am {event_date}")

    def add_event_dialog(self):
        event_name, ok = QInputDialog.getText(self, "Ereignis hinzufügen", "Geben Sie den Namen des Ereignisses ein:")
        if ok and event_name:
            self.add_event(date=self.calendar.selectedDate(), event_name=event_name)

    def delete_event_dialog(self):
        current_date_str = self.calendar.selectedDate().toString("dd.MM.yyyy")
        if current_date_str in self.events:
            events = self.events[current_date_str]
            if events:
                event_to_delete, ok = QInputDialog.getItem(self, "Ereignis löschen", "Wählen Sie ein Ereignis zum Löschen aus:", events)
                if ok and event_to_delete:
                    self.delete_event(event_to_delete)
            else:
                QMessageBox.information(self, "Ereignis löschen", "Keine Ereignisse für dieses Datum vorhanden.")
        else:
            QMessageBox.information(self, "Ereignis löschen", "Keine Ereignisse für dieses Datum vorhanden.")

    def delete_event(self, event_name):
        current_date_str = self.calendar.selectedDate().toString("dd.MM.yyyy")
        if current_date_str in self.events:
            self.events[current_date_str].remove(event_name)
            send_telegram_message(self.bot_token, self.chat_id, f"Ereignis gelöscht: {event_name} am {current_date_str}")
            self.text_output.append(f"Ereignis gelöscht: {event_name} am {current_date_str}")
            self.update_event_view(current_date_str)

    def update_event_view(self, date):
        if date in self.events:
            events = self.events[date]
            event_text = "\n".join(events)
            self.event_view.setPlainText(f"Ereignisse für {date}:\n{event_text}")
        else:
            self.event_view.setPlainText(f"Keine Ereignisse für {date}.")

    def show_events_for_date(self, date):
        event_date = date.toString("dd.MM.yyyy")
        self.update_event_view(event_date)

    def calendar_clicked(self):
        self.show_events_for_selected_date()

    def show_events_for_selected_date(self):
        selected_date = self.calendar.selectedDate().toString("dd.MM.yyyy")
        if selected_date in self.events:
            events = self.events[selected_date]
            event_text = "\n".join(events)
            QMessageBox.information(self, f"Ereignisse am {selected_date}", event_text)
        else:
            QMessageBox.information(self, f"Ereignisse am {selected_date}", "Keine Ereignisse an diesem Datum.")

    def load_notes(self):
        if os.path.exists(self.notes_file_path):
            with open(self.notes_file_path, 'r', encoding='utf-8') as file:
                self.notes = json.load(file)
                for note in self.notes:
                    self.notes_list.addItem(note)

    def save_notes(self):
        with open(self.notes_file_path, 'w', encoding='utf-8') as file:
            json.dump(self.notes, file)

    def add_note(self):
        note_text, ok = QInputDialog.getText(self, "Notiz hinzufügen", "Geben Sie den Text der Notiz ein:")
        if ok and note_text:
            self.notes.append(note_text)
            self.notes_list.addItem(note_text)
            self.notes_section.setText(note_text)
            self.save_notes()  
            send_telegram_message(self.bot_token, self.chat_id, f"Notiz hinzugefügt: {note_text}")  

    def delete_note(self):
        current_row = self.notes_list.currentRow()
        if current_row >= 0:
            deleted_note = self.notes[current_row]
            self.notes_list.takeItem(current_row)
            del self.notes[current_row]
            self.notes_section.clear()
            self.save_notes()  
            send_telegram_message(self.bot_token, self.chat_id, f"Notiz gelöscht: {deleted_note}")  

# Hauptausführung
if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = GPT4AllGUI()
    gui.show()
    sys.exit(app.exec_())
import sys, datetime, threading, requests, logging
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLineEdit, QTextEdit, QMessageBox, QListWidget, QHBoxLayout
from PyQt6.QtCore import pyqtSignal, pyqtSlot

class DiscordScraperApp(QWidget):
    load_dm_signal = pyqtSignal(str, str, str)

    def __init__(self, default_api_key=''):
        super().__init__()
        self.default_api_key = default_api_key
        self.dm_channels = []
        self.init_ui()
        self.load_dm_signal.connect(self.load_dm_slot)
        logging.basicConfig(filename='discord_scraper.log', level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')
        logging.info('Discord Scraper started')

    def init_ui(self):
        self.setWindowTitle('Discord Scraper')
        self.setGeometry(100, 100, 400, 400)
        layout = QVBoxLayout(self)

        self.api_key_input = self.add_input_field(layout, 'Enter API Key', self.default_api_key)
        self.server_id_input = self.add_input_field(layout, 'Enter Server ID')
        self.channel_id_input = self.add_input_field(layout, 'Enter Channel ID')
        self.dm_list_widget = QListWidget(self)
        layout.addWidget(self.dm_list_widget)
        self.result_display = QTextEdit(self)
        layout.addWidget(self.result_display)

        self.add_button(layout, 'Load DMs', self.load_dms)
        self.add_button(layout, 'Refresh DMs', self.refresh_dms)
        self.add_button(layout, 'Get Approximate Member Count', self.show_member_count)
        self.add_button(layout, 'Get Approximate Presence Count', self.show_presence_count)
        
        msg_layout = QHBoxLayout()
        self.num_messages_input = QLineEdit(self)
        self.num_messages_input.setPlaceholderText('Number of messages')
        msg_layout.addWidget(self.num_messages_input)
        self.add_button(msg_layout, 'Get Messages', self.show_messages)
        layout.addLayout(msg_layout)

        self.dm_list_widget.itemClicked.connect(self.show_dm_messages)

    def add_input_field(self, layout, placeholder, default_text=''):
        input_field = QLineEdit(self)
        input_field.setPlaceholderText(placeholder)
        input_field.setText(default_text)
        layout.addWidget(input_field)
        return input_field

    def add_button(self, layout, label, function):
        button = QPushButton(label, self)
        button.clicked.connect(function)
        layout.addWidget(button)

    def get_headers(self):
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, 'Input Error', 'Please enter an API Key')
            return None
        return {'Authorization': api_key}

    def get_data_from_discord(self, url):
        headers = self.get_headers()
        if not headers:
            return None
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        logging.error(f'Error fetching data from Discord: {response.status_code} - {response.text}')
        return None

    def load_dms(self):
        try:
            self.load_dm_channels_from_file()
            self.load_dm_channels()
        except FileNotFoundError:
            reply = QMessageBox.question(self, 'Error', 'Failed to load DM channels from file. Do you want to re-download the list?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.dm_channels = []
                self.dm_list_widget.clear()
                threading.Thread(target=self.load_dms_thread).start()
            else:
                QMessageBox.warning(self, 'Error', 'Failed to load DM channels')

    def load_dms_thread(self):
        dm_channels = self.get_data_from_discord('https://discord.com/api/v9/users/@me/channels')
        if isinstance(dm_channels, list):
            dm_list = []
            for channel in dm_channels:
                if channel.get('type') == 1:  # Only direct messages, no group DMs
                    username = channel.get('recipients', [{}])[0].get('username', 'Unknown')
                    last_message = self.get_data_from_discord(f'https://discord.com/api/v9/channels/{channel["id"]}/messages?limit=1')
                    if last_message:
                        timestamp = last_message[0].get('timestamp', '')
                        timestamp_str = datetime.datetime.fromisoformat(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                        dm_list.append((username, timestamp_str, channel.get("id")))
            dm_list.sort(key=lambda x: x[1], reverse=True)
            self.dm_channels = dm_list
            self.save_dm_channels_to_file()
            for item in dm_list:
                self.load_dm_signal.emit(item[0], item[1], item[2])

    @pyqtSlot(str, str, str)
    def load_dm_slot(self, username, timestamp_str, channel_id):
        self.dm_list_widget.addItem(f'{username} ({timestamp_str}) ({channel_id})')

    def refresh_dms(self):
        self.dm_channels = []
        self.dm_list_widget.clear()
        threading.Thread(target=self.load_dms_thread).start()

    def load_dm_channels(self):
        for item in self.dm_channels:
            self.load_dm_signal.emit(item[0], item[1], item[2])

    def load_dm_channels_from_file(self):
        with open('dm_channels.txt', 'r') as f:
            for line in f:
                username, timestamp_str, channel_id = line.strip().split(',')
                self.dm_channels.append((username, timestamp_str, channel_id))

    def save_dm_channels_to_file(self):
        with open('dm_channels.txt', 'w') as f:
            for item in self.dm_channels:
                f.write(f'{item[0]},{item[1]},{item[2]}\n')

    def show_dm_messages(self, item=None):
        channel_id = item.text().split(' (')[-1].replace(')', '') if item else self.channel_id_input.text().strip()
        messages = self.get_data_from_discord(f'https://discord.com/api/v9/channels/{channel_id}/messages?limit=10')
        if messages:
            self.result_display.setText('\n'.join(f'({datetime.datetime.fromisoformat(m["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")}) - {m["author"]["username"]}: {m["content"]}' for m in messages))

    def show_member_count(self):
        self.display_data('approximate_member_count')

    def show_presence_count(self):
        self.display_data('approximate_presence_count')

    def show_messages(self):
        channel_id = self.channel_id_input.text().strip()
        num_messages = self.num_messages_input.text().strip()
        if not channel_id or not num_messages.isdigit():
            QMessageBox.warning(self, 'Input Error', 'Please enter valid Channel ID and number of messages')
            return
        messages = self.get_data_from_discord(f'https://discord.com/api/v9/channels/{channel_id}/messages?limit={num_messages}')
        if messages:
            self.result_display.setText('Messages:\n' + '\n'.join(f'({datetime.datetime.fromisoformat(m["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")}) - {m["author"]["username"]}: {m["content"]}' for m in messages))

    def display_data(self, data_type):
        server_id = self.server_id_input.text().strip()
        if not server_id:
            QMessageBox.warning(self, 'Input Error', 'Please enter a Server ID')
            return
        data = self.get_data_from_discord(f'https://discord.com/api/guilds/{server_id}/preview')
        if data:
            self.result_display.setText(f'{data_type.replace("_", " ").title()}: {data.get(data_type, "Key not found")}')

    def closeEvent(self, event):
        self.save_dm_channels_to_file()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    scraper_app = DiscordScraperApp()
    scraper_app.show()
    sys.exit(app.exec())

import sys, datetime, threading, requests, logging
from PyQt6.QtWidgets import *
from PyQt6.QtCore import pyqtSignal, pyqtSlot

class DiscordScraperApp(QWidget):
    load_dm_signal = pyqtSignal(str, str, str)

    def __init__(self, default_api_key=''):
        super().__init__()
        self.dm_channels = []
        self.init_ui(default_api_key)
        self.load_dm_signal.connect(self.load_dm_slot)
        logging.basicConfig(filename='discord_scraper.log', level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')

    def init_ui(self, default_api_key):
        self.setWindowTitle('Discord Scraper')
        self.setGeometry(100, 100, 400, 400)
        layout = QVBoxLayout(self)

        self.api_key_input = QLineEdit(self)
        self.api_key_input.setPlaceholderText('Enter API Key')
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setText(default_api_key)
        self.server_id_input = QLineEdit(self)
        self.server_id_input.setPlaceholderText('Enter Server ID')
        self.channel_id_input = QLineEdit(self)
        self.channel_id_input.setPlaceholderText('Enter Channel ID')
        self.dm_list_widget = QListWidget(self)
        self.result_display = QTextEdit(self)

        for widget in [self.api_key_input, self.server_id_input, self.channel_id_input, self.dm_list_widget, self.result_display]:
            layout.addWidget(widget)

        buttons = [
            ('Load DMs', self.load_dms),
            ('Refresh DMs', self.refresh_dms),
            ('Get Approximate Member Count', lambda: self.display_data('approximate_member_count')),
            ('Get Approximate Presence Count', lambda: self.display_data('approximate_presence_count')),
            ('Get Guilds', self.show_guilds)
        ]

        for label, func in buttons:
            btn = QPushButton(label, self)
            btn.clicked.connect(func)
            layout.addWidget(btn)

        msg_layout = QHBoxLayout()
        self.num_messages_input = QLineEdit(self)
        self.num_messages_input.setPlaceholderText('Number of messages')
        msg_layout.addWidget(self.num_messages_input)
        get_msg_btn = QPushButton('Get Messages', self)
        get_msg_btn.clicked.connect(self.show_messages)
        msg_layout.addWidget(get_msg_btn)
        layout.addLayout(msg_layout)

        self.dm_list_widget.itemClicked.connect(self.show_dm_messages)

    def get_headers(self):
        api_key = self.api_key_input.text().strip()
        return {'Authorization': api_key} if api_key else None

    def get_data_from_discord(self, url):
        headers = self.get_headers()
        if not headers:
            QMessageBox.warning(self, 'Input Error', 'Please enter an API Key')
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
            if QMessageBox.question(self, 'Error', 'Failed to load DM channels from file. Re-download?', 
                                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
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
                if channel.get('type') == 1:
                    username = channel.get('recipients', [{}])[0].get('username', 'Unknown')
                    last_message = self.get_data_from_discord(f'https://discord.com/api/v9/channels/{channel["id"]}/messages?limit=1')
                    if last_message:
                        timestamp = datetime.datetime.fromisoformat(last_message[0].get('timestamp', '')).strftime("%Y-%m-%d %H:%M:%S")
                        dm_list.append((username, timestamp, channel.get("id")))
            self.dm_channels = sorted(dm_list, key=lambda x: x[1], reverse=True)
            self.save_dm_channels_to_file()
            for item in self.dm_channels:
                self.load_dm_signal.emit(*item)

    @pyqtSlot(str, str, str)
    def load_dm_slot(self, username, timestamp_str, channel_id):
        self.dm_list_widget.addItem(f'{username} ({timestamp_str}) ({channel_id})')

    def refresh_dms(self):
        self.dm_channels = []
        self.dm_list_widget.clear()
        threading.Thread(target=self.load_dms_thread).start()

    def load_dm_channels(self):
        for item in self.dm_channels:
            self.load_dm_signal.emit(*item)

    def load_dm_channels_from_file(self):
        with open('dm_channels.txt', 'r') as f:
            self.dm_channels = [tuple(line.strip().split(',')) for line in f]

    def save_dm_channels_to_file(self):
        with open('dm_channels.txt', 'w') as f:
            f.writelines(f'{",".join(item)}\n' for item in self.dm_channels)

    def show_dm_messages(self, item=None):
        channel_id = item.text().split(' (')[-1].replace(')', '') if item else self.channel_id_input.text().strip()
        messages = self.get_data_from_discord(f'https://discord.com/api/v9/channels/{channel_id}/messages?limit=10')
        if messages:
            self.result_display.setText('\n'.join(f'({datetime.datetime.fromisoformat(m["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")}) - {m["author"]["username"]}: {m["content"]}' for m in messages))

    def display_data(self, data_type):
        server_id = self.server_id_input.text().strip()
        if not server_id:
            QMessageBox.warning(self, 'Input Error', 'Please enter a Server ID')
            return
        data = self.get_data_from_discord(f'https://discord.com/api/guilds/{server_id}/preview')
        if data:
            self.result_display.setText(f'{data_type.replace("_", " ").title()}: {data.get(data_type, "Key not found")}')

    def show_messages(self):
        channel_id = self.channel_id_input.text().strip()
        num_messages = self.num_messages_input.text().strip()
        if not channel_id or not num_messages.isdigit():
            QMessageBox.warning(self, 'Input Error', 'Please enter valid Channel ID and number of messages')
            return
        messages = self.get_data_from_discord(f'https://discord.com/api/v9/channels/{channel_id}/messages?limit={num_messages}')
        if messages:
            self.result_display.setText('Messages:\n' + '\n'.join(f'({datetime.datetime.fromisoformat(m["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")}) - {m["author"]["username"]}: {m["content"]}' for m in messages))

    def show_guilds(self):
        guilds = self.get_data_from_discord('https://discord.com/api/v9/users/@me/guilds')
        if guilds:
            self.result_display.setText('Guilds:\n' + '\n'.join(f'{guild["name"]} ({guild["id"]})' for guild in guilds))

    def closeEvent(self, event):
        self.save_dm_channels_to_file()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    scraper_app = DiscordScraperApp()
    scraper_app.show()
    sys.exit(app.exec())

import toml
import uuid
import os
from pathlib import Path
from flask import Flask
from jellyfin_apiclient_python.client import JellyfinClient
import logging
import queue

class Settings:
  transcode_h265 = False
  remote_kbps: int = 10000
  local_kbps: int = 2147483
  transcode_hi10p: bool = False
  always_transcode: bool = False
  transcode_to_h265: bool = False

settings = Settings()

params = {
    'SortBy': 'SortName,ProductionYear',
    'SortOrder': 'Ascending',
    'Recursive': True,
    'ImageTypeLimit': 1,
    'Limit': 100,
    'Fields': 'RemoteTrailers,MediaSources',
}

client = JellyfinClient()
app = Flask(__name__)

config_file = os.path.expanduser( '~' ) / Path('.config/jellyfin2txt/config.toml')
config_file_dev = os.path.dirname(os.path.dirname(__file__)) / Path('config.toml')

if not config_file.is_file():
    if not config_file_dev.is_file():
        logging.error('Config file not found in one of this location:')
        logging.error(f' - {config_file}')
        logging.error(f' - {config_file_dev}')
        exit(1)
    config_file = config_file_dev

app.config.from_file(config_file, load=toml.load)

client.config.data["app.default"] = True
version = "0.1"
client.config.app(
    "jellyfin2txt", version, "uwu", str(uuid.uuid4())
)
client.config.data["http.user_agent"] = "Jellyfin-MPV-Shim/%s" % version
client.config.data["auth.ssl"] = not False
client.auth.connect_to_address(app.config['SERVER_URL'])
result = client.auth.login(
    app.config['SERVER_URL'],
    app.config['USERNAME'],
    app.config['PASSWORD'],
)
if "AccessToken" in result:
    credentials = client.auth.credentials.get_credentials()
    server = credentials["Servers"][0]
    server["uuid"] = str(uuid.uuid4())
    server["username"] = app.config['USERNAME']
    state = client.authenticate({"Servers": [server]}, discover=False)
else:
    logging.error("Can't login to server")
    exit(1)

try:
    client.start()
except ValueError as err:
    logging.error(err)
    exit(1)

class ExtractTasks(dict):
    def __contains__(self, srt_name):
        for k,v in self.items():
            if v.srt_name == srt_name:
                return True
        return False
    def item(self, srt_name):
        items = [x for x in self.values() if x.srt_name == srt_name]
        if items:
            return items[0]
        return False

extract_queue = queue.Queue()
extract_tasks = ExtractTasks()

logging.basicConfig(encoding='utf-8', level=logging.INFO)
import toml
import uuid
import os
from pathlib import Path
from flask import Flask
from jellyfin_apiclient_python.client import JellyfinClient
import logging
import queue
from babelfish import Language

from jellyfin2txt.utils import ExtractTasks, Jellyfin2TextSerializer

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
app.json_encoder = Jellyfin2TextSerializer

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

extract_queue = queue.Queue()
extract_tasks = ExtractTasks()

subs_providers_lang = app.config['SUBS_PROVIDERS_LANGS']
subs_providers_lang_set = set()
invalid_language = []
for lang in subs_providers_lang:
    try:
        subs_providers_lang_set.add(Language(lang))
    except ValueError as err:
        if 'is not a valid language' in str(err):
            invalid_language.append(lang)
        else:
            raise err
if invalid_language:
    logging.error(f'[CONFIG ERROR] Uknown languages for SUBS_PROVIDERS_LANGS: {invalid_language}')
    exit(1)
app.config['SUBS_PROVIDERS_LANGS'] = subs_providers_lang_set

logging.basicConfig(encoding='utf-8', level=logging.INFO)
logging.getLogger('subliminal').setLevel(logging.WARNING)
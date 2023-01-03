import toml
import uuid
import os
from flask import Flask
from jellyfin_apiclient_python.client import JellyfinClient

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

app.config.from_file(os.getcwd() + '/config.toml', load=toml.load)

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
client.start()


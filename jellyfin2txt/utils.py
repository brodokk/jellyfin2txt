import os
import json

from jellyfin2txt.key import Key, CollisionsList

def _read_keyfile():
    keys_json = {}
    keyfile = 'keyfile.json'
    if os.path.isfile(keyfile):
        with open(keyfile, 'r') as file:
            keys_json = json.load(file)
    keys = CollisionsList()
    for key in keys_json:
        keys.append(Key(**key), 'id')
    return keys

import os
import json
import uuid
from pathlib import PosixPath

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

def sizeof_fmt(num, suffix="B"):
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"

class ExtractTasks(dict):
    def __contains__(self, srt_name):
        for k,v in self.items():
            if v.srt_name == srt_name:
                return True
        return False
    def is_uuid(self, item):
        try:
            return uuid.UUID(str(item))
        except ValueError:
            return False
    def item(self, item):
        if self.is_uuid(item):
            items = [x for x in self.values() if x.item_id == item]
        else:
            items = [x for x in self.values() if x.srt_name == item]
        if items:
            return items[0]
        return False


class ExtractObject:

    def __init__(self, srt_name, status, item_id, item_name, error_message = ""):
        self.srt_name = srt_name
        self.status = status
        self.item_id = item_id
        self.item_name = item_name
        self.error_message = error_message

    def __repr__(self):
        return f"{self.srt_name}`{self.status}`{self.item_id}`{self.item_name}`{self.error_message}"


class Jellyfin2TextSerializer(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ExtractObject):
            serialized = {}
            for k,v in obj.__dict__.items():
                if isinstance(v, PosixPath):
                    serialized[k] = str(v)
                else:
                    serialized[k] = v
            return serialized
        return json.JSONEncoder.default(self, obj)
import os
import re
import argparse
import json
import secrets
import dataclasses
from typing import Optional, List

from tabulate import tabulate


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


class CollisionsList(list):
    def get(self, field, value):
        for item in self:
            if getattr(item, field) == value:
                return item
        return None

    def update(self, search_field, search_value, field, value):
        for item in self:
            if getattr(item, search_field) == search_value:
                setattr(item, field, value)
                return True
        raise ValueError('--> No value {0} found for field {1}'.format(search_value, search_field))

    def contains(self, field, value):
        for item in self:
            if getattr(item, field) == value:
                return True
        return False

    def append(self, other, field):
        for item in self:
            if getattr(other, field) == getattr(item, field):
                raise ValueError('--> Value already added: {0}'.format(other))
        super().append(other)


class KeyManagerException(Exception):
    pass


class KeyManagerActionException(Exception):
    pass


@dataclasses.dataclass
class Key:
    id: str
    key: str
    comment: str
    revoked: bool


@dataclasses.dataclass
class KeyManager:
    keys: CollisionsList[Key]

    def __init__(self, *args, **kargs):
        self.keys = CollisionsList()
        self.keyfile = "keyfile.json"
        self._load_keyfile()
        super().__init__()

    def _load_keyfile(self):
        keys_json = self._read_keyfile()
        for key in keys_json:
            self.keys.append(Key(**key), 'id')

    def _save_key(self):
        self._write_keyfile()

    def _revoke_key(self, id):
        self.keys.update('id', id, 'revoked', True)
        self._write_keyfile()

    def _read_keyfile(self):
        data = {}
        if os.path.isfile(self.keyfile):
            with open(self.keyfile, 'r') as file:
                data = json.load(file)
        return data

    def _write_keyfile(self):
        with open(self.keyfile, 'w') as f:
            json.dump(self.keys, f, ensure_ascii=False, cls=EnhancedJSONEncoder)

    def genkey(self, comment=""):
        key = secrets.token_urlsafe(16)
        if not self.keys.contains('key', key):
            index = str(1)
            if len(self.keys):
                index = str(int(self.keys[-1].id) + 1)
            self.keys.append(Key(index, key, comment, False), 'key')
            self._save_key()

    def revokekey(self, id):
        if self.keys.contains('id', id):
            self._revoke_key(id)

    def listkeys(self):
        table = []
        headers = ["id", "revoked", "comment", "key"]
        for key in self.keys:
            row = [key.id, key.revoked, key.comment, key.key]
            table.append(row)
        print(tabulate(table, headers, tablefmt="grid"))


keyManager = KeyManager(CollisionsList())

class keyManagerAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if len(values) < 1:
            return
        action = values[0]
        args = {}
        if len(values) == 2:
            if not re.fullmatch(r'[a-z]+=\d+', values[1]):
                raise KeyManagerActionException("The format should be <field>=<data>")
            args_key = values[1].split('=')[0]
            args_value = values[1].split('=')[1]
            args[args_key] = args_value
        if type(action) == str:
            method_list = [func for func in dir(KeyManager) if callable(getattr(KeyManager, func))]
            if action in method_list:
                getattr(keyManager, action)(**args)
            else:
                raise KeyManagerException


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='script 1.0')
    parser.add_argument(
        'genkey', nargs='*', action=keyManagerAction,
        help='Generate a new key')
    parser.add_argument(
        'revokekey', nargs='*', type=int, action=keyManagerAction,
        help='Revoke a key. The format should be key=<id>')
    parser.add_argument(
        'listkeys', nargs='*', action=keyManagerAction,
        help='List all the key available')
    try:
        args = parser.parse_args()
    except Exception as e:
        raise e
        if type(e).__name__ not in  ['KeyManagerException', 'KeyManagerActionException']:
            raise e
        print(parser.print_help())

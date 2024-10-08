from __future__ import annotations

import sys
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


class KeysValidator(list):
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
    keys: KeysValidator[Key]

    def __init__(self, *args, **kargs) -> None:
        self.keys = KeysValidator()
        self.keyfile = "keyfile.json"
        self._load_keyfile()
        super().__init__()

    def _load_keyfile(self) -> None:
        keys_json = self._read_keyfile()
        for key in keys_json:
            self.keys.append(Key(**key), 'id')

    def _save_key(self) -> None:
        self._write_keyfile()

    def _revoke_key(self, id: int) -> None:
        self.keys.update('id', id, 'revoked', True)
        self._write_keyfile()

    def _read_keyfile(self) -> dict:
        data = {}
        if os.path.isfile(self.keyfile):
            with open(self.keyfile, 'r') as file:
                data = json.load(file)
        return data

    def _write_keyfile(self) -> None:
        with open(self.keyfile, 'w') as f:
            json.dump(self.keys, f, ensure_ascii=False, cls=EnhancedJSONEncoder)

    def _gen_table(self, keys: list, headers=["id", "revoked", "comment", "key"]) -> str:
        table = []
        for key in keys:
            row = [key.id, key.revoked, key.comment, key.key]
            table.append(row)
        return tabulate(table, headers, tablefmt="grid")

    def genkey(self, comment: str ="") -> None:
        key = secrets.token_urlsafe(16)
        if not self.keys.contains('key', key):
            index = str(1)
            if len(self.keys):
                index = str(int(self.keys[-1].id) + 1)
            self.keys.append(Key(index, key, comment, False), 'key')
            self._save_key()
            print(self._gen_table(self.keys))
        else:
            print("Key already exist")

    def revokekey(self, id: int) -> None:
        if self.keys.contains('id', id):
            self._revoke_key(id)
            print(self._gen_table(self.keys))
        else:
            print("Key not found")

    def listkeys(self) -> None:
        print(self._gen_table(self.keys))


keyManager = KeyManager(KeysValidator())

class keyManagerAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if len(values) < 1:
            return
        action = values[0]
        args = {}
        if len(values) == 2:
            if not re.fullmatch(r'[a-z]+=[a-zA-Z0-9]+', values[1]):
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
        sys.exit()


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
        print(parser.print_help())
    except Exception as e:
        if e.__class__.__name__ not in  ['KeyManagerException', 'KeyManagerActionException']:
            raise e
        print(parser.print_help())

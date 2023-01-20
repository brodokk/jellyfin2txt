#!/bin/python

from typing import Optional
import tempfile
import urllib.request
import os
from pathlib import Path

import sys
import json
import argparse
import logging

from flask import request

from jellyfin2txt.key import Key
from jellyfin2txt.config import client, app, params, settings
from jellyfin2txt.media import Media
from jellyfin2txt.subtitle import Subtitle
from jellyfin2txt.utils import _read_keyfile

def check_perms(data):
    data_str = data.decode('utf-8')
    try:
        data_json = json.loads(data_str)
        if "auth_key" in data_json.keys():
            keys = _read_keyfile()
            if keys.contains('key', data_json['auth_key']):
                if not keys.get('key', data_json['auth_key']).revoked:
                    return True
                return False
            return False
        return False
    except json.decoder.JSONDecodeError:
        return False

def access_denied():
    return 'Invalid auth_key!', 403

@app.route('/')
def index():
    html = """
    <p>A simple api to make parsing easier on NeosVR of a small part of the jellyfin API.</p>
    <p>Check the source code: <a href='https://github.com/brodokk/jellyfin2txt'>https://github.com/brodokk/jellyfin2txt</a></p>
    """
    return html

@app.route('/movies', methods=['POST'])
def movies():
    if check_perms(request.data):
        return Media.movies(
            request.args.get("StartIndex", 0),
            request.args.get("Limit", 100),
            request.args.get("ThumbFillHeight", 320),
            request.args.get("ThumbFillWidth", 213),
            request.args.get("ThumbQuality", 96),
        )
    return access_denied()

@app.route('/series', methods=['POST'])
def series():
    if check_perms(request.data):
        return Media.series(
            request.args.get("StartIndex", 0),
            request.args.get("Limit", 100),
            request.args.get("ThumbFillHeight", 320),
            request.args.get("ThumbFillWidth", 213),
            request.args.get("ThumbQuality", 96),
        )
    return access_denied()

@app.route('/series/<serie_id>', methods=['POST'])
def seasons(serie_id):
    if check_perms(request.data):
        return Media.seasons(serie_id)
    return access_denied()

@app.route('/series/<serie_id>/<season_id>', methods=['POST'])
def episodes(serie_id, season_id):
    if check_perms(request.data):
        return Media.episodes(serie_id, season_id)
    return access_denied()

@app.route('/subtitles/<item_id>', methods=['POST'])
def subtitles(item_id):
    if check_perms(request.data):
        return Subtitle.subtitles(item_id)
    return access_denied()

@app.route('/subtitles/<item_id>/<subtitle_name>', methods=['POST'])
def subtitle(item_id, subtitle_name):
    if check_perms(request.data):
        return Subtitle.subtitle(item_id, subtitle_name)
    return access_denied()

@app.route('/subtitles/<item_id>/<subtitle_name>/extract', methods=['POST'])
def subtitle_extract(item_id, subtitle_name):
    if check_perms(request.data):
        return Subtitle.subtitle_extract(item_id, subtitle_name)
    return access_denied()

@app.route('/subtitles/<item_id>/discover', methods=['POST'])
def subtitle_discover(item_id):
    if check_perms(request.data):
        return Subtitle.subtitle_discover(item_id)
    return access_denied()

@app.route('/subtitles/<item_id>/all', methods=['POST'])
def subtitles_all(item_id):
    if check_perms(request.data):
        return Subtitle.subtitles_all(item_id)
    return access_denied()

@app.route('/subtitles/<item_id>/<subtitle_name>/extract/status', methods=['POST'])
def subtitle_extract_status(item_id, subtitle_name):
    if check_perms(request.data):
        return Subtitle.subtitle_extract_status(item_id, subtitle_name)
    return access_denied()

@app.route('/extract_status', methods=['POST'])
def extract_status():
    if check_perms(request.data):
        return Subtitle.extract_status()
    return access_denied()

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--port', type=int, default=5000,
        help='Port to use, default 5000')
    parser.add_argument(
        '--debug', action='store_true',
        help='Make the server verbose')
    args = parser.parse_args()

    if args.debug:
        loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
        for logger in loggers:
            logger.setLevel(logging.DEBUG)

    media_folders = client.jellyfin.get_media_folders()
    item_ids = []
    items = {}

    for item in media_folders['Items']:
        item_ids.append(item['Id'])
        items[item['Name']] = item['Id']

    def item_not_found(item, key):
        logging.error('{} ({}) not found in:'.format(item, key))
        for item_name, item_id in items.items():
            logging.error('{}: {}'.format(item_name, item_id))
        sys.exit(1)

    if not app.config.get('MOVIES_ID'):
        if app.config.get('MOVIES') not in items.keys():
            item_not_found('MOVIES', app.config.get('MOVIES'))
        else:
            client.movies_id = items[app.config['MOVIES']]
    if not app.config.get('SERIES_ID'):
        if app.config.get('SERIES') not in items.keys():
            item_not_found('SERIES', app.config.get('SERIES'))
        else:
            client.series_id = items[app.config['SERIES']]
    if (
        not getattr(client, 'movies_id', False) and
        app.config.get('MOVIES_ID') not in items.values()
    ):
        item_not_found('MOVIES_ID', app.config.get('MOVIES_ID'))
    if (
        not getattr(client, 'series_id', False) and
        app.config.get('SERIES_ID') not in items.values()
    ):
        item_not_found('SERIES_ID', app.config.get('SERIES_ID'))


    import threading
    task = threading.Thread(
        target=Subtitle.subtitle_extract_thread
    )
    task.start()

    app.run(host='0.0.0.0', port=args.port)

    client.stop()

if __name__ == '__main__':
    main()
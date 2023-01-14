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

USER_APP_NAME = "Jellyfin2txt"

@app.route('/movies_id', methods=['POST'])
def movies_id():
    item_id = "4e25807f0e7f80b36466b7559fad73b5"
    profile = "TW96aWxsYS81LjAgKFdpbmRvd3MgTlQgMTAuMDsgV2luNjQ7IHg2NDsgcnY6OTUuMCkgR2Vja28vMjAxMDAxMDEgRmlyZWZveC85NS4wfDE2NDIwOTExODk4NzM1"
    is_playback = True
    sid = 3
    aid = 1
    args = {
            'UserId': "9bc44fa4c1204b2b8a78e58145de169d",
            'MaxStreamingBitrate': 4000000,
            'AutoOpenLiveStream': is_playback,
            'StartTimeTicks': 11603630000,
            'DeviceId': "TW96aWxsYS81LjAgKFdpbmRvd3MgTlQgMTAuMDsgV2luNjQ7IHg2NDsgcnY6OTUuMCkgR2Vja28vMjAxMDAxMDEgRmlyZWZveC85NS4wfDE2NDIwOTExODk4NzM1",
            'IsPlayback': is_playback
    }
    args['SubtitleStreamIndex'] = sid
    args['AudioStreamIndex'] = aid
    args['MediaSourceId'] = item_id

    #new_sync_client = client.jellyfin.new_sync_play_v2('test')
    #print(type(new_sync_client))
    #print(dir(new_sync_client))
    #print(new_sync_client)
    sync_play = client.jellyfin.get_sync_play(item_id)
    print(sync_play)
    join = client.jellyfin.join_sync_play("43032e1fd8ec4e6f8accf5a1595b1ae0")
    print(join)


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
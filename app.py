#!/bin/python

import requests
import argparse
import datetime
import json
import toml
from itertools import cycle
from bs4 import BeautifulSoup

import pytz
from timezonefinder import TimezoneFinder

from flask import Flask
from flask_apscheduler import APScheduler
from flask import request

from jellyfin_apiclient_python.client import JellyfinClient
import logging
import uuid


client = JellyfinClient()
app = Flask(__name__)

app.config.from_file('config.toml', load=toml.load)

params = {
    'SortBy': 'SortName,ProductionYear',
    'SortOrder': 'Ascending',
    'Recursive': True,
    'ImageTypeLimit': 1,
    'Limit': 100,
    'Fields': 'RemoteTrailers,MediaSources',
}

def get_media_ids(params):
    items = []
    media = client.jellyfin.users('/Items', params=params)
    for item in media['Items']:
        items.append(item['Id'])
    media['Items'] = items
    return media

def get_movies_ids(start_index=0):
    params['StartIndex'] = start_index
    params['IncludeItemTypes'] = 'Movie'
    params['ParentId'] = app.config['MOVIES_ID']
    return get_media_ids(params)

def get_series_ids(start_index=0):
    params['StartIndex'] = start_index
    params['IncludeItemTypes'] = 'Series'
    params['ParentId'] = app.config['SERIES_ID']
    return get_media_ids(params)

def get_thumbnail(item_id):
    server_url = app.config['SERVER_URL']
    return f'{server_url}/Items/{item_id}/Images/Primary'

def get_movies(start_id=0):
    movies_ids = get_movies_ids(start_id)
    response = "{},{};".format(
        movies_ids['StartIndex'], movies_ids['TotalRecordCount']
    )
    for movie_id in movies_ids['Items']:
        movie = client.jellyfin.get_item(movie_id)
        trailer_url = ""
        if movie['RemoteTrailers']:
            trailer_url = movie['RemoteTrailers'][0]['Url']
        name = movie['Name']
        external_link = ""
        for external_url in movie['ExternalUrls']:
            if external_url['Name'] == 'IMDb':
                external_link = external_url['Url']
        dl_url = client.jellyfin.download_url(movie_id)
        stream_url = client.jellyfin.video_url(movie_id)
        img_url = get_thumbnail(movie_id)
        variables = [name, img_url, dl_url, stream_url, trailer_url, external_link]
        response += ','.join(variables) + ';'
    return response.rstrip(';')

def get_series(start_id=0):
    series_ids = get_series_ids()
    response = "{},{};".format(
        series_ids['StartIndex'], series_ids['TotalRecordCount']
    )
    for serie_id in series_ids['Items']:
        serie = client.jellyfin.get_item(serie_id)
        name = serie['Name']
        external_link = ""
        for external_url in serie['ExternalUrls']:
            if external_url['Name'] == 'IMDb':
                external_link = external_url['Url']
        img_url = get_thumbnail(serie_id)
        variables = [name, img_url, serie_id, external_link]
        response += ','.join(variables) + ';'
    return response.rstrip(';')

def get_seasons(serie_id):
    seasons = client.jellyfin.get_seasons(serie_id)
    response = "{},{};".format(
        seasons['StartIndex'], seasons['TotalRecordCount']
    )
    for season in seasons['Items']:
        name = season['Name']
        season_id = season['Id']
        img_url = get_thumbnail(season_id)
        variables = [name, img_url, season_id]
        response += ','.join(variables) + ';'
    return response.rstrip(';')

def get_episodes(serie_id, season_id):
    episodes = client.jellyfin.get_season(serie_id, season_id)
    response = "{},{};".format(
        episodes['StartIndex'], episodes['TotalRecordCount']
    )

    for episode in episodes['Items']:
        name = episode['Name']
        episode_id = episode['Id']
        img_url = get_thumbnail(episode_id)
        dl_url = client.jellyfin.download_url(episode_id)
        stream_url = client.jellyfin.video_url(episode_id)
        variables = [name, img_url, episode_id, dl_url, stream_url]
        response += ','.join(variables) + ';'
    return response.rstrip(';')

from key import Key, CollisionsList
import os


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

@app.route('/movies', methods=['POST'])
def movies():
    if check_perms(request.data):
        return get_movies()
    return access_denied()

@app.route('/series', methods=['POST'])
def series():
    if check_perms(request.data):
        return get_series()
    return access_denied()

@app.route('/series/<serie_id>', methods=['POST'])
def seasons(serie_id):
    if check_perms(request.data):
        return get_seasons(serie_id)
    return access_denied()

@app.route('/series/<serie_id>/<season_id>', methods=['POST'])
def episodes(serie_id, season_id):
    if check_perms(request.data):
        return get_episodes(serie_id, season_id)
    return access_denied()


if __name__ == '__main__':

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

    app.run(host='0.0.0.0', port=args.port)

    client.stop()

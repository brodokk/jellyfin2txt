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
import threading

from flask import request

from jellyfin2txt.key import Key
from jellyfin2txt.config import client, app, params, settings
from jellyfin2txt.media import Media
from jellyfin2txt.subtitle import Subtitle
from jellyfin2txt.utils import _read_keyfile

def check_perms(data: bytes) -> bool:
    """Check if the given data contains a valid and non-revoked authorization key.

    This function decodes a bytes object to a string and attempts to parse it as
    JSON object. It checks whether the JSON contains "auth_key" field, and if so,
    verifies that the key exists in a list of valid keys and has not been revoked.

    Args:
        data (bytes): The input data in bytes, expected to contain a JSON-encoded string.

    Returns:
        bool: Returns True if the data contains a valid, non-revoked authorization key;
              otherwise, returns False.
    """
    data_str: str = data.decode('utf-8')
    try:
        data_json: dict = json.loads(data_str)
        if "auth_key" in data_json.keys():
            keys: CollisionsList = _read_keyfile()
            if keys.contains('key', data_json['auth_key']):
                if not keys.get('key', data_json['auth_key']).revoked:
                    return True
                return False
            return False
        return False
    except json.decoder.JSONDecodeError:
        return False

def access_denied() -> (str, int):
    """Generate an access denied response.

    This function returns a tuple containing an error message and an HTTP status code,
    typically used when a user provides an invalid authorization key.

    Args:
        None

    Returns:
        tuple: A tuple where the first element is a string message ('Invalid auth_key!')
               and the second element is an integer representing the HTTP status code (403).
    """
    return 'Invalid auth_key!', 403

@app.route('/')
def index() -> str:
    """Render the home page of the API.

    This function handles the root URL of the web application and returns a simple HTML string
    describing the API and providing a link to the source code.

    Returns:
        str: An HTML string that provides information about the API and a link to its GitHub repository.
    """

    html: str = """
    <p>A simple api to make parsing easier on Resonite of a small part of the jellyfin API.</p>
    <p>Check the source code: <a href='https://github.com/brodokk/jellyfin2txt'>https://github.com/brodokk/jellyfin2txt</a></p>
    """
    return html

@app.route('/movies', methods=['POST'])
def movies() -> str:
    """Retrieve a list of movies.

    This function first checks if the request contains a valid and non-revoked authorization
    key If the authorization is successful, it retrieves and returns a list of movies based
    on the query parameters provided. If the authorization fails, it returns an access denied
    response.

    Query Parameters:
        StartIndex (int, optional): The starting index for the movies list (default is 0).
        Limit (int, optional): The maximum number of movies to return (default is 100).
        ThumbFillHeight (int, optional): The desired thumbnail height (default is 320).
        ThumbFillWidth (int, optional): The desired thumbnail width (default is 213).
        ThumbQuality (int, optional): The quality of the thumbnails (default is 96).
        tags (str, optional): A comma-separated list of tags to filter the movies (default is an empty string).

    Returns:
        str: A JSON-encoded string in a Resonite compatible format of movies if the authorization is valid, otherwise an access denied message.
    """
    if check_perms(request.data):
        return Media.movies(
            request.args.get("StartIndex", 0),
            request.args.get("Limit", 100),
            request.args.get("ThumbFillHeight", 320),
            request.args.get("ThumbFillWidth", 213),
            request.args.get("ThumbQuality", 96),
            request.args.get("tags", '').split(','),
        )
    return access_denied()

@app.route('/series', methods=['POST'])
def series() -> str:
    """Retrieve a list of TV shows.

    This function first checks if the request contains a valid and non-revoked authorization
    key If the authorization is successful, it retrieves and returns a list of TV shows based
    on the query parameters provided. If the authorization fails, it returns an access denied
    response.

    Query Parameters:
        StartIndex (int, optional): The starting index for the TV shows list (default is 0).
        Limit (int, optional): The maximum number of TV shows to return (default is 100).
        ThumbFillHeight (int, optional): The desired thumbnail height (default is 320).
        ThumbFillWidth (int, optional): The desired thumbnail width (default is 213).
        ThumbQuality (int, optional): The quality of the thumbnails (default is 96).
        tags (str, optional): A comma-separated list of tags to filter the TV shows (default is an empty string).

    Returns:
        str: A JSON-encoded string in a Resonite compatible format of TV shows if the authorization is valid, otherwise an access denied message.
    """
    if check_perms(request.data):
        return Media.series(
            request.args.get("StartIndex", 0),
            request.args.get("Limit", 100),
            request.args.get("ThumbFillHeight", 320),
            request.args.get("ThumbFillWidth", 213),
            request.args.get("ThumbQuality", 96),
            request.args.get("tags", '').split(','),
        )
    return access_denied()

@app.route('/series/<serie_id>', methods=['POST'])
def seasons(serie_id: str) -> str:
    """Retrieve a list of seasons for a specific TV show.

    This function first checks if the request contains a valid and non-revoked authorization
    key If the authorization is successful, it retrieves and returns the list of seasons for
    the specified TV show. If the authorization fails, it returns an access denied response.

    Args:
        serie_id (str): The unique identifier for the TV show.

    Returns:
        str: A JSON-encoded string in a Resonite compatible format of the list of seasons for
             the specified TV show if the authorization is valid, otherwise an access denied message.
    """
    if check_perms(request.data):
        return Media.seasons(serie_id)
    return access_denied()

@app.route('/series/<serie_id>/<season_id>', methods=['POST'])
def episodes(serie_id: str, season_id: str) -> str:
    """Retrieve a list of episodes for a specific season of a TV show.

    This function first checks if the request contains a valid and non-revoked authorization
    key If the authorization is successful, it retrieves and returns the list episodes of the
    specified seasons of a TV show. If the authorization fails, it returns an access denied response.

    Args:
        serie_id (str): The unique identifier for the TV show.
        season_id (str): The unique identifier for the season within the specified TV show.

    Returns:
        str: A JSON-encoded string in a Resonite compatible format of the list of episodes of
             the specified seasons for of a TV show if the authorization is valid, otherwise an
             access denied message.
    """
    if check_perms(request.data):
        return Media.episodes(serie_id, season_id)
    return access_denied()

@app.route('/subtitles/<item_id>', methods=['POST'])
def subtitles(item_id: str) -> str:
    """Retrieve a list of subtitles for a specific media.

    This function first checks if the request contains a valid and non-revoked authorization
    key If the authorization is successful, it retrieves and returns the list subtitles for
    the media. If the authorization fails, it returns an access denied response.

    Args:
        item_id (str): The unique identifier for the media.

    Returns:
        str: A JSON-encoded string in a Resonite compatible format of the list of the subtitles
             for a specific media if the authorization is valid, otherwise an access denied message.
    """
    if check_perms(request.data):
        return Subtitle.subtitles(item_id)
    return access_denied()

@app.route('/subtitles/<item_id>/<subtitle_name>', methods=['POST'])
def subtitle(item_id: str, subtitle_name: str) -> str:
    """Retrieve a specific subtitle for a media.

    This function first checks if the request contains a valid and non-revoked authorization
    key If the authorization is successful, it retrieves and returns the subtitle access URL
    of the media based on it's name. If the authorization fails, it returns an access denied
    response.

    Args:
        item_id (str): The unique identifier for the media.
        subtitle_name (str): The name of the subtitle for the media.

    Returns:
        str: A JSON-encoded string in a Resonite compatible format of the list of the subtitles
             for a specific media if the authorization is valid, otherwise an access denied message.
    """
    if check_perms(request.data):
        return Subtitle.subtitle(item_id, subtitle_name)
    return access_denied()

@app.route('/subtitles/<item_id>/<subtitle_name>/extract', methods=['POST'])
def subtitle_extract(item_id: str, subtitle_name: str) -> str:
    """Extract subtitle from a media.

    This function first checks if the request contains a valid and non-revoked authorization
    key. If authorization is successful, it starts the extraction process for the subtitle
    with the specified name for the media and returns a status indicating whether the
    extraction job was successfully started. If the authorization fails, it returns an
    access denied response.

    Args:
        item_id (str): The unique identifier for the media.
        subtitle_name (str): The name of the subtitle for the media.

    Returns:
        str: A status message indicating whether the extraction job was successfully started
              or if there was an issue (e.g., "Extraction job started" or "Failed to start
              extraction"), or an access denied message if the authorization fails.
    """
    if check_perms(request.data):
        return Subtitle.subtitle_extract(item_id, subtitle_name)
    return access_denied()

@app.route('/subtitles/<item_id>/discover', methods=['POST'])
def subtitle_discover(item_id: str) -> str:
    """Generate external subtitle list.

    This will also start the task to make this subtitle available.

    Args:
        item_id (str): The Jellyfin media id.

    Returns:
        str: The list of external subtitles available for this Jellyfin media.
    """
    if check_perms(request.data):
        return Subtitle.subtitle_discover(item_id)
    return access_denied()

@app.route('/subtitles/<item_id>/all', methods=['POST'])
def subtitles_all(item_id: str) -> str:
    if check_perms(request.data):
        return Subtitle.subtitles_all(item_id)
    return access_denied()

@app.route('/subtitles/<item_id>/<subtitle_name>/extract/status', methods=['POST'])
def subtitle_extract_status(item_id: str, subtitle_name: str) -> str:
    if check_perms(request.data):
        return Subtitle.subtitle_extract_status(item_id, subtitle_name)
    return access_denied()

@app.route('/extract_status', methods=['POST'])
def extract_status() -> str:
    if check_perms(request.data):
        return Subtitle.extract_status()
    return access_denied()

def main() -> None:
    parser: ArgumentParser = argparse.ArgumentParser()
    parser.add_argument(
        '--port', type=int, default=5000,
        help='Port to use, default 5000')
    parser.add_argument(
        '--debug', action='store_true',
        help='Make the server verbose')
    args: Namespace = parser.parse_args()

    import logging

    if args.debug:
        loggers: dict = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
        for logger in loggers:
            logger.setLevel(logging.DEBUG)

    media_folders: dict = client.jellyfin.get_media_folders()
    item_ids: list = []
    items: dict = {}

    for item in media_folders['Items']:
        item_ids.append(item['Id'])
        items[item['Name']]: str = item['Id']

    def item_not_found(item, key):
        logging.error('{} ({}) not found in:'.format(item, key))
        for item_name, item_id in items.items():
            logging.error('{}: {}'.format(item_name, item_id))
        sys.exit(1)

    if not app.config.get('MOVIES_ID'):
        if app.config.get('MOVIES') not in items.keys():
            item_not_found('MOVIES', app.config.get('MOVIES'))
        else:
            client.movies_id: str = items[app.config['MOVIES']]
    if not app.config.get('SERIES_ID'):
        if app.config.get('SERIES') not in items.keys():
            item_not_found('SERIES', app.config.get('SERIES'))
        else:
            client.series_id: str = items[app.config['SERIES']]
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

    task: Thread = threading.Thread(
        target=Subtitle.subtitle_extract_thread
    )
    task.start()

    app.run(host='0.0.0.0', port=args.port)

    client.stop()

if __name__ == '__main__':
    main()
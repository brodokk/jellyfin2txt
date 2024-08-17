#!/bin/python

import sys
import json
from argparse import (
    ArgumentParser,
    Namespace,
)
from threading import Thread

from flask import request

from jellyfin2txt.key import KeysValidator
from jellyfin2txt.config import (
    client,
    app,
)
from jellyfin2txt.media import Media
from jellyfin2txt.subtitle import Subtitle
from jellyfin2txt.utils import _read_keyfile

def check_perms(data: bytes) -> bool:
    """Validate the authorization key in JSON data.

    Decodes a bytes object to a string and attempts to parse it as
    JSON. It checks for the presence of an "auth_key" field. validating the
    key as existing and non-revoked based on an internal list.

    The key list is stored in a file named `keyfile.json`.

    :param data: The input data containing a JSON-encoded string.

    :returns:
        Possible values:
            - True: If the data contains a valid, non-revoked authorization key.
            - False:  If the data contains an invalid, revoked or if the JSON parsing fails.
    """
    data_str: str = data.decode('utf-8')
    try:
        data_json: dict = json.loads(data_str)
        if "auth_key" in data_json.keys():
            keys: KeysValidator = _read_keyfile()
            if keys.contains('key', data_json['auth_key']):
                if not keys.get('key', data_json['auth_key']).revoked:
                    return True
                return False
            return False
        return False
    except json.decoder.JSONDecodeError:
        return False

def access_denied() -> (str, int):
    """Build HTTP access denied response.

    Typically used to respond to requests with invalid authentication keys.

    :returns:
        A tuple containing:
            - :py:class:`str`: The error message 'Invalid auth_key!'.
            - :py:class:`int`: The HTTP Status code 403 (Forbidden).
    """
    return 'Invalid auth_key!', 403

@app.route('/')
def index() -> str:
    """Render the index page for the API.

    Handles the root URL of the web application and returns a simple HTML string
    describing the API and providing a link to the source code.

    :returns:
        The HTML content.
    """

    html: str = """
    <p>A simple api to make parsing easier on Resonite of a small part of the jellyfin API.</p>
    <p>Check the source code: <a href='https://github.com/brodokk/jellyfin2txt'>https://github.com/brodokk/jellyfin2txt</a></p>
    """
    return html

@app.route('/movies', methods=['POST'])
def movies() -> str:
    """Retrieve a list of movies.

    First checks if the request contains a valid and non-revoked authorization key.
    If the authorization is successful, it retrieves and returns a list of movies based
    on the query parameters provided. If the authorization fails, it returns access denied
    response.

    QUERY PARAMETERS:
        - StartIndex (:py:class:`int`, optional): The starting index for the movies list (default: 0).
        - Limit (:py:class:`int`, optional): The maximum number of movies to return (default: 100).
        - ThumbFillHeight (:py:class:`int`, optional): The desired thumbnail height (default: 320).
        - ThumbFillWidth (:py:class:`int`, optional): The desired thumbnail width (default: 213).
        - ThumbQuality (:py:class:`int`, optional): The quality of the thumbnails (default: 96).
        - tags (:py:class:`str`, optional): A comma-separated list of tags to filter the movies (default: '').

    :returns:
        A JSON-encoded string in a Resonite compatible format of movies if the authorization is valid, otherwise an access denied message.
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

    First checks if the request contains a valid and non-revoked authorization key.
    If the authorization is successful, it retrieves and returns a list of TV shows based
    on the query parameters provided. If the authorization fails, it returns an access denied
    response.

    QUERY PARAMETERS:
        - StartIndex (:py:class:`int`, optional): The starting index for the TV shows list (default: 0).
        - Limit (:py:class:`int`, optional): The maximum number of TV shows to return (default: 100).
        - ThumbFillHeight (:py:class:`int`, optional): The desired thumbnail height (default: 320).
        - ThumbFillWidth (:py:class:`int`, optional): The desired thumbnail width (default: 213).
        - ThumbQuality (:py:class:`int`, optional): The quality of the thumbnails (default: 96).
        - tags (:py:class:`str`, optional): A comma-separated list of tags to filter the TV shows
        (default is an empty string).

    :returns:
        A JSON-encoded string in a Resonite compatible format of TV shows if the authorization is valid
        otherwise an access denied message.
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

    First checks if the request contains a valid and non-revoked authorization key.
    If the authorization is successful, it retrieves and returns the list of seasons for
    the specified TV show. If the authorization fails, it returns an access denied response.

    :param serie_id: The unique identifier for the TV show.

    Returns:
        A JSON-encoded string in a Resonite compatible format of the list of seasons for
        the specified TV show if the authorization is valid, otherwise an access denied message.
    """
    if check_perms(request.data):
        return Media.seasons(serie_id)
    return access_denied()

@app.route('/series/<serie_id>/<season_id>', methods=['POST'])
def episodes(serie_id: str, season_id: str) -> str:
    """Retrieve a list of episodes for a specific season of a TV show.

    First checks if the request contains a valid and non-revoked authorization
    key If the authorization is successful, it retrieves and returns the list episodes of the
    specified seasons of a TV show. If the authorization fails, it returns an access denied response.

    :param serie_id: The unique identifier for the TV show.
    :param season_id: The unique identifier for the season within the specified TV show.

    :returns:
        A JSON-encoded string in a Resonite compatible format of the list of episodes of
        the specified seasons for of a TV show if the authorization is valid, otherwise
        access denied message.
    """
    if check_perms(request.data):
        return Media.episodes(serie_id, season_id)
    return access_denied()

@app.route('/subtitles/<item_id>', methods=['POST'])
def subtitles(item_id: str) -> str:
    """Retrieve a list of subtitles for a specific media.

    First checks if the request contains a valid and non-revoked authorization
    key If the authorization is successful, it retrieves and returns the list subtitles for
    the media. If the authorization fails, it returns access denied response.
    This return the subtitles available on the Jellyfin server only.

    :param item_id: The unique identifier for the media.

    :returns:
        A JSON-encoded string in a Resonite compatible format of the list of the subtitles
        for a specific media if the authorization is valid, otherwise an access denied message.
    """
    if check_perms(request.data):
        return Subtitle.subtitles(item_id)
    return access_denied()

@app.route('/subtitles/<item_id>/<subtitle_name>', methods=['POST'])
def subtitle(item_id: str, subtitle_name: str) -> str:
    """Retrieve a specific cached subtitle for a media.

    First checks if the request contains a valid and non-revoked authorization
    key If the authorization is successful, it retrieves and returns the subtitle access URL
    of the media based on its name. If the authorization fails, it returns an access denied
    response.

    :param item_id: The unique identifier for the media.
    :param subtitle_name: The name of the subtitle for the media.

    :returns:
        A JSON-encoded string in a Resonite compatible format of the list of the subtitles
        for a specific media if the authorization is valid, otherwise an access denied message.
    """
    if check_perms(request.data):
        return Subtitle.subtitle(item_id, subtitle_name)
    return access_denied()

@app.route('/subtitles/<item_id>/<subtitle_name>/extract', methods=['POST'])
def subtitle_extract(item_id: str, subtitle_name: str) -> str:
    """Extract and cache subtitle from a media.

    First checks if the request contains a valid and non-revoked authorization
    key. If authorization is successful, it starts the extraction process for the subtitle
    with the specified name for the media and returns a status indicating whether the
    extraction job was successfully started. If the authorization fails, it returns an
    access denied response.

    :param item_id: The unique identifier for the media.
    :param subtitle_name: The name of the subtitle for the media.

    returns:
        A status message indicating whether the extraction job was successfully started
        or if there was an issue (e.g., "Extraction job started" or "Failed to start
        extraction"), or an access denied message if the authorization fails.
    """
    if check_perms(request.data):
        return Subtitle.subtitle_extract(item_id, subtitle_name)
    return access_denied()

@app.route('/subtitles/<item_id>/discover', methods=['POST'])
def subtitle_discover(item_id: str) -> str:
    """Discover and cache the best subtitle available for a media.

    First checks if the request contains a valid and non-revoked authorization key.
    If the authorization is successful, it starts the extraction process for the subtitles
    of the media. If the authorization fails, it returns an access denied response.
    The caching will be done in a separate thread.

    :param item_id: The unique identifier for the media.

    :returns:
        The list of external subtitles available for this Jellyfin media.
    """
    if check_perms(request.data):
        return Subtitle.subtitle_discover(item_id)
    return access_denied()

@app.route('/subtitles/<item_id>/all', methods=['POST'])
def subtitles_all(item_id: str) -> str:
    """Retrieve the list of cached subtitles for a media.

    First checks if the request contains a valid and non-revoked authorization key.
    If the authorization is successful, it retrieves and returns the list of cached
    subtitles for the media. If the authorization fails, it returns an access denied
    response.

    :params item_id: The unique identifier for the media.

    :returns:
        The list of cached subtitles in a Resonite compatible format.
    """
    if check_perms(request.data):
        return Subtitle.subtitles_all(item_id)
    return access_denied()

@app.route('/subtitles/<item_id>/<subtitle_name>/extract/status', methods=['POST'])
def subtitle_extract_status(item_id: str, subtitle_name: str) -> str:
    """Return the extraction status for a cached subtitle.

    First checks if the request contains a valid and non-revoked authorization key.
    If the authorization is successful, it returns the extraction status for the
    subtitle with the specified name for the media. If the authorization fails, it
    returns an access denied response.

    :params item_id: The unique identifier for the media.
    :params subtitle_name: The name of the subtitle for the media.

    :returns:
        The extraction status in a Resonite compatible format.
    """
    if check_perms(request.data):
        return Subtitle.subtitle_extract_status(item_id, subtitle_name)
    return access_denied()

@app.route('/extract_status', methods=['POST'])
def extract_status() -> str:
    """Return all the extraction status for all cached subtitles.

    First checks if the request contains a valid and non-revoked authorization key.
    If the authorization is successful, it returns the extraction status for all
    cached subtitles. If the authorization fails, it returns an access denied response.

    :returns:
        A list of extraction status in a Resonite compatible format.
    """
    if check_perms(request.data):
        return Subtitle.extract_status()
    return access_denied()

def main() -> None:
    parser: ArgumentParser = ArgumentParser()
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

    task: Thread = Thread(
        target=Subtitle.subtitle_extract_thread
    )
    task.start()

    app.run(host='0.0.0.0', port=args.port)

    client.stop()

if __name__ == '__main__':
    main()
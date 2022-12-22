#!/bin/python

from typing import Optional
from cleanit import Config as cleanitConfig
from cleanit import Subtitle as cleanitSubtitle
from cleanit.rule import Change
import tempfile
import urllib.request
import os
from pathlib import Path
import urllib.request
from pyasstosrt import Subtitle as pyasstosrtSubtitle
import tempfile
import os
from pathlib import Path

import os
import sys
import json
import toml
import uuid
import argparse
import logging
from itertools import cycle

from flask import Flask, request

from jellyfin_apiclient_python.client import JellyfinClient

from key import Key, CollisionsList

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

def get_movies_ids(start_index=0, limit=100):
    params['StartIndex'] = start_index
    params['Limit'] = limit
    params['IncludeItemTypes'] = 'Movie'
    params['ParentId'] = client.movies_id
    return get_media_ids(params)

def get_series_ids(start_index=0, limit=100):
    params['StartIndex'] = start_index
    params['Limit'] = limit
    params['IncludeItemTypes'] = 'Series'
    params['ParentId'] = client.series_id
    return get_media_ids(params)

def get_thumbnail(item_id, fillHeight=320, fillWidth=213, quality=96):
    server_url = app.config['SERVER_URL']
    return (
        f'{server_url}/Items/{item_id}/Images/Primary?fillHeight={fillHeight}'
        f'&fillWidth={fillWidth}&quality={quality}'
    )

def get_movies(
    start_index=0, limit=100, thumb_fill_height=320, thumb_fill_width=213,
    thumb_quality=96
):
    movies_ids = get_movies_ids(start_index, limit)
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
        img_url = get_thumbnail(movie_id, thumb_fill_height, thumb_fill_width, thumb_quality)
        variables = [name, img_url, dl_url, stream_url, trailer_url, external_link]
        response += ','.join(variables) + ';'
    return response.rstrip(';')

def get_series(
    start_index=0, limit=100, thumb_fill_height=320, thumb_fill_width=213,
    thumb_quality=96
):
    series_ids = get_series_ids(start_index, limit)
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
        img_url = get_thumbnail(serie_id, thumb_fill_height, thumb_fill_width, thumb_quality)
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

subtitles_output_folder = Path("subtitles")

def download(item_id, name):
    data = client.jellyfin.download_url(item_id)

    from time import sleep
    from urllib.request import urlopen

    from rich.progress import wrap_file

    from functools import partial

    response = urlopen(data)
    size = int(response.headers["Content-Length"])

    
    from rich.progress import (
        BarColumn,
        DownloadColumn,
        Progress,
        TaskID,
        TextColumn,
        TimeRemainingColumn,
        TransferSpeedColumn,
    )

    from threading import Event

    import signal

    progress = Progress(
        TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        DownloadColumn(),
        "•",
        TransferSpeedColumn(),
        "•",
        TimeRemainingColumn(),
    )

    done_event = Event()


    def handle_sigint(signum, frame):
        done_event.set()


    #signal.signal(signal.SIGINT, handle_sigint)

    with progress:
        task_id = progress.add_task('download', filename=name, total=size, start=False)
        with open(name, 'wb') as dest_file:
            progress.start_task(task_id)
            for dat in iter(partial(response.read, 32768), b''):
                dest_file.write(dat)
                progress.update(task_id, advance=len(dat))
                if done_event.is_set():
                    exit(1)

    #with urllib.request.urlopen(data) as f:
    #    html = f.read().decode('utf-8')
    return name

def clean_sub(sub_file, final_filename):
    sub = cleanitSubtitle(sub_file)
    cfg = cleanitConfig()
    rules = cfg.select_rules(tags={'no-style', 'ocr', 'tidy', 'no-spam'})
    if sub.clean(rules):
        sub.save(f"{subtitles_output_folder/final_filename}")

def get_subtitles(item_id):
    profile = {
            "Name": "Kodi",
            "MusicStreamingTranscodingBitrate": 1280000,
            "TimelineOffsetSeconds": 5,
            "ResponseProfiles": [],
            "ContainerProfiles": [],
            "CodecProfiles": [],
            "SubtitleProfiles": [
                {
                    "Format": "srt",
                    "Method": "External"
                },
                {
                    "Format": "sub",
                    "Method": "External"
                },
                {
                    "Format": "ssa",
                    "Method": "External"
                },
                {
                    "Format": "ttml",
                    "Method": "External"
                },
                {
                    "Format": "vtt",
                    "Method": "External"
                }
            ]
        }
    
    #item_id='24b6d39b4779259fda28d856e9479b66' # psg quick
    item_id='ce096db83d3454055cf0b5315284c947' # pgs slow: a lot
    #item_id='32b81e45fa24eef35b6305bbd5c2329a'
    #item_id='c792916f205221d1d84c73baad5e9814'
    data = client.jellyfin.get_play_info(
        item_id=item_id,
        profile=profile
    )
    name = data['MediaSources'][0]['Path'].split('/')[-1]

    subtitles = []

    subtitles_file_supported = ['subrip', 'ass', 'PGSSUB', 'mov_text']
    neos_converted_subtitles_file_supported = ['ass', 'mov_text']
    neos_extracted_subtitles_file_supported = ['PGSSUB']
    
    for media in data['MediaSources'][0]['MediaStreams']:
        if media['Type'] == 'Subtitle':
            format_supported = False
            codec = media["Codec"]
            if codec in subtitles_file_supported:
                format_supported = True
                if media['IsExternal'] or media['IsTextSubtitleStream'] or media['SupportsExternalStream']:
                    url = f"{app.config['SERVER_URL']}{media['DeliveryUrl']}"
                    if codec not in neos_converted_subtitles_file_supported:
                            format_supported = False
                elif  media['Codec'] not in neos_extracted_subtitles_file_supported:
                    format_supported = False           
                    
            if format_supported:
                subtitles.append(media['DisplayTitle'])
            else:
                print(f'Warning format {codec} not suported for item id {item_id}')
                if media['IsExternal'] or media['IsTextSubtitleStream'] or media['SupportsExternalStream']:
                    print('This format seems to be easly convertable in srt')
                url = f"{app.config['SERVER_URL']}{media['DeliveryUrl']}"
                print(url)
            
    for subtitle in subtitles:
        print(subtitle)
    return subtitles

def get_subtitle(item_id, subtitle_name):
    profile = {
            "Name": "Kodi",
            "MusicStreamingTranscodingBitrate": 1280000,
            "TimelineOffsetSeconds": 5,
            "ResponseProfiles": [],
            "ContainerProfiles": [],
            "CodecProfiles": [],
            "SubtitleProfiles": [
                {
                    "Format": "srt",
                    "Method": "External"
                },
                {
                    "Format": "sub",
                    "Method": "External"
                },
                {
                    "Format": "ssa",
                    "Method": "External"
                },
                {
                    "Format": "ttml",
                    "Method": "External"
                },
                {
                    "Format": "vtt",
                    "Method": "External"
                }
            ]
        }
    
    item_id='24b6d39b4779259fda28d856e9479b66' # psg quick
    #item_id='ce096db83d3454055cf0b5315284c947' # pgs slow: a lot
    #item_id='32b81e45fa24eef35b6305bbd5c2329a'
    #item_id='c792916f205221d1d84c73baad5e9814'
    data = client.jellyfin.get_play_info(
        item_id=item_id,
        profile=profile
    )
    name = data['MediaSources'][0]['Path'].split('/')[-1]

    subtitles_file_supported = ['subrip', 'ass', 'PGSSUB', 'mov_text']
    neos_subtitles_file_supported = ['subrip']
    
    for media in data['MediaSources'][0]['MediaStreams']:
        format_supported = False
        if media['Type'] == 'Subtitle':
            if media['DisplayTitle'] != subtitle_name:
                print('incorrect name')
            if media['Codec'] not in subtitles_file_supported:
                print('incorrect codec')
            codec = media["Codec"]
            final_filename = Path(f"{name.replace('/', '')}.{media['DisplayTitle'].replace('/', '')}.srt")
            if media['IsExternal'] or media['IsTextSubtitleStream'] or media['SupportsExternalStream']:
                url = f"{app.config['SERVER_URL']}{media['DeliveryUrl']}"
                if codec not in neos_subtitles_file_supported:
                    if codec == 'ass':
                        with tempfile.NamedTemporaryFile() as sub_temp_file:
                            urllib.request.urlretrieve(url, sub_temp_file.name)
                            sub = pyasstosrtSubtitle(sub_temp_file.name)
                            tmp_filename = sub_temp_file.name.split('/')[-1]
                            sub.export(output_dir=subtitles_output_folder)
                            os.replace(f"{subtitles_output_folder/tmp_filename}.srt", f"{subtitles_output_folder/final_filename}")
                    elif codec == 'mov_text':
                        with tempfile.NamedTemporaryFile() as sub_temp_file:
                            urllib.request.urlretrieve(url, sub_temp_file.name)
                            clean_sub(sub_temp_file.name, final_filename)
                    else:
                        format_supported = False
                format_supported = True
            elif  media['Codec'] == 'PGSSUB':
                print('go pgsrip')
                with tempfile.TemporaryDirectory(dir='tmp') as sub_temp_dir:
                    #urllib.request.urlretrieve(url, sub_temp_dir)
                    #clean_sub(sub_temp_file.name, final_filename)
                    sub_temp_file = download(item_id, Path(sub_temp_dir) / Path(name))
                    from sh import pgsrip
                    from pgsrip import pgsrip, Mkv, Options
                    from babelfish import Language

                    media_file = Mkv(sub_temp_file)
                    options = Options(languages={Language('eng')}, overwrite=True, one_per_lang=False)
                    pgsrip.rip(media_file, options)
                    from sh import ls

                    print(ls('-alh', sub_temp_dir))
                    print(sub_temp_file)
                    #print(sub_temp_file)
                    #import time
                    #time.sleep(10000)
                    #pgsrip('-a', sub_temp_file)

                    for entry in Path(sub_temp_dir).iterdir():
                        if entry.is_file() and entry.suffix == '.srt':
                            print(entry.stem.replace('/', ''))
                            final_filename = Path(f"{entry.stem.replace('/', '')}.srt")
                            clean_sub(sub_temp_file, f"{subtitles_output_folder/final_filename}")
                            url = 'uwu'
                # for extract pgsrip use https://github.com/ratoaq2/pgsrip
            else:
                format_supported = False           
                
            if format_supported:
                print(media)
                print(url)
                print(subtitles)
                print(media['DisplayTitle'])
                return url
            else:
                print(f"Warning format {media['DisplayTitle']} {codec} not suported for item id {item_id}")
                if media['IsExternal'] or media['IsTextSubtitleStream'] or media['SupportsExternalStream']:
                    print('This format seems to be easly convertable in srt')
                url = f"{app.config['SERVER_URL']}{media['DeliveryUrl']}"
                print(url)

        print("err")
    
    return "Invalid id?"

def get_subtitles_old(item_id):
    profile = {
            "Name": "Kodi",
            "MusicStreamingTranscodingBitrate": 1280000,
            "TimelineOffsetSeconds": 5,
            "ResponseProfiles": [],
            "ContainerProfiles": [],
            "CodecProfiles": [],
            "SubtitleProfiles": [
                {
                    "Format": "srt",
                    "Method": "External"
                },
                {
                    "Format": "sub",
                    "Method": "External"
                },
                {
                    "Format": "ssa",
                    "Method": "External"
                },
                {
                    "Format": "ttml",
                    "Method": "External"
                },
                {
                    "Format": "vtt",
                    "Method": "External"
                }
            ]
        }
    
    #item_id='24b6d39b4779259fda28d856e9479b66' # psg quick
    #item_id='ce096db83d3454055cf0b5315284c947' # pgs slow: a lot
    #item_id='32b81e45fa24eef35b6305bbd5c2329a'
    #item_id='c792916f205221d1d84c73baad5e9814'
    data = client.jellyfin.get_play_info(
        item_id=item_id,
        profile=profile
    )
    print(data['MediaSources'][0]['Name'])
    name = data['MediaSources'][0]['Path'].split('/')[-1]

    subtitles = []

    subtitles_file_supported = ['subrip', 'ass', 'PGSSUB', 'mov_text']
    neos_subtitles_file_supported = ['subrip']
    
    for media in data['MediaSources'][0]['MediaStreams']:
        if media['Type'] == 'Subtitle':
            format_supported = False
            codec = media["Codec"]
            if codec in subtitles_file_supported:
                format_supported = True
                final_filename = Path(f"{name.replace('/', '')}.{media['DisplayTitle'].replace('/', '')}.srt")
                if media['IsExternal'] or media['IsTextSubtitleStream'] or media['SupportsExternalStream']:
                    index = media["Index"]
                    #url = f"{app.config['SERVER_URL']}/Videos/{item_id}/{item_id}/Subtitles/{index}/0/Stream.{codec}"
                    url = f"{app.config['SERVER_URL']}{media['DeliveryUrl']}"
                    if codec not in neos_subtitles_file_supported:
                        if codec == 'ass':
                            with tempfile.NamedTemporaryFile() as sub_temp_file:
                                urllib.request.urlretrieve(url, sub_temp_file.name)
                                sub = pyasstosrtSubtitle(sub_temp_file.name)
                                tmp_filename = sub_temp_file.name.split('/')[-1]
                                sub.export(output_dir=subtitles_output_folder)
                                os.replace(f"{subtitles_output_folder/tmp_filename}.srt", f"{subtitles_output_folder/final_filename}")
                        elif codec == 'mov_text':
                            with tempfile.NamedTemporaryFile() as sub_temp_file:
                                urllib.request.urlretrieve(url, sub_temp_file.name)
                                clean_sub(sub_temp_file.name, final_filename)
                        else:
                            format_supported = False
                elif  media['Codec'] == 'PGSSUB':
                    print('go pgsrip')
                    with tempfile.TemporaryDirectory(dir='tmp') as sub_temp_dir:
                        #urllib.request.urlretrieve(url, sub_temp_dir)
                        #clean_sub(sub_temp_file.name, final_filename)
                        sub_temp_file = download(item_id, Path(sub_temp_dir) / Path(name))
                        from sh import pgsrip
                        from pgsrip import pgsrip, Mkv, Options
                        from babelfish import Language

                        media_file = Mkv(sub_temp_file)
                        options = Options(languages={Language('eng')}, overwrite=True, one_per_lang=False)
                        pgsrip.rip(media_file, options)
                        from sh import ls

                        print(ls('-alh', sub_temp_dir))
                        print(sub_temp_file)
                        #print(sub_temp_file)
                        #import time
                        #time.sleep(10000)
                        #pgsrip('-a', sub_temp_file)

                        for entry in Path(sub_temp_dir).iterdir():
                            if entry.is_file() and entry.suffix == '.srt':
                                print(entry.stem.replace('/', ''))
                                final_filename = Path(f"{entry.stem.replace('/', '')}.srt")
                                clean_sub(sub_temp_file, f"{subtitles_output_folder/final_filename}")
                                url = 'uwu'
                    # for extract pgsrip use https://github.com/ratoaq2/pgsrip
                else:
                    format_supported = False           
                    
            if format_supported:
                print(media)
                print(url)
                print(subtitles)
                print(media['DisplayTitle'])
                subtitles.append(f"{media['DisplayTitle']}`{url}")
            else:
                print(f'Warning format {codec} not suported for item id {item_id}')
                if media['IsExternal'] or media['IsTextSubtitleStream'] or media['SupportsExternalStream']:
                    print('This format seems to be easly convertable in srt')
                url = f"{app.config['SERVER_URL']}{media['DeliveryUrl']}"
                print(url)
            
    for subtitle in subtitles:
        print(subtitle)
    return subtitles





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
        return get_movies(
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
        return get_series(
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
        return get_seasons(serie_id)
    return access_denied()

@app.route('/series/<serie_id>/<season_id>', methods=['POST'])
def episodes(serie_id, season_id):
    if check_perms(request.data):
        return get_episodes(serie_id, season_id)
    return access_denied()

@app.route('/subtitles/<item_id>', methods=['POST'])
def subtitles(item_id):
    if check_perms(request.data):
        return get_subtitles(item_id)
    return access_denied()

@app.route('/subtitles/<item_id>/<subtitle_name>', methods=['POST'])
def subtitle(item_id, subtitle_name):
    if check_perms(request.data):
        return get_subtitle(item_id, subtitle_name)
    return access_denied()

USER_APP_NAME = "Jellyfin2txt"

class Settings:
  transcode_h265 = False
  remote_kbps: int = 10000
  local_kbps: int = 2147483
  transcode_hi10p: bool = False
  always_transcode: bool = False
  transcode_to_h265: bool = False

settings = Settings()


def get_profile(
    is_remote: bool = False,
    video_bitrate: Optional[int] = None,
    force_transcode: bool = False,
    is_tv: bool = False,
):
    if video_bitrate is None:
        if is_remote:
            video_bitrate = settings.remote_kbps
        else:
            video_bitrate = settings.local_kbps

    if settings.transcode_h265:
        transcode_codecs = "h264,mpeg4,mpeg2video"
    elif settings.transcode_to_h265:
        transcode_codecs = "h265,hevc,h264,mpeg4,mpeg2video"
    else:
        transcode_codecs = "h264,h265,hevc,mpeg4,mpeg2video"

    profile = {
        "Name": USER_APP_NAME,
        "MaxStreamingBitrate": video_bitrate * 1000,
        "MaxStaticBitrate": video_bitrate * 1000,
        "MusicStreamingTranscodingBitrate": 1280000,
        "TimelineOffsetSeconds": 5,
        "TranscodingProfiles": [
            {"Type": "Audio"},
            {
                "Container": "ts",
                "Type": "Video",
                "Protocol": "hls",
                "AudioCodec": "aac,mp3,ac3,opus,flac,vorbis",
                "VideoCodec": transcode_codecs,
                "MaxAudioChannels": "6",
            },
            {"Container": "jpeg", "Type": "Photo"},
        ],
        "DirectPlayProfiles": [{"Type": "Video"}, {"Type": "Audio"}, {"Type": "Photo"}],
        "ResponseProfiles": [],
        "ContainerProfiles": [],
        "CodecProfiles": [],
        "SubtitleProfiles": [
            {"Format": "srt", "Method": "External"},
            {"Format": "srt", "Method": "Embed"},
            {"Format": "ass", "Method": "External"},
            {"Format": "ass", "Method": "Embed"},
            {"Format": "sub", "Method": "Embed"},
            {"Format": "sub", "Method": "External"},
            {"Format": "ssa", "Method": "Embed"},
            {"Format": "ssa", "Method": "External"},
            {"Format": "smi", "Method": "Embed"},
            {"Format": "smi", "Method": "External"},
            # Jellyfin currently refuses to serve these subtitle types as external.
            {"Format": "pgssub", "Method": "Embed"},
            # {
            #    "Format": "pgssub",
            #    "Method": "External"
            # },
            {"Format": "dvdsub", "Method": "Embed"},
            # {
            #    "Format": "dvdsub",
            #    "Method": "External"
            # },
            {"Format": "pgs", "Method": "Embed"},
            # {
            #    "Format": "pgs",
            #    "Method": "External"
            # }
        ],
    }

    if settings.transcode_hi10p:
        profile["CodecProfiles"].append(
            {
                "Type": "Video",
                "codec": "h264",
                "Conditions": [
                    {
                        "Condition": "LessThanEqual",
                        "Property": "VideoBitDepth",
                        "Value": "8",
                    }
                ],
            }
        )

    if settings.always_transcode or force_transcode:
        profile["DirectPlayProfiles"] = []

    if is_tv:
        profile["TranscodingProfiles"].insert(
            0,
            {
                "Container": "ts",
                "Type": "Video",
                "AudioCodec": "mp3,aac",
                "VideoCodec": "h264",
                "Context": "Streaming",
                "Protocol": "hls",
                "MaxAudioChannels": "2",
                "MinSegments": "1",
                "BreakOnNonKeyFrames": True,
            },
        )

    return profile

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

    #get_subtitles('f17589e06f4724ed4d416449efe51b8a')
    #exit()

    app.run(host='0.0.0.0', port=args.port)

    client.stop()


import os
from pathlib import Path
from cleanit import Config as cleanitConfig
from cleanit import Subtitle as cleanitSubtitle
from pyasstosrt import Subtitle as pyasstosrtSubtitle
import tempfile

from jellyfin2txt.config import client, app

class Subtitle:
    subtitles_output_folder = Path("subtitles")

    @staticmethod
    def subtitles(item_id):
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

    @staticmethod
    def clean_sub(sub_file, final_filename):
        sub = cleanitSubtitle(sub_file)
        cfg = cleanitConfig()
        rules = cfg.select_rules(tags={'no-style', 'ocr', 'tidy', 'no-spam'})
        if sub.clean(rules):
            sub.save(f"{subtitles_output_folder/final_filename}")


    @staticmethod
    def subtitle(item_id, subtitle_name):
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
                        sub_temp_file = Subtitle.download(item_id, Path(sub_temp_dir) / Path(name))
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

    @staticmethod
    def subtitles_old(item_id):
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
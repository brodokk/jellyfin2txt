import os
import urllib
import psutil
from urllib.request import urlopen
from functools import partial
from pathlib import Path
from cleanit import Config as cleanitConfig
from cleanit import Subtitle as cleanitSubtitle
from pyasstosrt import Subtitle as pyasstosrtSubtitle
import tempfile
from jellyfin2txt.utils import sizeof_fmt
from pgsrip import pgsrip, Mkv, Options
from babelfish import Language

import logging

from  jellyfin_apiclient_python.exceptions import HTTPException as jellyfin_apiclient_python_HTTPException

#item_id='24b6d39b4779259fda28d856e9479b66' # psg quick
#item_id='ce096db83d3454055cf0b5315284c947' # pgs slow: a lot
#item_id='32b81e45fa24eef35b6305bbd5c2329a' # move_text
#item_id='c792916f205221d1d84c73baad5e9814'
#5be3fa7d8dc9524a52426b8e0ba73a49 subrip forced
#98b7b058a754399f2513631a0c65bdce subrip external
#f17589e06f4724ed4d416449efe51b8a ass

from jellyfin2txt.config import client, app, extract_queue

class ExtractObject:

    def __init__(self, item_name, item_id, final_filename, status):
        self.id = item_id
        self.name = item_name
        self.status = status
        self.final_filename = final_filename

class Subtitle:
    subtitles_output_folder = Path(app.config['SUBTITLES_OUTPUT'])
    tmp_subtitles_output_folder = Path(app.config['SUBTITLES_TMP'])
    proxy_url = Path(app.config['PROXY_URL'])
    profile = {
        "Name": "Jellyfin2txt",
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
    neos_subtitles_file_supported = ['subrip']
    neos_converted_subtitles_file_supported = ['ass', 'mov_text']
    neos_extracted_subtitles_file_supported = ['PGSSUB']

    @staticmethod
    def subtitles(item_id):
        try:
            data = client.jellyfin.get_play_info(
                item_id=item_id,
                profile=Subtitle.profile
            )
        except jellyfin_apiclient_python_HTTPException:
            return "Item not existing on Jellyfin", 404

        subtitles = []

        name = data['MediaSources'][0]['Path'].split('/')[-1]
    
        for media in data['MediaSources'][0]['MediaStreams']:
            if media['Type'] == 'Subtitle':
                format_supported = False
                codec = media["Codec"]
                format_supported = False
                if (
                    (media['IsExternal'] or media['IsTextSubtitleStream'] or media['SupportsExternalStream'])
                    or codec in Subtitle.neos_subtitles_file_supported
                    or codec in Subtitle.neos_converted_subtitles_file_supported
                    or codec in Subtitle.neos_extracted_subtitles_file_supported
                ):
                    format_supported = True
                    
                if format_supported:
                    subtitles.append(media['DisplayTitle'])
                else:
                    logging.warning(f'format {codec} not suported for item id {item_id}')
                    if media['IsExternal'] or media['IsTextSubtitleStream'] or media['SupportsExternalStream']:
                        logging.info('This format seems to be easly convertable in srt')
            
        return "`".join(subtitles)

    def download(item_id, name):
        data = client.jellyfin.download_url(item_id)
        response = urlopen(data)
        tt_size = int(response.headers["Content-Length"])
        if name.is_file() and name.stat().st_size == tt_size:
            logging.warning('File already exist and seems to be the same, ignoring dl...')
        else:
            hz_tt_size = sizeof_fmt(tt_size)
            size = 0
            with open(name, 'wb') as dest_file:
                for dat in iter(partial(response.read, 32768), b''):
                    dest_file.write(dat)
                    size += len(dat)
                    logging.info(f"{sizeof_fmt(size)} / {hz_tt_size}")
        return name, tt_size

    @staticmethod
    def clean_sub(sub_file, final_filename):
        logging.info('Starting cleaning sub...')
        sub = cleanitSubtitle(sub_file)
        cfg = cleanitConfig()
        rules = cfg.select_rules(tags={'no-style', 'ocr', 'tidy', 'no-spam'})
        from cleanit.cli import clean_subtitle
        clean_subtitle(
            sub = sub,
            rules = rules,
            encoding = 'utf-8',
            force = False,
            test = False,
            verbose = 99
        )

    @staticmethod
    def subtitle(item_id, subtitle_name):
        try:
            data = client.jellyfin.get_play_info(
                item_id=item_id,
                profile=Subtitle.profile
            )
        except jellyfin_apiclient_python_HTTPException:
            return "Item not existing on Jellyfin", 404

        name = Path(data['MediaSources'][0]['Path'].split('/')[-1])
        subtitle_filename = f"{name.stem} - {subtitle_name}.srt"

        subtitle_found = False
        for entry in Path(Subtitle.subtitles_output_folder).iterdir():
            if entry.is_file() and entry.suffix == '.srt' and entry.name == subtitle_filename:
                subtitle_found = True

        if subtitle_found:
            return f"{Subtitle.proxy_url / subtitle_filename}"
        return "Subtitle not found", 404

    @staticmethod
    def subtitle_extract(item_id, subtitle_name):
        try:
            data = client.jellyfin.get_play_info(
                item_id=item_id,
                profile=Subtitle.profile
            )
        except jellyfin_apiclient_python_HTTPException:
            return "Item not existing on Jellyfin", 404

        name = Path(data['MediaSources'][0]['Path'].split('/')[-1])

        subtitle_name_name = False
        for media in data['MediaSources'][0]['MediaStreams']:
            if media['DisplayTitle'] == subtitle_name:
                    subtitle_name_name = True
        if not subtitle_name_name:
            return f"Subtitle {subtitle_name} not found for this media", 404
    
        for media in data['MediaSources'][0]['MediaStreams']:
            format_supported = False
            if media['Type'] == 'Subtitle':
                if media['DisplayTitle'] != subtitle_name:
                    continue
                codec = media["Codec"]

                final_filename = Path(f"{name.stem} - {media['DisplayTitle']}.srt")
                if media['IsExternal'] or media['IsTextSubtitleStream'] or media['SupportsExternalStream']:
                    if 'DeliveryUrl' in media:
                        url = f"{app.config['SERVER_URL']}{media['DeliveryUrl']}"
                    else:
                        url = f"{app.config['SERVER_URL']}/Videos/{item_id}/{item_id}/Subtitles/{media['Index']}/0/Stream.{codec}"
                    tmp_filename = Subtitle.tmp_subtitles_output_folder / final_filename 
                    if codec in Subtitle.neos_subtitles_file_supported:
                        urllib.request.urlretrieve(url, tmp_filename)
                        os.replace(tmp_filename, f"{Subtitle.subtitles_output_folder/final_filename}")
                    if codec in Subtitle.neos_converted_subtitles_file_supported:
                        if codec == 'ass':
                            urllib.request.urlretrieve(url, tmp_filename)
                            sub = pyasstosrtSubtitle(tmp_filename)
                            sub.export(output_dir=Subtitle.tmp_subtitles_output_folder)
                            os.replace(tmp_filename, f"{Subtitle.subtitles_output_folder/final_filename}")
                        elif codec == 'mov_text':
                            urllib.request.urlretrieve(url, tmp_filename)
                            Subtitle.clean_sub(tmp_filename, final_filename)
                            os.replace(tmp_filename, f"{Subtitle.subtitles_output_folder/final_filename}")
                        else:
                            format_supported = False
                    format_supported = True
                elif  media['Codec'] in Subtitle.neos_extracted_subtitles_file_supported:
                    srt_file = Subtitle.subtitles_output_folder / final_filename
                    logging.info(srt_file)
                    if srt_file.is_file():
                        return "Subtitle already extracted"
                    if name in extract_queue:
                        return f"Subtile extraction {extract_queue.item(name).status}"
                    extract_queue.put(ExtractObject(name, item_id, final_filename, 'planned'))
                    return "Subtitle extraction started"
                else:
                    format_supported = False           
                
                if format_supported:
                    return "Subtitle extracted correctly"
                else:
                    logging.warning(f"Format {media['DisplayTitle']} {codec} not suported for item id {item_id}")
                    if media['IsExternal'] or media['IsTextSubtitleStream'] or media['SupportsExternalStream']:
                        logging.info('This format seems to be easly convertable in srt')
        if not data['MediaSources'][0]['MediaStreams']:
            logging.warning('No subtitle found')
    
        return "Error while returning the srt", 500

    @staticmethod
    def subtitle_extract_thread():
        import time
        while True:
            if extract_queue.empty():
                time.sleep(2)
                continue
            item = extract_queue.get()
            item_id = item.id
            name = item.name
            final_filename = item.final_filename
            try:
                from sh import mkvmerge
            except ImportError:
                logging.error("Cannot extract subtitles if mkvmerge is not available.")
                continue
            media_dl_path = Path(Subtitle.tmp_subtitles_output_folder) / Path(name)
            sub_temp_file, sub_temp_file_size = Subtitle.download(item_id, media_dl_path)
            free_mem = psutil.virtual_memory().available
            if sub_temp_file_size >= free_mem + 100000:
                logging.error(f'Only {sizeof_fmt(free_mem)} RAM free while the file is {sizeof_fmt(sub_temp_file_size)}')
                continue

            media = Mkv(sub_temp_file)
            options = Options(languages={Language('eng')}, overwrite=True, one_per_lang=False)
            logging.info("Processing the media...")
            pgsrip.rip(media, options)

            for entry in Path(Subtitle.tmp_subtitles_output_folder).iterdir():
                if entry.is_file() and entry.suffix == '.srt':
                    Subtitle.clean_sub(entry, final_filename)
                    os.replace(entry, f"{Subtitle.subtitles_output_folder/final_filename}")

            logging.info("Cleaning downloaded file...")
            os.remove(media_dl_path)
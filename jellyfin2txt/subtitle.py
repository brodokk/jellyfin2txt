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

from jellyfin2txt.config import client, app

class Subtitle:
    subtitles_output_folder = Path("subtitles")
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
                    print(f"{sizeof_fmt(size)} / {hz_tt_size}")
        return name, tt_size

    @staticmethod
    def clean_sub(sub_file, final_filename):
        sub = cleanitSubtitle(sub_file)
        cfg = cleanitConfig()
        rules = cfg.select_rules(tags={'no-style', 'ocr', 'tidy', 'no-spam'})
        if sub.clean(rules):
            sub.save(f"{Subtitle.subtitles_output_folder/final_filename}")


    @staticmethod
    def subtitle(item_id, subtitle_name):
        try:
            data = client.jellyfin.get_play_info(
                item_id=item_id,
                profile=Subtitle.profile
            )
        except jellyfin_apiclient_python_HTTPException:
            return "Item not existing on Jellyfin", 404

        name = data['MediaSources'][0]['Path'].split('/')[-1]
    
        for media in data['MediaSources'][0]['MediaStreams']:
            format_supported = False
            if media['Type'] == 'Subtitle':
                if media['DisplayTitle'] != subtitle_name:
                    continue
                codec = media["Codec"]
                final_filename = Path(f"{name.replace('/', '')}.{media['DisplayTitle'].replace('/', '')}.srt")
                url = ''
                if media['IsExternal'] or media['IsTextSubtitleStream'] or media['SupportsExternalStream']:
                    if 'DeliveryUrl' in media:
                        url = f"{app.config['SERVER_URL']}{media['DeliveryUrl']}"
                    else:
                        url = f"{app.config['SERVER_URL']}/Videos/{item_id}/{item_id}/Subtitles/{media['Index']}/0/Stream.{codec}"
                    if codec in Subtitle.neos_converted_subtitles_file_supported:
                        if codec == 'ass':
                            with tempfile.NamedTemporaryFile() as sub_temp_file:
                                urllib.request.urlretrieve(url, sub_temp_file.name)
                                sub = pyasstosrtSubtitle(sub_temp_file.name)
                                tmp_filename = sub_temp_file.name.split('/')[-1]
                                sub.export(output_dir=Subtitle.subtitles_output_folder)
                                os.replace(f"{Subtitle.subtitles_output_folder/tmp_filename}.srt", f"{Subtitle.subtitles_output_folder/final_filename}")
                        elif codec == 'mov_text':
                            with tempfile.NamedTemporaryFile() as sub_temp_file:
                                urllib.request.urlretrieve(url, sub_temp_file.name)
                                Subtitle.Media.clean_sub(sub_temp_file.name, final_filename)
                        else:
                            format_supported = False
                    format_supported = True
                elif  media['Codec'] in Subtitle.neos_extracted_subtitles_file_supported:
                    dl_path = "/home/neodarz/Code/brodokk/jellyfin2txt/tmp/"
                    dl_path = "/home/brodokk/Code/jellyfin2txt/tmp/"
                    with tempfile.TemporaryDirectory(dir='tmp') as sub_temp_dir:
                        try:
                            from sh import mkvmerge
                        except ImportError:
                            logging.error("Cannot extract subtitles if mkvmerge is not available.")
                            return "Error while extracting subtitles from media", 500 
                        sub_temp_file, sub_temp_file_size = Subtitle.download(item_id, Path(dl_path) / Path(name))
                        free_mem = psutil.virtual_memory().available
                        if sub_temp_file_size >= free_mem + 100000:
                            logging.error(f'Only {sizeof_fmt(free_mem)} RAM free while the file is {sizeof_fmt(sub_temp_file_size)}')
                            return "Error while extracting subtitles from media", 500

                        media_file = Mkv(sub_temp_file)
                        options = Options(languages={Language('eng')}, overwrite=True, one_per_lang=False)
                        logging.info("Processing the media...")
                        pgsrip.rip(media_file, options)

                        for entry in Path(dl_path).iterdir():
                            if entry.is_file() and entry.suffix == '.srt':
                                final_filename = Path(f"{entry.stem.replace('/', '')}.srt")
                                Media.clean_sub(sub_temp_file, f"{Subtitle.subtitles_output_folder/final_filename}")
                                url = 'uwu'
                else:
                    format_supported = False           
                
                if format_supported:
                    return url
                else:
                    print(f"Warning format {media['DisplayTitle']} {codec} not suported for item id {item_id}")
                    if media['IsExternal'] or media['IsTextSubtitleStream'] or media['SupportsExternalStream']:
                        print('This format seems to be easly convertable in srt')
    
        return "Error while returning the srt", 500
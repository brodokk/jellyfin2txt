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
    subtitles_output_folder = Path(app.config['SUBTITLES_OUTPUT'])
    tmp_subtitles_output_folder = Path(app.config['SUBTITLES_TMP'])
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
                url = ''
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
                    try:
                        from sh import mkvmerge
                    except ImportError:
                        logging.error("Cannot extract subtitles if mkvmerge is not available.")
                        return "Error while extracting subtitles from media", 500 
                    sub_temp_file, sub_temp_file_size = Subtitle.download(item_id, Path(Subtitle.tmp_subtitles_output_folder) / Path(name))
                    free_mem = psutil.virtual_memory().available
                    if sub_temp_file_size >= free_mem + 100000:
                        logging.error(f'Only {sizeof_fmt(free_mem)} RAM free while the file is {sizeof_fmt(sub_temp_file_size)}')
                        return "Error while extracting subtitles from media", 500

                    media = Mkv(sub_temp_file)
                    options = Options(languages={Language('eng')}, overwrite=True, one_per_lang=False)
                    logging.info("Processing the media...")
                    pgsrip.rip(media, options)

                    for entry in Path(Subtitle.tmp_subtitles_output_folder).iterdir():
                        if entry.is_file() and entry.suffix == '.srt':
                            Subtitle.clean_sub(entry, final_filename)
                            os.replace(entry, f"{Subtitle.subtitles_output_folder/final_filename}")
                            url = 'uwu'
                    format_supported = True
                else:
                    format_supported = False           
                
                if format_supported:
                    return url
                else:
                    logging.warning(f"Format {media['DisplayTitle']} {codec} not suported for item id {item_id}")
                    if media['IsExternal'] or media['IsTextSubtitleStream'] or media['SupportsExternalStream']:
                        logging.info('This format seems to be easly convertable in srt')
        if not data['MediaSources'][0]['MediaStreams']:
            logging.warning('No subtitle found')
    
        return "Error while returning the srt", 500
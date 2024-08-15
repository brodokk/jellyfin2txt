from typing import Optional

from jellyfin2txt.config import client, params, app

class Media:

    @staticmethod
    def _ids(params: dict, tags: list = None) -> dict:
        if tags:
            params['Tags']: list = tags
        media: dict = client.jellyfin.users('/Items', params=params)
        items: list = []
        for item in media['Items']:
            items.append(item['Id'])
        media['Items'] = items
        return media

    @staticmethod
    def _movies_ids(
        start_index: int = 0,
        limit: int = 100, tags:
        list = None,
    ) -> dict:
        params['StartIndex']: int = start_index
        params['Limit']: int = limit
        params['IncludeItemTypes']: str = 'Movie'
        params['ParentId']: str = client.movies_id
        return Media._ids(params, tags)

    @staticmethod
    def _series_ids(
        start_index: int = 0,
        limit: int = 100,
        tags: list = None,
    ) -> dict:
        params['StartIndex']: int = start_index
        params['Limit']: int = limit
        params['IncludeItemTypes']: str = 'Series'
        params['ParentId']: str = client.series_id
        return Media._ids(params, tags)

    @staticmethod
    def _thumbnail(
        item_id: str,
        fillHeight: int = 320,
        fillWidth: int = 213,
        quality: int = 96,
    ) -> str:
        server_url: str = app.config['SERVER_URL']
        return (
            f'{server_url}/Items/{item_id}/Images/Primary?fillHeight={fillHeight}'
            f'&fillWidth={fillWidth}&quality={quality}'
        )

    @staticmethod
    def movies(
        start_index: int = 0,
        limit: int = 100,
        thumb_fill_height: int = 320,
        thumb_fill_width: int = 213,
        thumb_quality: int = 96,
        tags: str = None,
    ) -> str:
        movies_ids: dict = Media._movies_ids(start_index, limit, tags)
        response: str = "{},{};".format(
            movies_ids['StartIndex'], movies_ids['TotalRecordCount']
        )
        for movie_id in movies_ids['Items']:
            movie: dict = client.jellyfin.get_item(movie_id)
            trailer_url: str = ""
            if movie['RemoteTrailers']:
                trailer_url: str = movie['RemoteTrailers'][0]['Url']
            name: str = movie['Name']
            external_link: str = ""
            for external_url in movie['ExternalUrls']:
                if external_url['Name'] == 'IMDb':
                    external_link: str = external_url['Url']
            dl_url: str = client.jellyfin.download_url(movie_id)
            stream_url: str = client.jellyfin.video_url(movie_id)
            img_url: str = Media._thumbnail(movie_id, thumb_fill_height, thumb_fill_width, thumb_quality)
            variables: list = [name, img_url, dl_url, stream_url, trailer_url, external_link, movie_id]
            response += ','.join(variables) + ';'
        return response.rstrip(';')

    @staticmethod
    def series(
        start_index: int = 0,
        limit: int = 100,
        thumb_fill_height: int = 320,
        thumb_fill_width: int = 213,
        thumb_quality: int = 96,
        tags: list = None
    ) -> str:
        series_ids: dict = Media._series_ids(start_index, limit, tags)
        response: str = "{},{};".format(
            series_ids['StartIndex'], series_ids['TotalRecordCount']
        )
        for serie_id in series_ids['Items']:
            serie: dict = client.jellyfin.get_item(serie_id)
            name: str = serie['Name']
            external_link: str = ""
            for external_url in serie['ExternalUrls']:
                if external_url['Name'] == 'IMDb':
                    external_link: str = external_url['Url']
            img_url: str = Media._thumbnail(serie_id, thumb_fill_height, thumb_fill_width, thumb_quality)
            variables: str = [name, img_url, serie_id, external_link, serie_id]
            response += ','.join(variables) + ';'
        return response.rstrip(';')

    @staticmethod
    def seasons(serie_id: str) -> str:
        seasons: dict = client.jellyfin.get_seasons(serie_id)
        response: str = "{},{};".format(
            seasons['StartIndex'], seasons['TotalRecordCount']
        )
        for season in seasons['Items']:
            name: str = season['Name']
            season_id: str = season['Id']
            img_url: str = Media._thumbnail(season_id)
            variables: str = [name, img_url, season_id]
            response += ','.join(variables) + ';'
        return response.rstrip(';')

    @staticmethod
    def episodes(serie_id: str, season_id: str) -> str:
        episodes: dict = client.jellyfin.get_season(serie_id, season_id)
        response: str = "{},{};".format(
            episodes['StartIndex'], episodes['TotalRecordCount']
        )

        for episode in episodes['Items']:
            name: str = episode['Name']
            episode_id: str = episode['Id']
            img_url: str = Media._thumbnail(episode_id)
            dl_url: str = client.jellyfin.download_url(episode_id)
            stream_url: str = client.jellyfin.video_url(episode_id)
            variables: str = [name, img_url, episode_id, dl_url, stream_url]
            response += ','.join(variables) + ';'
        return response.rstrip(';')

    @staticmethod
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
            "Name": "Jellyfin2txt",
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
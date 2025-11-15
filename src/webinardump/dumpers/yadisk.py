import json
import re
from pathlib import Path

from .base import Dumper
from ..utils import LOGGER


class YandexDisk(Dumper):

    title = 'Яндекс.Диск'

    _user_input_map = {
        'url_video': 'Video URL (https://disk.yandex.ru/i/xxx)',
    }

    def _get_manifest(self, url: str) -> dict:
        LOGGER.debug(f'Getting manifest from {url} ...')

        contents = self._get_response_simple(url)
        manifest = re.findall(r'id="store-prefetch">([^<]+)</script', contents)
        assert manifest, f'Manifest not found for {url}'
        manifest = manifest[0]
        manifest = json.loads(manifest)
        return manifest

    def _get_playlist_and_title(self, manifest: dict) -> tuple[str, str]:

        resources = list(manifest['resources'].values())
        resource = resources[0]

        dimension_max = 0
        url_playlist = '<none>'

        for stream_info in resource['videoStreams']['videos']:
            dimension, *_ = stream_info['dimension'].partition('p')
            if not dimension.isnumeric():
                continue  # e.g. 'adaptive'
            dimension = int(dimension)
            if dimension_max < dimension:
                dimension_max = dimension
                url_playlist = stream_info['url']

        return url_playlist, resource['name']

    def _gather(self, *, url_video: str, start_chunk: str = '', **params) -> Path:

        manifest = self._get_manifest(url_video)
        url_playlist, title = self._get_playlist_and_title(manifest)

        return self._video_dump(
            title=title,
            url_playlist=url_playlist,
            url_referer=url_video,
            start_chunk=start_chunk,
        )

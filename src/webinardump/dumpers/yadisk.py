import json
import re
from pathlib import Path
from typing import ClassVar
from urllib.parse import quote, urlsplit

from ..utils import LOGGER
from .base import Dumper


class YandexDisk(Dumper):

    title = 'Яндекс.Диск'

    _user_input_map: ClassVar[dict[str, str]] = {
        'url_video': 'Video URL (https://disk.yandex.ru/i/xxx or /d/xxx/yyy.mp4)',
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

    def _get_shared_info(self, url: str) -> tuple[str, str]:
        LOGGER.debug(f'Getting shared file from {url} ...')

        contents = self._get_response_simple(url)

        objects = self._extract_js_objects(contents, key='environment')

        assert objects, f'File params not found for {url}'
        sk = objects[0]['environment']['sk']
        resource_id = objects[0]['currentResourceId']
        resource_data = objects[0]['resources'][resource_id]
        resource_path = resource_data['path']
        filepath = urlsplit(url).path.split('/', 3)[-1]

        response_data = self._handle_response_simple(self._session.post(
            'https://disk.yandex.ru/public/api/get-video-streams',
            data=quote(f'{{"hash": "{resource_path}/{filepath}", "sk": "{sk}"}}'),
            headers={'Content-Type': 'text/plain', 'X-Requested-With': 'XMLHttpRequest'}
        ), json=True)

        playlist_candidate = None
        greatest_resolution = 0

        videos = response_data.get('data', {}).get('videos', [])

        for video in videos:
            width = video['size'].get('width', 0)
            if width > greatest_resolution:
                greatest_resolution = width
                playlist_candidate = video['url']

        assert playlist_candidate, f'No video candidates found for {url}'

        return playlist_candidate, Path(filepath).stem

    def _gather(self, *, url_video: str, start_chunk: str = '', **params) -> Path:

        if '/d/' in url_video:
            url_playlist, title = self._get_shared_info(url_video)

        else:
            manifest = self._get_manifest(url_video)
            url_playlist, title = self._get_playlist_and_title(manifest)

        return self._video_dump(
            title=title,
            url_playlist=url_playlist,
            url_referer=url_video,
            start_chunk=start_chunk,
        )

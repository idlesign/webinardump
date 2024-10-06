#! /usr/bin/env python3
import json
import logging
import re
import shutil
import subprocess
from functools import partial
from pathlib import Path
from random import choice
from time import sleep

import requests
from requests import Session

LOGGER = logging.getLogger(__name__)


def configure_logging(
        *,
        level: int = None,
        logger: logging.Logger = None,
        fmt: str = '%(message)s'
):
    """Switches on logging at a given level. For a given logger or globally.

    :param level:
    :param logger:
    :param fmt:

    """
    logging.basicConfig(format=fmt, level=level if logger else None)
    logger and logger.setLevel(level or logging.INFO)


configure_logging(logger=LOGGER)


class Dumper:

    _user_input_map: dict[str, str] = None

    _headers: dict[str, str] = {
        'Connection': 'keep-alive',
        'Accept': '*/*',
        'User-Agent': (
            'Mozilla/5.0 (X11; Linux x86_64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/79.0.3945.136 YaBrowser/20.2.3.320 (beta) Yowser/2.5 Safari/537.36'
        ),
        'Sec-Fetch-Site': 'same-site',
        'Sec-Fetch-Mode': 'cors',
        'Accept-Language': 'ru,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, sdch, br',
    }

    def __init__(self):
        self._user_input_map = self._user_input_map or {}
        self._session = self._get_session()
        self._sleepy = True

    @staticmethod
    def _get_user_input(prompt: str) -> str:
        while True:
            data = input(f'{prompt}: ')
            data = data.strip()
            if data:
                return data

    def _get_session(self) -> Session:
        session = requests.Session()
        session.headers = self._headers
        return session

    def _get_args(self) -> dict:
        input_data = {}

        for param, hint in self._user_input_map.items():
            input_data[param] = self._get_user_input(hint)

        return input_data

    def _chunks_get_list(self, url: str) -> list[str]:
        """Get video chunks names from playlist file at URL.

        :param url: File URL.

        """
        LOGGER.info(f'Getting video chunks from playlist {url} ...')

        playlist = self._get_response_simple(url)
        chunk_lists = []

        for line in playlist.splitlines():
            line = line.strip()

            if not line.partition('?')[0].endswith('.ts'):
                continue

            chunk_lists.append(line)

        assert chunk_lists, 'No .ts chunks found in playlist file'

        return chunk_lists

    def _chunks_download(
        self,
        *,
        url_video_root: str,
        dump_dir: Path,
        chunk_names: list[str],
        start_chunk: str,
        headers: dict[str, str] = None,
    ) -> None:

        chunks_total = len(chunk_names)

        for idx, chunk_name in enumerate(chunk_names, 1):

            if chunk_name == start_chunk:
                start_chunk = ''  # clear to allow further download

            if start_chunk:
                continue

            percent = round(idx * 100 / chunks_total, 1)

            LOGGER.info(f'Get {idx}/{chunks_total} ({chunk_name}) [{percent}%] ...')

            chunk_url = f'{url_video_root.rstrip("/")}/{chunk_name}'

            with self._session.get(chunk_url, headers=headers or {}, stream=True) as r:
                r.raise_for_status()
                with open(dump_dir / chunk_name.partition('?')[0], 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

            if self._sleepy:
                sleep(choice([1, 0.5, 0.7, 0.6]))

    def _video_concat(self, path: Path) -> Path:

        LOGGER.info('Concatenating video ...')

        fname_video = 'all_chunks.mp4'
        fname_index = 'all_chunks.txt'
        call = partial(subprocess.check_call, cwd=path, shell=True)

        call(f'for i in `ls *.ts | sort -V`; do echo "file $i"; done >> {fname_index}')
        call(f'ffmpeg -f concat -i {fname_index} -c copy -bsf:a aac_adtstoasc {fname_video}')

        return path / fname_video

    def _get_response_simple(self, url: str, *, json: bool = False) -> str | dict:
        """Returns a text or a dictionary from a URL.

        :param url:
        :param json:

        """
        response = self._session.get(url)
        response.raise_for_status()

        if json:
            return response.json()

        return response.text

    def _video_dump(
        self,
        *,
        title: str,
        url_playlist: str,
        url_referer: str,
        start_chunk: str = '',
    ):
        assert url_playlist.endswith('m3u8'), f'No playlist in `{url_playlist}`'

        LOGGER.info(f'Title: {title}')

        chunk_names = self._chunks_get_list(url_playlist)

        LOGGER.info('Downloading video ...')

        dump_dir = Path(title).absolute()
        dump_dir.mkdir(exist_ok=True)

        url_root = url_playlist.rpartition('/')[0]  # strip playlist filename

        self._chunks_download(
            url_video_root=url_root,
            dump_dir=dump_dir,
            chunk_names=chunk_names,
            start_chunk=start_chunk,
            headers={'Referer': url_referer}
        )

        fpath_video_target = Path(f'{title}.mp4').absolute()
        fpath_video = self._video_concat(dump_dir)

        shutil.move(fpath_video, fpath_video_target)
        shutil.rmtree(dump_dir, ignore_errors=True)

        LOGGER.info(f'Video is ready: {fpath_video_target}')

    def _gather(self, *, url_video: str, start_chunk: str = '', **params):
        raise NotImplementedError

    def run(self):
        self._gather(**self._get_args())


class WebinarRu(Dumper):

    _user_input_map = {
        'url_video': 'Video URL (with `record-new/`)',
        'url_playlist': 'Video chunk list URL (with `chunklist.m3u8`)',
    }

    _headers = {
        **Dumper._headers,
        'Origin': 'https://events.webinar.ru',
    }

    def _gather(self, *, url_video: str, start_chunk: str = '', url_playlist: str = '', **params):
        """Runs video dump.

        :param url_video: Video URL. Hint: has record-new/
        :param url_playlist: Video chunk list URL. Hint: ends with chunklist.m3u8
        :param start_chunk: Optional chunk name to continue download from.
        """
        assert url_playlist, 'Playlist URL must be specified'

        assert 'record-new/' in url_video, (
            'Unexpected video URL format\n'
            f'Given:    {url_video}.\n'
            f'Expected: https://events.webinar.ru/xxx/yyy/record-new/aaa/bbb')

        _, _, tail = url_video.partition('record-new/')
        session_id, _, video_id = tail.partition('/')

        LOGGER.info('Getting manifest ...')

        manifest = self._get_response_simple(
            f'https://events.webinar.ru/api/eventsessions/{session_id}/record/isviewable?recordAccessToken={video_id}',
            json=True
        )

        self._video_dump(
            title=manifest['name'],
            url_playlist=url_playlist,
            url_referer=url_video,
            start_chunk=start_chunk,
        )


class YandexDisk(Dumper):

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

    def _gather(self, *, url_video: str, start_chunk: str = '', **params):

        manifest = self._get_manifest(url_video)
        url_playlist, title = self._get_playlist_and_title(manifest)

        self._video_dump(
            title=title,
            url_playlist=url_playlist,
            url_referer=url_video,
            start_chunk=start_chunk,
        )


if __name__ == '__main__':
    dumper = YandexDisk()
    dumper.run()

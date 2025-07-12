#! /usr/bin/env python3
# /// script
# dependencies = [
#   "requests",
# ]
# ///
import argparse
import json
import logging
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import chdir
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


def get_user_input(prompt: str, *, choices: list[str] = None) -> str:

    choices = set(choices or [])

    while True:
        data = input(f'{prompt}: ')
        data = data.strip()
        if not data or (choices and data not in choices):
            continue

        return data


class Dumper:

    title: str = ''

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

    registry: list[type['Dumper']] = []

    def __init_subclass__(cls):
        super().__init_subclass__()
        cls.registry.append(cls)

    def __init__(self, *, target_dir: Path, timeout: int = 5, concurrent: int = 10, sleepy: bool = False) -> None:
        self._target_dir = target_dir
        self._timeout = timeout
        self._concurrent = concurrent
        self._user_input_map = self._user_input_map or {}
        self._session = self._get_session()
        self._sleepy = sleepy

    def __str__(self):
        return self.title

    def _get_session(self) -> Session:
        session = requests.Session()
        session.headers = self._headers
        return session

    def _get_args(self) -> dict:
        input_data = {}

        for param, hint in self._user_input_map.items():
            input_data[param] = get_user_input(hint)

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
        concurrent: int = 10,
    ) -> None:

        chunks_total = len(chunk_names)

        def dump(*, name: str, url: str, session: Session, sleepy: bool, timeout: int) -> None:

            with session.get(url, headers=headers or {}, stream=True, timeout=timeout) as r:
                r.raise_for_status()
                with open(dump_dir / name.partition('?')[0], 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

            if sleepy:
                sleep(choice([1, 0.5, 0.7, 0.6]))

        with ThreadPoolExecutor(max_workers=concurrent) as executor:

            future_url_map = {}

            for chunk_name in chunk_names:

                if chunk_name == start_chunk:
                    start_chunk = ''  # clear to allow further download

                if start_chunk:
                    continue

                chunk_url = f'{url_video_root.rstrip("/")}/{chunk_name}'
                submitted = executor.submit(
                    dump,
                    name=chunk_name,
                    url=chunk_url,
                    session=self._session,
                    sleepy=self._sleepy,
                    timeout=self._timeout,
                )

                future_url_map[submitted] = (chunk_name, chunk_url)

            if future_url_map:
                LOGGER.info(f'Downloading up to {concurrent} files concurrently ...')

                counter = 1
                for future in as_completed(future_url_map):
                    chunk_name, chunk_url = future_url_map[future]
                    future.result()
                    percent = round(counter * 100 / chunks_total, 1)
                    counter += 1
                    LOGGER.info(f'Got {counter}/{chunks_total} ({chunk_name}) [{percent}%] ...')

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

        target_dir = self._target_dir
        LOGGER.info(f'Downloading video into {target_dir} ...')

        with chdir(target_dir):
            dump_dir = (target_dir / title).absolute()
            dump_dir.mkdir(parents=True, exist_ok=True)

            url_root = url_playlist.rpartition('/')[0]  # strip playlist filename

            self._chunks_download(
                url_video_root=url_root,
                dump_dir=dump_dir,
                chunk_names=chunk_names,
                start_chunk=start_chunk,
                headers={'Referer': url_referer},
                concurrent=self._concurrent,
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

    title = 'webinar.ru'

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

    def _gather(self, *, url_video: str, start_chunk: str = '', **params):

        manifest = self._get_manifest(url_video)
        url_playlist, title = self._get_playlist_and_title(manifest)

        self._video_dump(
            title=title,
            url_playlist=url_playlist,
            url_referer=url_video,
            start_chunk=start_chunk,
        )


def cli():
    parser = argparse.ArgumentParser(prog='webinardump')
    parser.add_argument('-t', '--target', type=Path, default=Path('.'), help='Directory to dump to')
    parser.add_argument('--timeout', type=int, default=5, help='Request timeout')
    parser.add_argument('--rmax', type=int, default=10, help='Max concurrent requests number')

    args = parser.parse_args()

    dumper_choices = []
    print('Available dumpers:')

    for idx, dumper in enumerate(Dumper.registry, 1):
        print(f'{idx} — {dumper.title}')
        dumper_choices.append(f'{idx}')

    chosen = get_user_input('Select dumper number', choices=dumper_choices)

    dumper = Dumper.registry[int(chosen)-1](
        target_dir=args.target,
        timeout=args.timeout,
        concurrent=args.rmax,
    )
    dumper.run()



if __name__ == '__main__':
    cli()

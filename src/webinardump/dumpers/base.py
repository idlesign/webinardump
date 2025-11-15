import shutil
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import chdir
from functools import partial
from pathlib import Path
from random import choice
from threading import Lock
from time import sleep

import requests
from requests import Session
from requests.adapters import HTTPAdapter, Retry

from ..utils import LOGGER, call


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

    def __init__(self, *, target_dir: Path, timeout: int = 3, concurrent: int = 10, sleepy: bool = False) -> None:
        self._target_dir = target_dir
        self._timeout = timeout
        self._concurrent = concurrent
        self._user_input_map = self._user_input_map or {}
        self._session = self._get_session()
        self._sleepy = sleepy

    def __str__(self):
        return self.title

    def _get_session(self) -> Session:
        # todo при ошибках сессия в нитях блокируется. можно попробовать несколько сессий
        session = requests.Session()
        session.headers = self._headers
        retries = Retry(total=3, backoff_factor=0.1, status_forcelist=[500])
        session.mount('http://', HTTPAdapter(max_retries=retries))
        session.mount('https://', HTTPAdapter(max_retries=retries))
        return session

    def _get_args(self, *, get_param_hook: Callable[[str, str], str]) -> dict:
        input_data = {}

        for param, hint in self._user_input_map.items():
            input_data[param] = get_param_hook(param, hint)

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

        progress_file = (dump_dir / 'files.txt')
        progress_file.touch()

        files_done = dict.fromkeys(progress_file.read_text().splitlines())
        lock = Lock()

        def dump(*, name: str, url: str, session: Session, sleepy: bool, timeout: int) -> None:

            name = name.partition('?')[0]

            if name in files_done:
                LOGGER.info(f'File {name} has been already downloaded before. Skipping.')
                return

            with session.get(url, headers=headers or {}, stream=True, timeout=timeout) as r:
                r.raise_for_status()
                with open(dump_dir / name, 'wb') as f:
                    f.writelines(r.iter_content(chunk_size=8192))

            files_done[name] = True
            with lock:
                progress_file.write_text('\n'.join(files_done))

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
                    LOGGER.info(f'Got {counter}/{chunks_total} ({chunk_name.partition("?")[0]}) [{percent}%] ...')

    def _video_concat(self, path: Path) -> Path:

        LOGGER.info('Concatenating video ...')

        fname_video = 'all_chunks.mp4'
        fname_index = 'all_chunks.txt'

        call(f'for i in `ls *.ts | sort -V`; do echo "file $i"; done >> {fname_index}', path=path)
        call(f'ffmpeg -f concat -i {fname_index} -c copy -bsf:a aac_adtstoasc {fname_video}', path=path)

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
    ) -> Path:
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
                headers={'Referer': url_referer.strip()},
                concurrent=self._concurrent,
            )

            fpath_video_target = Path(f'{title}.mp4').absolute()
            fpath_video = self._video_concat(dump_dir)

            shutil.move(fpath_video, fpath_video_target)
            shutil.rmtree(dump_dir, ignore_errors=True)

        LOGGER.info(f'Video is ready: {fpath_video_target}')
        return fpath_video_target

    def _gather(self, *, url_video: str, start_chunk: str = '', **params) -> Path:
        raise NotImplementedError

    def run(self, params_or_hook: Callable[[str, str], str] | dict[str, str]) -> Path:
        params = params_or_hook if isinstance(params_or_hook, dict) else self._get_args(get_param_hook=params_or_hook)
        return self._gather(**params)

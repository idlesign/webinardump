import logging
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

    user_input_map: dict[str, str] = None

    headers: dict[str, str] = {
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
        self.user_input_map = self.user_input_map or {}
        self.session = self._get_session()

    @staticmethod
    def _get_user_input(prompt: str) -> str:
        while True:
            data = input(f'{prompt}: ')
            data = data.strip()
            if data:
                return data

    def _get_session(self) -> Session:
        session = requests.Session()
        session.headers = self.headers
        return session

    def _get_args(self) -> dict:
        input_data = {}

        for param, hint in self.user_input_map.items():
            input_data[param] = self._get_user_input(hint)

        return input_data

    def _chunks_get_list(self, url: str) -> list[str]:
        """Get video chunks names from playlist file at URL.

        :param url: File URL.

        """
        LOGGER.info('Getting video chunk names ...')

        playlist = self._get_response_simple(url)
        chunk_lists = []

        for line in playlist.splitlines():
            line = line.strip()

            if not line.endswith('.ts'):
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
        headers: dict[str, str] = None
    ) -> None:

        chunks_total = len(chunk_names)

        for idx, chunk_name in enumerate(chunk_names, 1):

            if chunk_name == start_chunk:
                start_chunk = ''  # clear to allow further download

            if start_chunk:
                continue

            percent = round(idx * 100 / chunks_total, 1)

            LOGGER.info(f'Get {idx}/{chunks_total} ({chunk_name}) [{percent}%] ...')

            chunk_url = f'{url_video_root}/{chunk_name}'

            with self.session.get(chunk_url, headers=headers or {}, stream=True) as r:
                r.raise_for_status()
                with open(dump_dir / chunk_name, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

            sleep(choice([1, 0.5, 0.7, 0.6]))

    def _chunks_to_video(self, path: Path) -> Path:

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
        response = self.session.get(url)
        response.raise_for_status()

        if json:
            return response.json()

        return response.text

    def gather(self, **params):
        raise NotImplementedError

    def run(self):
        self.gather(**self._get_args())


class WebinarRu(Dumper):

    user_input_map = {
        'url_entry': 'Video entry URL (with `record-new/`)',
        'url_chunklist': 'Video chunk list URL (with `chunklist.m3u8`)',
    }

    headers = {
        **Dumper.headers,
        'Origin': 'https://events.webinar.ru',
    }

    def gather(self, *, url_entry: str, url_chunklist: str, start_chunk: str = ''):
        """Runs video dump.

        :param url_entry: Video entry URL. Hint: has record-new/
        :param url_chunklist: Video chunk list URL. Hint: ends with chunklist.m3u8
        :param start_chunk: Optional chunk name to continue download from.
        """
        chunklist_postfix = '/chunklist.m3u8'
        assert chunklist_postfix in url_chunklist, 'Provide chunklist.m3u8 URL to `url_chunklist`'

        assert 'record-new/' in url_entry, (
            'Unexpected entry URL format\n'
            f'Given:    {url_entry}.\n'
            f'Expected: https://events.webinar.ru/xxx/yyy/record-new/aaa/bbb')

        _, _, tail = url_entry.partition('record-new/')
        session_id, _, video_id = tail.partition('/')

        LOGGER.info('Getting manifest ...')

        manifest = self._get_response_simple(
            f'https://events.webinar.ru/api/eventsessions/{session_id}/record/isviewable?recordAccessToken={video_id}',
            json=True
        )

        title = manifest['name']

        LOGGER.info(f'Title: {title}')

        chunk_names = self._chunks_get_list(url_chunklist)

        LOGGER.info('Downloading video ...')

        dump_dir = Path(title).absolute()
        dump_dir.mkdir(exist_ok=True)

        self._chunks_download(
            url_video_root=url_chunklist.replace(chunklist_postfix, '', 1),
            dump_dir=dump_dir,
            chunk_names=chunk_names,
            start_chunk=start_chunk,
            headers={'Referer': url_entry}
        )

        fpath_video_target = Path(f'{title}.mp4').absolute()
        fpath_video = self._chunks_to_video(dump_dir)

        shutil.move(fpath_video, fpath_video_target)
        shutil.rmtree(dump_dir, ignore_errors=True)

        LOGGER.info(f'Video is ready: {fpath_video_target}')


if __name__ == '__main__':
    dumper = WebinarRu()
    dumper.run()

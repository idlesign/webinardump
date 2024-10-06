import logging
import shutil
import subprocess
from functools import partial
from pathlib import Path
from random import choice
from time import sleep

import requests

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


session = requests.Session()
session.headers = {
    'Connection': 'keep-alive',
    'Accept': '*/*',
    'User-Agent': (
        'Mozilla/5.0 (X11; Linux x86_64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/79.0.3945.136 YaBrowser/20.2.3.320 (beta) Yowser/2.5 Safari/537.36'
    ),
    'Origin': 'https://events.webinar.ru',
    'Sec-Fetch-Site': 'same-site',
    'Sec-Fetch-Mode': 'cors',
    'Accept-Language': 'ru,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, sdch, br',
}


def get_response_simple(url: str, *, json: bool = False) -> str | dict:
    """Returns a text or a dictionary from a URL.

    :param url:
    :param json:

    """
    response = session.get(url)
    response.raise_for_status()

    if json:
        return response.json()

    return response.text


def get_chunks(url: str) -> list[str]:
    """Get video chunks names from playlist file at URL.

    :param url: File URL.

    """
    LOGGER.info('Getting video chunk names ...')

    playlist = get_response_simple(url)
    chunk_lists = []

    for line in playlist.splitlines():
        line = line.strip()

        if not line.endswith('.ts'):
            continue

        chunk_lists.append(line)

    assert chunk_lists, 'No .ts chunks found in playlist file'

    return chunk_lists


def concat_chunks(path: Path) -> Path:

    LOGGER.info('Concatenating video ...')

    fname_video = 'all_chunks.mp4'
    fname_index = 'all_chunks.txt'
    call = partial(subprocess.check_call, cwd=path, shell=True)

    call(f'for i in `ls *.ts | sort -V`; do echo "file $i"; done >> {fname_index}')
    call(f'ffmpeg -f concat -i {fname_index} -c copy -bsf:a aac_adtstoasc {fname_video}')

    return path / fname_video


def download_chunks(*, url_video_root: str, dump_dir: Path, chunk_names: list[str], start_chunk: str):

    chunks_total = len(chunk_names)

    for idx, chunk_name in enumerate(chunk_names, 1):

        if chunk_name == start_chunk:
            start_chunk = ''  # clear to allow further download

        if start_chunk:
            continue

        percent = round(idx * 100 / chunks_total, 1)

        LOGGER.info(f'Get {idx}/{chunks_total} ({chunk_name}) [{percent}%] ...')

        chunk_url = f'{url_video_root}/{chunk_name}'

        with session.get(chunk_url, headers={'Referer': url_entry}, stream=True) as r:
            r.raise_for_status()
            with open(str(dump_dir / chunk_name), 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        sleep(choice([1, 0.5, 0.7, 0.6]))


def run(*, url_entry: str, url_chunklist: str, start_chunk: str = ''):
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

    manifest = get_response_simple(
        f'https://events.webinar.ru/api/eventsessions/{session_id}/record/isviewable?recordAccessToken={video_id}',
        json=True
    )

    title = manifest['name']

    LOGGER.info(f'Title: {title}')

    chunk_names = get_chunks(url_chunklist)

    LOGGER.info('Downloading video ...')

    dump_dir = Path(title).absolute()
    dump_dir.mkdir(exist_ok=True)

    download_chunks(
        url_video_root=url_chunklist.replace(chunklist_postfix, '', 1),
        dump_dir=dump_dir,
        chunk_names=chunk_names,
        start_chunk=start_chunk,
    )

    fpath_video_target = Path(f'{title}.mp4').absolute()
    fpath_video = concat_chunks(dump_dir)

    shutil.move(str(fpath_video), str(fpath_video_target))
    shutil.rmtree(str(dump_dir), ignore_errors=True)

    LOGGER.info(f'Video is ready: {fpath_video_target}')


if __name__ == '__main__':

    def get_data(prompt: str) -> str:

        while True:
            data = input(f'{prompt}: ')
            data = data.strip()
            if data:
                return data

    url_entry = get_data('Video entry URL (with `record-new/`)')
    url_chunklist = get_data('Video entry URL (with `chunklist.m3u8`)')

    run(url_entry=url_entry, url_chunklist=url_chunklist)

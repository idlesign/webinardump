from pathlib import Path

from .base import Dumper
from ..utils import LOGGER


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

    def _gather(self, *, url_video: str, start_chunk: str = '', url_playlist: str = '', **params) -> Path:
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

        return self._video_dump(
            title=manifest['name'],
            url_playlist=url_playlist,
            url_referer=url_video,
            start_chunk=start_chunk,
        )

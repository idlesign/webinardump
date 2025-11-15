from pathlib import Path

import pytest


@pytest.fixture
def mock_call(monkeypatch):
    calls = []

    def mock_call(cmd, **kwargs):
        if 'ffmpeg' in cmd:
            Path('yatst/all_chunks.mp4').write_bytes(b'')

        calls.append(cmd)

    monkeypatch.setattr("webinardump.utils.check_call", mock_call)

    return calls

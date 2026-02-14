from pathlib import Path

import pytest


@pytest.fixture
def mock_call(monkeypatch):
    calls = []

    def mock_call(cmd, **kwargs):
        if 'ffmpeg' in cmd:
            cwd = kwargs.get('cwd') or Path()
            (Path(cwd) / 'all_chunks.mp4').write_bytes(b'')

        calls.append(cmd)

    monkeypatch.setattr("webinardump.utils.check_call", mock_call)

    return calls

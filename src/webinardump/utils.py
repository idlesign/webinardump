import logging
from pathlib import Path
from subprocess import check_call

LOGGER = logging.getLogger('webinardump')


def call(cmd: str, *, path: Path):
    return check_call(cmd, cwd=path, shell=True)

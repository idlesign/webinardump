import logging
import re
from pathlib import Path
from subprocess import check_call

LOGGER = logging.getLogger('webinardump')
RE_DIGITS = re.compile(r'(\d+)')



def call(cmd: str, *, path: Path):
    return check_call(cmd, cwd=path, shell=True)


def get_files_sorted(path: Path, *, suffixes: set[str]) -> list[str]:
    def natural(text):
        return [(int(ch), ch) if ch.isdigit() else ch for ch in RE_DIGITS.split(text) if ch]

    files = [file.name for file in path.iterdir() if file.is_file() and file.suffix in suffixes]
    files.sort(key=natural)

    return files

import logging
from pathlib import Path

from webinardump.dumpers import YandexDisk

logging.basicConfig(level=logging.INFO, format='%(levelname)-8s: %(message)s')


dumper = YandexDisk(target_dir=Path('../tools/dumped/'))

dumper.run({
    'url_video': 'https://disk.yandex.ru/i/xxx',
})

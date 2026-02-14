# webinardump

<https://github.com/idlesign/webinardump>

[![PyPI - Version](https://img.shields.io/pypi/v/webinardump)](https://pypi.python.org/pypi/webinardump)
[![License](https://img.shields.io/pypi/l/webinardump)](https://pypi.python.org/pypi/webinardump)
[![Coverage](https://img.shields.io/coverallsCoverage/github/idlesign/webinardump)](https://coveralls.io/r/idlesign/webinardump)

## Описание

*Приложение позволяет скачать запись вебинара и сохранить в виде .mp4 файла.*


## Откуда качает

* Яндекс.Диск (записи стримов, общие файлы)
* webinar.ru


## Зависимости

Что нужно иметь для запуска приложения и работы с ним.

* Linux (Unix)
* Python 3.11+
* ffmpeg (для Ubuntu: `sudo apt install ffmpeg`)
* uv (для установки и обновления приложения)
* Базовые знания о работе в браузере с отладочной консолью.


## Установка и обновление

Производится при помощи приложения [uv](https://docs.astral.sh/uv/getting-started/installation/):

```shell
$ uv tool install webinardump
```

После этого запускать приложение можно командой

```shell
$ webinardump
```

Для обновления выполните

```shell
$ uv tool upgrade webinardump
```

## Как использовать

Переместитесь в желаемый каталог и выполните следующую команду. 

```shell

; Указываем путь для скачивания - my_webinar_dir/
; Указываем таймаут запросов - 10 секунд
; Указываем максимальное количество одновременных запросов - 20
$ webinardump --target my_webinar_dir/ --timeout 10 --rmax 20
```
Приложение скачает фрагменты вебинара, а потом соберёт из них единый файл.


### disk.yandex.ru

1. Взять ссылку на вебинар. Вида https://disk.yandex.ru/i/xxx или https://disk.yandex.ru/d/xxx/yyy.mp4
2. Запустить скачиватель и скормить ему ссылку из предыдущего пункта.


### webinar.ru

Процесс скачивания автоматизирован не полностью, потребуется искать
некоторые ссылки при помощи браузера.

1. Взять ссылку на вебинар. Вида https://events.webinar.ru/event/xxx/yyy/zzz
2. Открыть в браузере.
3. Включить отладочную консоль (F12).
4. Запустить воспроизведение.
5. Отыскать ссылку с `record-new/` и запомнить её.
6. Отыскать ссылку, оканчивающуюся на `chunklist.m3u8` и запомнить её.
7. Запустить скачиватель и скормить ему ссылки и двух предыдущих пунктов.

## Для разработки

При разработке используется [makeapp](https://pypi.org/project/makeapp/). Ставим:

```shell
$ uv tool install makeapp
```

После клонирования репозитория sponsrdump, в его директории выполняем:

```shell
# ставим утилиты
$ ma tools

# инициализируем виртуальное окружение
$ ma up --tool

# теперь в окружении доступны зависимости и команда sponsrdump
```

Проверь стиль перед отправкой кода на обзор:

```shell
# проверяем стиль
$ ma style
```

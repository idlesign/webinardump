# Установка webinardump

Рекомендуется установка при помощи [uv](https://docs.astral.sh/uv/), хотя можно обойтись и обычным `pip`.

## Из PyPI

Приложение устанавливается как изолированная утилита:

```bash
uv tool install webinardump
```

Обновление:

```bash
uv tool upgrade webinardump
```

или с помощью pip:

```bash
pip install webinardump
```

## Из исходников

Клонируем репозиторий и синхронизируем среду разработки:

```bash
git clone https://github.com/idlesign/webinardump webinardump
cd webinardump
uv sync
```

Команды в среде проекта запускаются через `uv run`.

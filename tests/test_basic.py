from webinardump.dumpers import WebinarRu, YandexDisk

CALLS = [
    'for i in `ls *.ts | sort -V`; do echo "file $i"; done >> all_chunks.txt',
    'ffmpeg -f concat -i all_chunks.txt -c copy -bsf:a aac_adtstoasc all_chunks.mp4'
]


def test_yadisk(response_mock, tmp_path, datafix_read, datafix_readbin, mock_call):
    data_manifest = datafix_read('manifest_yadisk.html')
    data_m3u = datafix_read('vid.m3u')
    data_ts = datafix_readbin('empty.ts')

    with response_mock([
        f'GET https://disk.yandex.ru/i/xxx -> 200:{data_manifest}',
        f'GET https://here/there.m3u8 -> 200:{data_m3u}',
        b'GET https://here/1.ts?some=other1 -> 200:' + data_ts,
        b'GET https://here/2.ts?some=other2 -> 200:' + data_ts,
    ]):
        fpath = YandexDisk(target_dir=tmp_path).run({
            'url_video': 'https://disk.yandex.ru/i/xxx',
        })
        assert fpath
        assert mock_call == CALLS


def test_webinarru(response_mock, tmp_path, datafix_read, datafix_readbin, mock_call):
    data_manifest = datafix_read('manifest_webinarru.json')
    data_m3u = datafix_read('vid.m3u')
    data_ts = datafix_readbin('empty.ts')

    with response_mock([
        'GET https://events.webinar.ru/api/eventsessions/aaa/record/isviewable?'
        f'recordAccessToken=bbb -> 200:{data_manifest}',

        f'GET https://here/there.m3u8 -> 200:{data_m3u}',
        b'GET https://here/1.ts?some=other1 -> 200:' + data_ts,
        b'GET https://here/2.ts?some=other2 -> 200:' + data_ts,
    ]):
        fpath = WebinarRu(target_dir=tmp_path).run({
            'url_video': ' https://events.webinar.ru/xxx/yyy/record-new/aaa/bbb',
            'url_playlist': 'https://here/there.m3u8',
        })
        assert fpath
        assert mock_call == CALLS

from webinardump.utils import get_files_sorted


def test_get_files_sorted(tmp_path):

    (tmp_path / '1.a').touch()
    (tmp_path / '01.a').touch()
    (tmp_path / '02.a').touch()
    (tmp_path / '9.a').touch()
    (tmp_path / '1.b').touch()
    (tmp_path / '10.a').touch()
    (tmp_path / '11.a').touch()

    fnames = get_files_sorted(tmp_path, suffixes={'.a'})
    assert fnames == ['01.a', '1.a', '02.a', '9.a', '10.a', '11.a']

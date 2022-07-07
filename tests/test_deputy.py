import os
import pathlib

import pytest

from hades.deputy.server import replace_file


class TestFileReplacement:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.file = tmp_path / "file"
        yield
        self.file.unlink(missing_ok=True)

    @pytest.mark.parametrize(
        ("content", "encoding"),
        (
            (b"bytes\n", None),
            ("ASCII\n", "ascii"),
            ("Ünicöde\n", "utf-8"),
        )
    )
    def test_replace_file_contents(self, content, encoding):
        replace_file(self.file, [content], encoding=encoding)
        if encoding is None:
            got = self.file.read_bytes()
        else:
            got = self.file.read_text(encoding)
        assert content == got

    def test_replace_file_replaces(self):
        self.file.touch(0o0666, exist_ok=False)
        original_content = b"test\n"
        new_content = b"replaced\n"
        with self.file.open("w+b") as original:
            original.write(original_content)
            original.seek(0, os.SEEK_SET)
            replace_file(self.file, [new_content])
            got1 = original.read()
            got2 = self.file.read_bytes()

        assert (original_content, new_content) == (got1, got2)

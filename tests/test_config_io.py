import json

import pytest

from conftest import EXAMPLE
from fg_gui import config_io


def test_parse_roundtrip():
    text = config_io.dumps(EXAMPLE)
    assert config_io.parse(text) == EXAMPLE
    assert config_io.parse(text.encode("utf-8-sig")) == EXAMPLE


@pytest.mark.parametrize("bad", ["{", "[1, 2]", "42"])
def test_parse_rejects(bad):
    with pytest.raises(config_io.ConfigError):
        config_io.parse(bad)


def test_list_examples(tmp_path):
    (tmp_path / "b.json").write_text(json.dumps(EXAMPLE))
    (tmp_path / "a.json").write_text("{}")
    (tmp_path / "notes.txt").write_text("x")
    assert [p.name for p in config_io.list_examples(tmp_path)] == ["a.json", "b.json"]
    assert config_io.list_examples(None) == []
    assert config_io.list_examples(tmp_path / "fehlt") == []


def test_summary():
    s = config_io.summary(EXAMPLE)
    assert s["Dimension"] == "1D" and s["Schichten"] == 1 and s["Schichttypen"] == "lamellar1d"
    assert config_io.summary({})["Schichten"] == 0

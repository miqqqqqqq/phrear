"""project.toml validation and round trip."""

from __future__ import annotations

from datetime import datetime

import pytest

from phrear.errors import ProjectError
from phrear.project.config import (
    ConstantHeads,
    ModelTime,
    ProjectConfig,
    dump_config,
    parse_config,
)

MINIMAL = """
schema_version = 1
software_version_created = "0.1.0"
software_version_last_saved = "0.1.0"
name = "Test"
crs = 7791

[model]
start_date = 2020-01-01
end_date = 2021-01-01
"""


def _config() -> ProjectConfig:
    return parse_config(MINIMAL)


def test_minimal_file_gets_defaults() -> None:
    cfg = _config()
    assert cfg.model.start_date == datetime(2020, 1, 1)
    assert cfg.model.steady_initial is True
    assert cfg.units.discharge == "l/s"
    assert cfg.grid.type == "dis"
    assert cfg.options.newton is True
    assert cfg.initial_heads is None


def test_roundtrip_preserves_values_and_writes_dates_as_dates() -> None:
    cfg = _config()
    cfg.initial_heads = ConstantHeads(value_m=12.5)
    cfg.model.period_breaks = [datetime(2020, 6, 1)]
    text = dump_config(cfg)
    assert "start_date = 2020-01-01\n" in text
    assert parse_config(text) == cfg


def test_rewrite_keeps_user_comments() -> None:
    previous = MINIMAL.replace('name = "Test"', 'name = "Test"  # nome del sito')
    cfg = parse_config(previous)
    cfg.description = "aggiornato"
    text = dump_config(cfg, previous)
    assert "# nome del sito" in text
    assert 'description = "aggiornato"' in text


@pytest.mark.parametrize(
    ("replace", "by", "location"),
    [
        ("end_date = 2021-01-01", "end_date = 2019-01-01", "model"),
        ("crs = 7791", 'crs = "abc"', "crs"),
        ("[model]", "typo_key = 1\n[model]", "typo_key"),
    ],
)
def test_invalid_values_report_location(replace: str, by: str, location: str) -> None:
    with pytest.raises(ProjectError) as exc:
        parse_config(MINIMAL.replace(replace, by))
    assert exc.value.code == "project.config_invalid"
    assert location in exc.value.message("it")


def test_syntax_error_has_its_own_code() -> None:
    with pytest.raises(ProjectError) as exc:
        parse_config("name = ")
    assert exc.value.code == "project.config_syntax"


def test_period_breaks_must_be_inside_the_period() -> None:
    with pytest.raises(ValueError, match="outside"):
        ModelTime(
            start_date=datetime(2020, 1, 1),
            end_date=datetime(2021, 1, 1),
            period_breaks=[datetime(2022, 1, 1)],
        )


def test_period_breaks_are_sorted() -> None:
    model = ModelTime(
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2021, 1, 1),
        period_breaks=[datetime(2020, 9, 1), datetime(2020, 3, 1)],
    )
    assert model.period_breaks == [datetime(2020, 3, 1), datetime(2020, 9, 1)]


def test_preferred_units_are_checked_against_their_quantity() -> None:
    with pytest.raises(ProjectError) as exc:
        parse_config(MINIMAL + '\n[units]\ndischarge = "m/s"\n')
    assert exc.value.code == "project.config_invalid"


def test_expert_solver_options_require_expert_preset() -> None:
    with pytest.raises(ProjectError):
        parse_config(MINIMAL + "\n[solver]\nims = { outer_maximum = 200 }\n")

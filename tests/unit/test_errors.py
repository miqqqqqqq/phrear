"""Error catalogue and error objects."""

from __future__ import annotations

import pytest

from phrear.errors import (
    CATALOG,
    InternalError,
    Localized,
    ObjectRef,
    PhrearError,
    UnitError,
    UsageError,
    placeholders,
)


@pytest.mark.parametrize("code", sorted(CATALOG))
def test_catalog_entry_is_complete_and_consistent(code: str) -> None:
    message = CATALOG[code]
    assert message.it and message.en, "message missing in one language"
    assert message.hint_it and message.hint_en, "hint missing in one language"
    assert placeholders(message.it) == placeholders(message.en)
    assert placeholders(message.hint_it) == placeholders(message.hint_en)


def test_codes_are_namespaced() -> None:
    for code in CATALOG:
        namespace, _, name = code.partition(".")
        assert namespace and name, code


def test_error_renders_both_languages_with_localized_fields() -> None:
    error = UnitError(
        "unit.dimension",
        unit="l/s",
        quantity=Localized("velocità", "velocity"),
        expected="m/d",
        ref=ObjectRef(kind="field", layer="hydro_units", fid=3, field="kh"),
    )
    assert error.message("it").startswith("L'unità «l/s»")
    assert "velocity" in error.message("en")
    assert error.ref is not None and error.ref.fid == 3
    assert str(error) == error.message("en")


def test_unknown_code_is_rejected() -> None:
    with pytest.raises(KeyError):
        PhrearError("does.not_exist")


def test_subclass_rejects_foreign_code() -> None:
    with pytest.raises(ValueError, match="does not admit"):
        UnitError("cli.usage", reason="x")


def test_subclass_prefixes() -> None:
    assert UsageError("cli.usage", reason="x").code == "cli.usage"
    assert InternalError("internal.unexpected").code == "internal.unexpected"

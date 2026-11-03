"""Errors shown to the user (docs/SPEC.md, sections 3.1 and 22).

Every error has a stable ``code``, a message and a hint in Italian and English,
an optional technical ``detail`` and an optional reference to the object involved
(feature, cell, period, file, ...). Message templates live in :data:`CATALOG`,
so the same code always produces the same text in both languages.
"""

from __future__ import annotations

import string
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

Lang = Literal["it", "en"]
LANGS: tuple[Lang, ...] = ("it", "en")


@dataclass(frozen=True)
class Localized:
    """A value whose text differs by language, e.g. the name of a physical quantity."""

    it: str
    en: str

    def get(self, lang: Lang) -> str:
        return self.it if lang == "it" else self.en


FieldValue = str | int | float | Localized


@dataclass(frozen=True)
class Message:
    """Message and hint templates of an error code, in both languages."""

    it: str
    en: str
    hint_it: str = ""
    hint_en: str = ""

    def template(self, lang: Lang) -> str:
        return self.it if lang == "it" else self.en

    def hint_template(self, lang: Lang) -> str:
        return self.hint_it if lang == "it" else self.hint_en


CATALOG: dict[str, Message] = {
    "cli.usage": Message(
        it="Comando non valido. {reason}",
        en="Invalid command. {reason}",
        hint_it="Esegui «phrear --help» per l'elenco dei comandi e delle opzioni.",
        hint_en="Run 'phrear --help' for the list of commands and options.",
    ),
    "unit.unknown": Message(
        it="Unità di misura non riconosciuta «{unit}».",
        en="Unrecognised unit '{unit}'.",
        hint_it="Usa una forma come m/s, l/s, m³/d, mm/anno o 1/m.",
        hint_en="Use a form such as m/s, l/s, m3/d, mm/year or 1/m.",
    ),
    "unit.dimension": Message(
        it="L'unità «{unit}» non è compatibile con la grandezza {quantity}, "
        "che si esprime per esempio in {expected}.",
        en="Unit '{unit}' is not compatible with {quantity}, "
        "which is expressed for example in {expected}.",
        hint_it="Controlla l'unità indicata e il campo a cui si riferisce.",
        hint_en="Check the unit and the field it refers to.",
    ),
    "project.exists": Message(
        it="La cartella «{path}» esiste e non è vuota.",
        en="Folder '{path}' exists and is not empty.",
        hint_it="Scegli una cartella nuova o vuota per il progetto.",
        hint_en="Choose a new or empty folder for the project.",
    ),
    "project.not_found": Message(
        it="In «{path}» non c'è un progetto, perché manca project.toml.",
        en="'{path}' is not a project, because project.toml is missing.",
        hint_it="Indica la cartella che contiene project.toml, oppure crea un progetto "
        "con «phrear new».",
        hint_en="Give the folder that contains project.toml, or create a project "
        "with 'phrear new'.",
    ),
    "project.config_syntax": Message(
        it="Il file project.toml contiene un errore di sintassi. {reason}",
        en="project.toml has a syntax error. {reason}",
        hint_it="Controlla virgolette, parentesi quadre e date nel formato AAAA-MM-GG.",
        hint_en="Check quotes, square brackets and dates in the YYYY-MM-DD format.",
    ),
    "project.config_invalid": Message(
        it="Valore non valido in project.toml, alla voce «{location}». {reason}",
        en="Invalid value in project.toml at '{location}'. {reason}",
        hint_it="Correggi la voce indicata e riprova.",
        hint_en="Fix the entry and try again.",
    ),
    "project.crs_unknown": Message(
        it="Il codice EPSG:{epsg} non corrisponde a nessun sistema di riferimento noto.",
        en="EPSG:{epsg} is not a known coordinate reference system.",
        hint_it="Usa per esempio EPSG:7791 (RDN2008 / UTM 32N) o EPSG:7792 (UTM 33N).",
        hint_en="Use for example EPSG:7791 (RDN2008 / UTM 32N) or EPSG:7792 (UTM 33N).",
    ),
    "project.crs_not_metric": Message(
        it="Il sistema EPSG:{epsg} ({crs_name}) non è proiettato in metri.",
        en="EPSG:{epsg} ({crs_name}) is not a projected system in metres.",
        hint_it="Il modello lavora in metri. Usa per esempio EPSG:7791 (RDN2008 / UTM 32N) "
        "o EPSG:7792 (UTM 33N).",
        hint_en="The model works in metres. Use for example EPSG:7791 (RDN2008 / UTM 32N) "
        "or EPSG:7792 (UTM 33N).",
    ),
    "project.schema_too_new": Message(
        it="Il progetto usa lo schema {found}, più recente di quello supportato ({supported}).",
        en="The project uses schema {found}, newer than the supported one ({supported}).",
        hint_it="Aggiorna Phrear alla versione che ha creato il progetto o successiva.",
        hint_en="Update Phrear to the version that created the project or later.",
    ),
    "project.migration_required": Message(
        it="Il progetto usa lo schema {found}, mentre questa versione usa lo schema {supported}.",
        en="The project uses schema {found}, while this version uses schema {supported}.",
        hint_it="Esegui «phrear migrate», che prima crea una copia di backup del progetto.",
        hint_en="Run 'phrear migrate', which first makes a backup copy of the project.",
    ),
    "project.gpkg_missing": Message(
        it="Nel progetto «{path}» manca il file model.gpkg.",
        en="Project '{path}' has no model.gpkg file.",
        hint_it="Ripristina il file da una copia di backup o ricrea il progetto.",
        hint_en="Restore the file from a backup or recreate the project.",
    ),
    "project.gpkg_tables_missing": Message(
        it="Nel file model.gpkg mancano le tabelle {tables}.",
        en="model.gpkg lacks the tables {tables}.",
        hint_it="Il file è stato modificato fuori da Phrear o è danneggiato. Ripristina "
        "una copia di backup.",
        hint_en="The file was changed outside Phrear or is damaged. Restore a backup copy.",
    ),
    "internal.unexpected": Message(
        it="Errore interno imprevisto.",
        en="Unexpected internal error.",
        hint_it="Segnala il problema allegando il dettaglio tecnico.",
        hint_en="Report the problem attaching the technical detail.",
    ),
}


class ObjectRef(BaseModel):
    """Where an error or warning occurred. Only the relevant fields are set."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["feature", "cell", "period", "table", "field", "file", "series"]
    layer: str | None = None
    fid: int | None = None
    cell: tuple[int, ...] | None = None
    period: int | None = None
    field: str | None = None
    path: str | None = None


def placeholders(template: str) -> set[str]:
    """Names of the ``{field}`` placeholders used by a template."""
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def render(code: str, lang: Lang, fields: dict[str, FieldValue], *, hint: bool = False) -> str:
    """Render the message (or hint) of ``code`` in ``lang``."""
    message = CATALOG[code]
    template = message.hint_template(lang) if hint else message.template(lang)
    values = {k: v.get(lang) if isinstance(v, Localized) else v for k, v in fields.items()}
    return template.format(**values)


class PhrearError(Exception):
    """Base class of the errors reported to the user.

    Subclasses restrict the admitted codes through :attr:`prefix`.
    """

    prefix: str = ""

    def __init__(
        self,
        code: str,
        *,
        ref: ObjectRef | None = None,
        detail: str = "",
        **fields: FieldValue,
    ) -> None:
        if code not in CATALOG:
            raise KeyError(f"unknown error code {code!r}")
        if not code.startswith(self.prefix):
            raise ValueError(f"{type(self).__name__} does not admit code {code!r}")
        self.code = code
        self.ref = ref
        self.detail = detail
        self.fields: dict[str, FieldValue] = dict(fields)
        super().__init__(self.message("en"))

    def message(self, lang: Lang = "it") -> str:
        return render(self.code, lang, self.fields)

    def hint(self, lang: Lang = "it") -> str:
        return render(self.code, lang, self.fields, hint=True)


class UsageError(PhrearError):
    """Invalid command line."""

    prefix = "cli."


class UnitError(PhrearError):
    """Unit of measure missing, unknown or incompatible with the quantity."""

    prefix = "unit."


class ProjectError(PhrearError):
    """Project folder, project.toml or GeoPackage missing, invalid or outdated."""

    prefix = "project."


class InternalError(PhrearError):
    """Unexpected failure inside the software, not caused by the input."""

    prefix = "internal."

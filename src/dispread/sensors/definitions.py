"""Unveraenderliche Daten eines Sensorpakets mit Schema 1."""

from dataclasses import dataclass
from pathlib import Path

GSV2AS_FORMAT_RULE = "gsv2as_v1"
CHAR_NUMBER_FORMAT_RULE = "char_number_v1"


@dataclass(frozen=True, slots=True)
class TemplateRef:
    file: str
    sha256: str


@dataclass(frozen=True, slots=True)
class LatticeDefinition:
    left: float
    pitch: float
    top: float
    bottom: float
    target_size: tuple[int, int]


@dataclass(frozen=True, slots=True)
class RolesDefinition:
    sign: tuple[int, ...]
    number: tuple[int, ...]
    separator: tuple[int, ...]
    unit: tuple[int, ...]
    blank: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class AnchorDefinition:
    char: str
    cell: int


@dataclass(frozen=True, slots=True)
class FormatDefinition:
    rule: str
    digits: int
    sign_chars: tuple[str, ...]
    leading_zero_rule: str
    decimal: str = "point"
    min_digits: int | None = None


@dataclass(frozen=True, slots=True)
class DisplayDefinition:
    schema: int
    family: str
    polarity: str
    cells: int
    rows: int
    lattice: LatticeDefinition
    roles: RolesDefinition
    anchor: AnchorDefinition | None
    format: FormatDefinition

    @property
    def empty_cells(self) -> tuple[int, ...]:
        return tuple(sorted(self.roles.separator + self.roles.blank))

    @property
    def classified_cells(self) -> int:
        return len(self.roles.sign) + len(self.roles.number) + len(self.roles.separator)

    @property
    def blank_cells(self) -> tuple[int, ...]:
        return self.roles.blank


@dataclass(frozen=True, slots=True)
class SensorDefinition:
    schema: int
    id: str
    version: int
    status: str
    display_name: str
    manufacturer: str
    aliases: tuple[str, ...]
    device_id: str
    unit: str
    release_notice: str
    templates: TemplateRef
    display: DisplayDefinition
    directory: Path

    @property
    def templates_path(self) -> Path:
        path = self.directory / self.templates.file
        if path.is_symlink():
            raise ValueError(f"Symlink als Vorlagendatei unzulaessig: {path}")
        return path

    @property
    def profile_ref(self) -> str:
        return f"{self.id}@{self.version}"

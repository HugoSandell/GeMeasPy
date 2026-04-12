import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from . import terrameter


class Task:
    """A terrameter task"""

    def __init__(
        self,
        id: int,
        name: str,
        spread_file: str,
        protocol_file: str,
        spacing: tuple[float, float, float],
        base_reference: tuple[float, float, float],
    ):
        self.id: int = id
        self.name: str = name
        self.spread_file: str = spread_file
        self.protocol_file: str = protocol_file
        self.spacing: tuple[float, float, float] = spacing
        self.base_reference: tuple[float, float, float] = base_reference
        self.is_complete: bool = False


def _parse_child[T](parent: ET.Element, tag: str, t: Callable[[Any], T]) -> T:
    if (child := parent.find(tag)) is not None:
        try:
            return t((child.text or "").strip())
        except ValueError:
            raise terrameter.ParseError(f"Failed to parse {tag} as int")
    else:
        raise terrameter.ParseError(f"Missing <{tag}> element")


def _parse_optional_child[T](
    parent: ET.Element, tag: str, t: Callable[[Any], T]
) -> T | None:
    if (child := parent.find(tag)) is not None:
        try:
            return t((child.text or "").strip())
        except ValueError:
            raise terrameter.ParseError(f"Failed to parse {tag} as int")
    else:
        return None


@dataclass
class CreateStation:
    name: str
    x: int
    y: int
    z: int
    excludes: list[str]

    @staticmethod
    def from_element(el: ET.Element):
        name = _parse_child(el, "Name", str)
        x = _parse_optional_child(el, "X", int) or 0
        y = _parse_optional_child(el, "Y", int) or 0
        z = _parse_optional_child(el, "Z", int) or 0
        excludes = [(exclude.text or "").strip() for exclude in el.iterfind("Exclude")]
        return CreateStation(
            name=name,
            x=x,
            y=y,
            z=z,
            excludes=excludes,
        )


@dataclass
class Vec3i:
    x: int
    y: int
    z: int

    @staticmethod
    def from_element(el: ET.Element):
        x = _parse_optional_child(el, "X", int) or 0
        y = _parse_optional_child(el, "Y", int) or 0
        z = _parse_optional_child(el, "Z", int) or 0
        return Vec3i(
            x=x,
            y=y,
            z=z,
        )


@dataclass
class Spread:
    name: str
    version: str | None
    description: str
    create_stations: list[CreateStation]
    rollalong: Vec3i | None  # fallback if `create_stations` is empty
    pole_mode: str | None
    # cable: TODO

    @staticmethod
    def parse(src: str):
        root = ET.fromstring(src)

        if root.tag != "Spread":
            raise terrameter.ParseError("Root tag is not <Spread>")

        name = _parse_child(root, "Name", str)
        version = _parse_optional_child(root, "Version", str)
        description = _parse_child(root, "Description", str)
        create_stations = [
            CreateStation.from_element(create_station)
            for create_station in root.iterfind("CreateStation")
        ]
        rollalong = None
        if (el := root.find("Rollalong")) is not None:
            rollalong = Vec3i.from_element(el)
        pole_mode = _parse_optional_child(root, "PoleMode", str)

        return Spread(
            name=name,
            version=version,
            description=description,
            create_stations=create_stations,
            rollalong=rollalong,
            pole_mode=pole_mode,
        )


@dataclass
class Protocol:
    name: str
    description: str
    arraycode: int
    spread_files: list[str]
    # user_select: TODO
    # sequence: TODO

    @staticmethod
    def parse(src: str):
        root = ET.fromstring(src)

        if root.tag != "Protocol":
            raise terrameter.ParseError("Root tag is not <Protocol>")

        name = _parse_child(root, "Name", str)
        description = _parse_child(root, "Description", str)
        arraycode = _parse_child(root, "Arraycode", int)
        spread_files = [
            (spread_file.text or "").strip()
            for spread_file in root.iterfind("SpreadFile")
        ]
        if len(spread_files) == 0:
            raise terrameter.ParseError("Missing <SpreadFile> element")

        return Protocol(
            name=name,
            description=description,
            arraycode=arraycode,
            spread_files=spread_files,
        )

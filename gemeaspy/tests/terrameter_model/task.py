from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from . import project, terrameter


class Task:
    """A terrameter task"""

    def __init__(
        self,
        id: int,
        name: str,
        spread_file: str,
        protocol_file: str,
        spread: Spread | None,
        protocol: Protocol | None,
        spacing: tuple[float, float, float],
        base_reference: tuple[float, float, float],
    ):
        self.id: int = id
        self.name: str = name
        self.spread_file: str = spread_file
        self.protocol_file: str = protocol_file
        self.spread: Spread | None = spread
        self.protocol: Protocol | None = protocol
        self.spacing: tuple[float, float, float] = spacing
        self.base_reference: tuple[float, float, float] = base_reference
        self.stations: list[project.Station] = []
        self.is_complete: bool = False

    @dataclass
    class CreateStationResult:
        station: project.Station
        index_selection: int
        max_index_selection: int
        pos_before: Vec3i
        rollalong: Vec3i

    def create_station(self, id: int, index_selection: str) -> CreateStationResult:
        first = len(self.stations) == 0
        try:
            actual_index_selection = int(index_selection)
        except ValueError:
            actual_index_selection = 1 if first else 2
        rollalongs = self.spread.get_rollalongs() if self.spread else [Vec3i(0, 0, 0)]
        if actual_index_selection not in range(0, len(rollalongs)):
            actual_index_selection = len(rollalongs) - 1
        pos_now = Vec3i(0, 0, 0) if first else self.stations[-1].pos
        rollalong = rollalongs[actual_index_selection]
        new_station = project.Station(id=id, pos=pos_now + rollalong)
        self.stations.append(new_station)
        return self.CreateStationResult(
            station=new_station,
            index_selection=actual_index_selection,
            max_index_selection=len(rollalongs) - 1,
            pos_before=pos_now,
            rollalong=rollalong,
        )


@dataclass
class TaskSpec:
    name: str
    spread: str
    protocol: str
    spacing: tuple[float, float, float]
    base_reference: tuple[float, float, float]
    settings: str | None = None


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
        return Vec3i(x=x, y=y, z=z)

    def __add__(self, rhs: Vec3i) -> Vec3i:
        return Vec3i(x=self.x + rhs.x, y=self.y + rhs.y, z=self.z + rhs.z)

    def __str__(self) -> str:
        return f"{self.x};{self.y};{self.z}"


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

    def get_rollalongs(self) -> list[Vec3i]:
        if self.create_stations:
            return [Vec3i(0, 0, 0)] + [
                Vec3i(create_station.x, create_station.y, create_station.z)
                for create_station in self.create_stations
            ]
        elif self.rollalong:
            return [Vec3i(0, 0, 0), Vec3i(0, 0, 0), self.rollalong]
        else:
            return [Vec3i(0, 0, 0)]


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

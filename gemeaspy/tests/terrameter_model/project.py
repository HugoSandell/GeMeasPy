from dataclasses import dataclass
from io import BytesIO

from .database import ProjectDatabase
from .project_types import TasksRow
from .task import Protocol, Spread, Task, Vec3i


@dataclass
class Station:
    """A terrameter station"""

    id: int
    pos: Vec3i


class NoTaskError(Exception):
    """Raised when an operation needs a task but none is active"""


class Project:
    """A terrameter project"""

    def __init__(self, name: str, db: BytesIO):
        self.name: str = name
        self.db = ProjectDatabase(db)
        self.tasks: list[Task] = []
        self.stations: list[Station] = []
        self.current_task_index: int | None = None

    def create_task(
        self,
        name: str,
        spread_file: str,
        protocol_file: str,
        spread: Spread | None,
        protocol: Protocol | None,
        spacing: tuple[float, float, float],
        base_reference: tuple[float, float, float],
    ) -> Task:
        """Add a task to the project. Returns the task"""
        task_name_number = 1
        done = False
        # Find unused number suffix
        while not done:
            done = True # Assume done (unique name + suffix)
            for task in self.tasks:
                if task.name == f"{name}_{task_name_number}":
                    task_name_number += 1
                    done = False # Counter-example found
        id = len(self.tasks) + 1
        resolved_name = f"{name}_{task_name_number}"
        new_task = Task(
            id,
            resolved_name,
            spread_file,
            protocol_file,
            spread,
            protocol,
            spacing,
            base_reference,
        )
        self.tasks.append(new_task)
        self.current_task_index = id - 1

        task_row = TasksRow()
        task_row.ID = id
        task_row.Name = resolved_name
        # TODO remaining columns
        self.db.tasks().append(task_row)
        self.db.write()

        return new_task

    def create_station(self, index_selection: str) -> Task.CreateStationResult:
        """Add a station to the project."""
        if self.current_task_index is None:
            raise NoTaskError()
        id = len(self.stations) + 1
        result = self.tasks[self.current_task_index].create_station(id, index_selection)
        self.stations.append(result.station)
        return result

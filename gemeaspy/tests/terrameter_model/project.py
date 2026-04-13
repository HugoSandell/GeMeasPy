from .task import Protocol, Spread, Task


class Station:
    """A terrameter station"""
    def __init__(self, id: str):
        self.id: str = id

class Project:
    """A terrameter project"""
    def __init__(self, name: str):
        self.name: str = name
        self.tasks: list[Task] = []
        self.stations: list[Station] = []

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
        new_task = Task(
            id,
            f"{name}_{task_name_number}",
            spread_file,
            protocol_file,
            spread,
            protocol,
            spacing,
            base_reference,
        )
        self.tasks.append(new_task)
        return new_task

    def create_station(self, id: str):
        """Add a station to the project."""
        new_station = Station(id)
        self.stations.append(new_station)
import typing

class Task:
    """A terrameter task"""
    def __init__(self, id: int, name: str, 
                 spread_file: str, protocol_file: str, 
                 spacing: tuple[float, float, float], unknown: tuple[float, float, float]):
        self.id: int = id
        self.name: str = name
        self.spread_file: str = spread_file
        self.protocol_file: str = protocol_file
        self.spacing: tuple[float, float, float] = spacing
        self.unknown: tuple[float, float, float] = unknown
        self.is_complete: bool = False

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

    def create_task(self, name: str, 
                    spread_file: str, protocol_file: str, 
                    spacing: tuple[float, float, float], unknown: tuple[float, float, float]) -> int:
        """Add a task to the project. Returns the index of the task"""
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
        new_task = Task(id, f"{name}_{task_name_number}", spread_file, protocol_file, spacing, unknown)
        self.tasks.append(new_task)
        return id - 1

    def create_station(self, id: str):
        """Add a station to the project."""
        new_station = Station(id)
        self.stations.append(new_station)
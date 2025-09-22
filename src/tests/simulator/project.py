from typing import *

class Task:
    """A terrameter task"""
    def __init__(self, id: int, name: str, 
                 spread_file: str, protocol_file: str, 
                 spacing: Tuple[int, int, int], unknown: Tuple[int, int, int]):
        self.id: int = id
        self.name: str = name
        self.spread_file: str = spread_file
        self.protocol_file: str = protocol_file
        self.spacing: Tuple[int, int, int] = spacing
        self.unknown: Tuple[int, int, int] = unknown
        self.is_complete: bool = False

class Project:
    """A terrameter project"""
    def __init__(self, name: str):
        self.name: str = name
        self.tasks: List[Task] = []

    def create_task(self, name: str, 
                    spread_file: str, protocol_file: str, 
                    spacing: Tuple[int, int ,int], unknown: Tuple[int, int, int]) -> int:
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
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

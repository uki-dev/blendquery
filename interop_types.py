from typing import Union, List, Tuple
from dataclasses import dataclass, field

@dataclass
class ParametricObjectNode:
    name: str
    material: Union[str, None] = None
    children: List['ParametricObjectNode'] = field(default_factory=list)
    vertices: List[Tuple[float, float, float]] = field(default_factory=list)
    faces: List[Tuple[int, int, int]] = field(default_factory=list)

class BlendQueryBuildException(Exception):
    def __init__(self, message):
        super().__init__(message)

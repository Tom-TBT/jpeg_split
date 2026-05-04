from dataclasses import dataclass
import numpy as np

@dataclass
class QuantTable:
    id: int
    values: np.ndarray

@dataclass
class HuffTable:
    tc: int
    th: int
    bits: list[int]
    huffval: list[int]
    enc: dict[int, str]
    dec: dict[str, int]

@dataclass
class SOFInfo:
    marker: int
    precision: int
    height: int
    width: int
    components: list[dict]

@dataclass
class SOSInfo:
    components: list[tuple[int, int, int]]
    ss: int
    se: int
    ah: int
    al: int
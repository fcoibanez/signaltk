from dataclasses import dataclass
from datetime import datetime


@dataclass
class SignalsConfig:
    """
    Configuration for investment signals computation and processing.
    """

    START_DT = datetime(1984, 12, 31)
    END_DT = datetime(2024, 12, 31)

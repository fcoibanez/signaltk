from enum import Enum
import os

WDIR = os.getcwd()


class SignalType(Enum):
    PRICE = "price"
    VOLUME = "volume"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"

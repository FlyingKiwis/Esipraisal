from enum import Enum

class Source(int, Enum):
    Invalid = ("None")
    MarketOrders = ("Market Orders")
    HistoricalOrders = ("Historical Orders")
    CCP = ("CCP")

    
    def __new__(cls, label):
        value = len(cls.__members__) + 1
        obj = int.__new__(cls, value)
        obj.label = label
        obj._value_ = value
        return obj

    def __str__(self):
        return self.label

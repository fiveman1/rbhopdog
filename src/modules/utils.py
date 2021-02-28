# utils.py
class Incrementer:
    def __init__(self, i:int):
        self.__value__ = i - 1
    def increment(self) -> int:
        self.__value__ += 1
        return self.__value__
    def get(self) -> int:
        return self.__value__ + 1
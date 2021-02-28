# utils.py

# increment(inc=1): returns i + inc (default i++)
# get(): returns i
class Incrementer:
    def __init__(self, i:int):
        self.__value__ = i
    def increment(self, inc:int=1) -> int:
        self.__value__ += inc
        return self.__value__ - inc
    def get(self) -> int:
        return self.__value__
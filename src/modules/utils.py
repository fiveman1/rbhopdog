# utils.py
from typing import List

# increment(inc=1): returns i then increments it by inc (default i++)
# get(): returns i
class Incrementer:
    def __init__(self, i:int):
        self.__value__ = i
    def increment(self, inc:int=1) -> int:
        self.__value__ += inc
        return self.__value__ - inc
    def get(self) -> int:
        return self.__value__

class StringBuilder:
    def __init__(self):
        self.message = []
    def append(self, s:str):
        self.message.append(s)
    def build(self) -> str:
        return "".join(self.message)

def page_messages(msg:str, max_length=1990) -> List[str]:
    messages = []
    length = 0
    s = StringBuilder()
    for line in msg.split("\n"):
        line_length = len(line) + 1
        length += line_length
        if length > max_length:
            messages.append(s.build())
            s = StringBuilder()
            length = line_length
        s.append(line)
        s.append("\n")
    messages.append(s.build())
    return messages
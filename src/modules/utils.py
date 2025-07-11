# utils.py
import datetime
import json
import os
import time
from typing import List

TRACEBACK_CHANNEL = 812768023920115742

def fix_path(path):
    return os.path.abspath(os.path.expanduser(path))

def open_json(path):
    with open(fix_path(path)) as file:
        data = file.read()
        return json.loads(data)

def fmt_md_code(s : str) -> str:
    s = s.replace("`", "") # don't allow the ` character to prevent escaping code blocks
    return f"```\n{s}```"

def between(lo, val, hi):
    return val >= lo and val <= hi

def utc2local(date: str):
    utc = datetime.datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")
    epoch = time.mktime(utc.timetuple())
    offset = datetime.datetime.fromtimestamp(epoch) - datetime.datetime.utcfromtimestamp(epoch)
    return int((utc + offset).timestamp())

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
        if not line:
            continue
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

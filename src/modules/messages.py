# messages.py
from typing import List

def page_messages(msg, max_length=2000) -> List[str]:
        ls = []
        lines = msg.split("\n")
        items = len(lines)
        length = 0
        page = ""
        i = 0
        #add each line together until the total length exceeds max_length
        #then create a new string (message)
        while i < items:
            while i < items and length + len(lines[i]) + 2 < max_length:
                page += lines[i] + "\n"
                length += len(lines[i]) + 2
                i += 1
            ls.append(page)
            length = 0
            page = ""
        if ls[len(ls) - 1] == "\n":
            ls = ls[:-1]
        return ls
from typing import Callable
from pathlib import Path

def read(filename: str|Path) -> str:
    content = ""
    with open(filename, 'r', encoding='utf-8') as file:
        content = file.read()
    return content


def read_lines(filename: str|Path, callback: Callable[[int, str], None]):
    index = 0
    with open(filename, 'r', encoding='utf-8') as file:
        for line in file:
            callback(index, line)
            index+=1
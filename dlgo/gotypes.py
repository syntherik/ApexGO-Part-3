import enum
#from typing import NamedTuple
from collections import namedtuple

__all__ = ['Player', 'Point']


class Player(enum.Enum):
    black = 1
    white = 2

    @property
    def other(self):
        return Player.black if self == Player.white else Player.white

    def __str__(self):
        return "white" if self == Player.white else "black"


#class Point(NamedTuple):
#    row: int
#    col: int

class Point(namedtuple('Point', 'row col')):
    def neighbors(self):
        return [
            Point(self.row - 1, self.col),
            Point(self.row + 1, self.col),
            Point(self.row, self.col - 1),
            Point(self.row, self.col + 1)
        ]

    def __deepcopy__(self, memodict=None):
        return self

# fork from https://github.com/ambionics/lightyear
from __future__ import annotations
from .iconv import convert
from .constants import *
from dataclasses import dataclass
from functools import cached_property
import base64

Byte = bytes
Digit = str
Conversion = tuple[str, str]
FilterChain = tuple[str, ...]

def data_decode(data: str) -> str:
    data += "A" * (4 - len(data) % 4)
    data = base64.b64decode(data)
    data = data.decode("utf-8", "replace")
    return data

class Lightyear:
    max_size: int
    filter_chunks: list[Chunk] = []

    def __init__(self, max_size:int = 44) -> None:
        self.max_size = max_size
        self.used_chars_map = dict()

    def _nb_dumped_bytes(self) -> int:
        return (len(self.digits) - 1) // 4 * 3
    
    def update(self, data) -> None:
        self._update_chunks(data)

    def fc(self) -> None:
        filters = [B64E, REMOVE_EQUAL]
        for chunk in self.filter_chunks:
            filters += chunk.fc
        return "/".join(filters)
    
    def output(self, decode: bool = False) -> str:
        out = ''
        for chunk in self.filter_chunks:
            out += chunk
        return data_decode(out) if decode else out
        
    def _update_chunks(self, new_data: str) -> None:
        assert len(new_data) > 0, "Data should be set" 

        split = self._find_split(new_data)
        if not split:
            raise ChunkException(f"No valid character found in {new_data}")

        char, index, reseted = split
        new_data = new_data[0:index+1]
        digit_set = DIGIT_SETS[char]
        if not reseted and len(self.filter_chunks) > 0:
            self.filter_chunks[-1].update(self.filter_chunks[-1].data + new_data, digit_set, char)
            if len(self.filter_chunks) > 1:
                prev = self.filter_chunks[-2]
                prev.update_safe_position(self.filter_chunks[-1].data)
        else:
            next = Chunk(new_data, digit_set, char)
            self.filter_chunks.append(next)

    def _find_split(self, data: str, reset_map: bool = False) -> tuple:
        if reset_map:
            self.used_chars_map = dict()

        split = None
        for i, char in enumerate(data):
            if char in self.used_chars_map or char not in DIGIT_SETS:
                continue
            split = char, i, reset_map
            self.used_chars_map[char] = True

        if split is None and not reset_map:
            return self._find_split(data, True)
        return split   


class ChunkException(Exception):
    pass

class DigitException(Exception):
    pass

@dataclass
class Chunk:
    data: str
    set: DigitSet
    split_char: str
    safe_chunk_size_fc: tuple = None

    @property
    def size(self):
        return len(self.data)

    @cached_property
    def fc(self):
        if not self.safe_chunk_size_fc:
            shortest = self.set.hex_digits[0][1]
            digit_fc = shortest * 5
        else:
            digit_fc = self.safe_chunk_size_fc

        digit_fc = '/'.join(digit_fc)
        return (digit_fc,) + self.set.forward + (DECHUNK,) + self.set.back

    def update(self, data: str, set: DigitSet, split_char: str):
        self._reset_cache()
        self.data = data
        self.set = set
        self.split_char = split_char

    def update_safe_position(self, next_chunk_data: str):
        def is_safe_position(chunk_size: int):
            digit = int(chunk_size, 16)
            return len(next_chunk_data) > digit and next_chunk_data[digit] != self.split_char

        if self.safe_chunk_size_fc:
            return

        first_char = self.set.from_base(self.data[0])
        # if the first character if it is a hex and a safe chunk_size
        if first_char in NON_ZERO_HEX_DIGITS and is_safe_position(chr(first_char)):
            self.safe_chunk_size_fc = () # nothing add
        else:
             # take first safe chunk_size
            for hex_digit in self.set.hex_digits:
                if is_safe_position(hex_digit[0]):
                    self.safe_chunk_size_fc = hex_digit[1]
                    break

        # reset cache if safe_chunk_size_fc is set
        if self.safe_chunk_size_fc:
            self._reset_cache()

    def _reset_cache(self):
        del self.__dict__['fc'] # ugly reset cache

    def __radd__(self, other):
        return other.__add__(str(self))

    def __str__(self):
        return self.data


@dataclass(frozen=True)
class DigitSet:
    digit: str
    conversions: tuple[Conversion]

    @staticmethod
    def _to_filter(conversion: Conversion) -> str:
        filter = f"convert.iconv.{conversion[0]}.{conversion[1]}"
        return filter

    @cached_property
    def forward(self) -> str:
        return tuple(map(self._to_filter, self.conversions))

    @cached_property
    def back(self) -> str:
        return tuple(
            map(self._to_filter, ((x[1], x[0]) for x in reversed(self.conversions)))
        )

    @cached_property
    def state(self) -> bytes:
        state = B64_DIGITS.encode()
        for cfrom, cto in self.conversions:
            state = convert(cfrom, cto, state)
        return state
    
    @cached_property
    def hex_digits(self) -> dict[str, FilterChain]:
        couples = [
            (chr(digit), DIGIT_PREPENDERS[B64_DIGITS[p]] + B64DE + (REMOVE_EQUAL,) )
            for p, digit in enumerate(self.state)
            if digit in NON_ZERO_HEX_DIGITS
        ]
        return sorted(couples, key=lambda couple: len(couple[1]))

    def to_base(self, digit: Byte) -> str:
        return B64_DIGITS[self.state.index(digit)]

    def from_base(self, digit: str) -> str:
        return self.state[B64_DIGITS.index(digit)]

    def has_non_zero_hex_digit(self) -> bool:
        return any(digit in NON_ZERO_HEX_DIGITS for digit in self.state)


DIGIT_SETS = {
    digit: DigitSet(digit, conversions) for digit, conversions, _ in DIGIT_SETS
}
DIGIT_SETS = {
    digit: set for digit, set in DIGIT_SETS.items() if set.has_non_zero_hex_digit()
} 
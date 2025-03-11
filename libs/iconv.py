"""Provides a convert() function that converts a string from one charset to another
using iconv. We cannot use python-iconv as it memleaks.
"""

from ctypes import (
    POINTER,
    byref,
    c_char_p,
    c_int,
    c_size_t,
    c_void_p,
    create_string_buffer,
    addressof,
    CDLL,
)
from ctypes.util import find_library


__all__ = ["convert"]

# Iconv bindings, courtesy of copilot

libc = CDLL(find_library("c"))
iconv_open = libc.iconv_open
iconv_open.argtypes = [c_char_p, c_char_p]
iconv_open.restype = c_void_p

iconv = libc.iconv
iconv.argtypes = [
    c_void_p,
    POINTER(c_char_p),
    POINTER(c_size_t),
    POINTER(c_char_p),
    POINTER(c_size_t),
]
iconv.restype = c_size_t

iconv_close = libc.iconv_close
iconv_close.argtypes = [c_void_p]
iconv_close.restype = c_int


def convert(charset_from: str, charset_to: str, input_str: str) -> bytes:
    """Converts a string from one charset to another using iconv.
    If the conversion fails, an empty string is returned. Although this is not proper
    practice, it works nicely for our use case.
    """
    cd = iconv_open(charset_to.encode(), charset_from.encode())
    if cd == c_void_p(-1).value:
        raise ValueError("Failed to create iconv object")

    in_buf = create_string_buffer(input_str)
    in_size = c_size_t(len(in_buf))
    out_buf = create_string_buffer(len(in_buf) * 4)
    out_size = c_size_t(len(out_buf))

    inbuf_ptr = c_char_p(addressof(in_buf))
    outbuf_ptr = c_char_p(addressof(out_buf))

    result = iconv(
        cd, byref(inbuf_ptr), byref(in_size), byref(outbuf_ptr), byref(out_size)
    )

    libc.iconv_close(cd)

    if result == c_size_t(-1).value:
        return b""

    return out_buf[: len(out_buf) - out_size.value - 1]

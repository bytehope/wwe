import base64
import re
from requests import Request 
from dataclasses import dataclass
from urllib.parse import quote

@dataclass(frozen=True)
class Tamper:
    pattern: str


@dataclass(frozen=True)
class Encoder(Tamper):
    pattern: str = ''

    def handle(self, str: str):
        iter = re.finditer(self.pattern, str, re.S)
        for match in iter:
            str = str.replace(match.group(0), self.get_replacement(match))
        return str
    
    def get_replacement(self, match: re.Match[str]):
        raise ValueError('Not implemented')


@dataclass(frozen=True)
class B64Tamper(Encoder):
    pattern: str = '<@base64>(.+?)</@base64>'

    def get_replacement(self, match: re.Match[str]):
        return base64.b64encode(match.group(1).encode()).decode()
    

@dataclass(frozen=True)
class URLETamper(Encoder):
    pattern: str = '<@urlencode>(.+?)</@urlencode>'

    def get_replacement(self, match: re.Match[str]):
        return quote(match.group(1))


@dataclass(frozen=True)
class ReplaceTamper(Tamper):
    replacement: str

    def handle(self, str):
        return str.replace(self.pattern, self.replacement)
    

@dataclass(frozen=True)
class MultiTamper(Tamper):
    pattern: list[Tamper]

    def handle(self, str):
        for tamper in self.pattern:
            str = tamper.handle(str)
        return str
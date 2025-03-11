from rich.live import Live
from rich.text import Text
from rich.console import Console
from rich.prompt import Prompt

class SimpleLive:
    def __init__(self):
        self._buf = []
        self._index = 0
        self._live = Live(
            console=Console(),
            vertical_overflow='visible',
            get_renderable=self.renderable,
            auto_refresh=True,
        )

    def renderable(self):
        return Text('\n'.join(self._buf))

    def print(self, str: str, flush:bool):
        if self._index >= len(self._buf):
            self._buf.append('')
        self._buf[self._index] = str 
        self._index += 1
        if flush:
            self._index = 0

    def start(self):
        self._live.start()

    def stop(self):
        self._live.stop()    

class UglyLive:
    def print(self, str: str, flush:bool):
        print(str, flush=flush) 
    
    def start(self):
        pass

    def stop(self):
        pass


class LiveOutput:
    def __init__(self, enabled: bool, *, ugly:bool = False):
        self.enabled = enabled
        self.live = SimpleLive() if not ugly else UglyLive()

    def print(self, str: str, flush: bool=False):
        if self.enabled:
            return self.live.print(str, flush=flush) 
    
    def start(self):
        if self.enabled:
            self.live.start()

    def stop(self):
        if self.enabled:
            self.live.stop()
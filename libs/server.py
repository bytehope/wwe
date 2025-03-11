import http.server
import socketserver
import threading
import queue
from urllib.parse import urlparse, parse_qsl

SERVER_QUEUE = queue.Queue() 

class Server(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        query = dict(parse_qsl(urlparse(self.path).query))

        SERVER_QUEUE.put(query.get('exf'))

        self.send_response(204)
        self.end_headers()
        self.wfile.write(b"")

    def log_message(self, format, *args):
        # disable logging
        pass

def start_server(port):
    def loop():
        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer(("", port), Server) as httpd:
            print("serving at port", port)
            httpd.serve_forever()

    threading.Thread(target=loop, daemon=True).start()
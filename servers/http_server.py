"""HTTP receiver (Flask app served by waitress). Usage: python http_server.py <log.csv>

waitress is used instead of Flask's dev server because the dev server closes
the TCP connection after every request (no keep-alive), which would unfairly
add a TCP handshake to every HTTP message. waitress also sets TCP_NODELAY.
"""
import sys
from flask import Flask, request
from waitress import serve
from sink import Sink
import config

sink = Sink(sys.argv[1])
app = Flask(__name__)


@app.post("/data")
def data():
    enc = "cbor" if "cbor" in request.content_type else "json"
    sink.record(request.get_data(), enc)
    return "", 200, {"Content-Length": "0"}   # explicit length keeps the connection alive


if __name__ == "__main__":
    serve(app, host="127.0.0.1", port=config.HTTP_PORT, threads=4, _quiet=True)

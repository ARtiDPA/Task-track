"""Application entry point and HTTP server lifecycle."""
import argparse
import os
from http.server import ThreadingHTTPServer as BaseThreadingHTTPServer
from backend.app.core.auth import Auth, load_secret
from backend.app.core.config import DATA
from backend.app.persistence.store import Store
from backend.app.api.http import Handler
from pathlib import Path

class ThreadingHTTPServer(BaseThreadingHTTPServer):
    # Chromium requests the independent styles and scripts concurrently on reload.
    request_queue_size = 128


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5173)
    parser.add_argument('--database', default=os.environ.get('RITMO_DB', str(DATA / 'ritmo.sqlite3')))
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.store = Store(args.database)
    server.auth = Auth(load_secret(Path(args.database).resolve().parent))
    server.auth.check()
    print(f'Ritmo: http://localhost:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()

"""Offline discovery fixture server, isolated official H-MEM only."""
from pathlib import Path
import sys
import time
from decision_fixture import app, guard
from test_update_discovery import Fixture, NOW

if __name__ == '__main__':
    root=guard(Path(sys.argv[1])); port=int(sys.argv[2])
    state=app.State(root); state.key='ISOLATED_OFFLINE_TEST_NOT_A_CREDENTIAL'
    original_run=state.discovery.run
    def run(**kwargs):
        time.sleep(1)
        return original_run(fetcher=Fixture(),now=NOW,**kwargs)
    state.discovery.run=run
    # Existing complete interface data; no real query service or import required.
    from decision_fixture import initialize
    from test_nextwise_app import FixtureClient
    if not (root/app.INVESTIGATION/'state.json').exists(): initialize(root)
    def loader(unused):
        mem=app.retrieve_memory(root)
        return app.load_investigation(FixtureClient(mem),lambda:mem)
    server=app.ThreadingHTTPServer(('127.0.0.1',port),app.make_handler(state,loader))
    server.daemon_threads=True
    server.serve_forever()

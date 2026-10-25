"""ISOLATED TEST FIXTURE: real official H-MEM, offline CSV-derived SQL responses.

No models or Zetaris requests. Never uses the production memory root.
"""
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
import nextwise_app as app
from test_nextwise_app import FixtureClient


def guard(root):
    root = Path(root).resolve()
    if not root.is_relative_to(Path(tempfile.gettempdir()).resolve()) or root == app.memory.DEFAULT_MEMORY_ROOT.resolve():
        raise ValueError('Decision fixtures require an isolated OS temporary directory')
    return root


def call(root, operation, **fields):
    return app.memory.call_bridge(dict(operation=operation, investigation_id=app.INVESTIGATION,
                                      memory_root=str(guard(root)), **fields))


def initialize(root):
    root = guard(root)
    paths = {app.KINDS[k]: v for k, v in app.exporter.INPUTS.items()}
    result = call(root, 'import', artifacts=app.memory.import_artifacts(paths))
    assert result['ok'], result
    (root / 'ISOLATED_DECISION_TEST_FIXTURE').write_text('Never a real founder decision\n')
    return call(root, 'resume')


def server(root, port):
    root = guard(root)
    if not (root / 'ISOLATED_DECISION_TEST_FIXTURE').is_file():
        raise ValueError('Missing explicit fixture marker')
    state = app.State(root)
    state.key = 'ISOLATED_OFFLINE_TEST_NOT_A_CREDENTIAL'
    def loader(unused):
        mem = app.retrieve_memory(root)
        data = app.load_investigation(FixtureClient(mem), lambda: mem)
        data['profile']['name'] = 'ISOLATED TEST FIXTURE — ' + data['profile']['name']
        return data
    http = app.ThreadingHTTPServer(('127.0.0.1', port), app.make_handler(state, loader))
    http.daemon_threads = True
    print('ISOLATED DECISION TEST FIXTURE READY', flush=True)
    try:
        http.serve_forever()
    finally:
        http.server_close()


if __name__ == '__main__':
    server(Path(sys.argv[1]), int(sys.argv[2]))

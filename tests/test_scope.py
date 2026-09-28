from pathlib import Path

from repomind.analysis.detectors import detect
from repomind.workflow import investigate


def _write(root: Path, name: str, source: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_detectors_cover_the_focused_backend_checks(tmp_path: Path):
    _write(
        tmp_path,
        "service.py",
        "import subprocess\n"
        "password = 'super-secret'\n"
        "def run_query(cursor, user):\n"
        "    cursor.execute(f'select * from users where name = {user}')\n"
        "    subprocess.run(user, shell=True)\n"
        "def load(path):\n"
        "    handle = open(path)\n"
        "    return handle.read()\n"
        "def decode(token):\n"
        "    return jwt.decode(token, options={'verify_signature': False})\n",
    )
    _write(
        tmp_path,
        "routes.py",
        "from fastapi import Depends, FastAPI\n"
        "app = FastAPI()\n"
        "def get_db():\n"
        "    return {}\n"
        "@app.get('/items')\n"
        "def read_item(db=Depends(get_db())):\n"
        "    return db\n"
        "@app.get('/slow')\n"
        "async def slow():\n"
        "    import time\n"
        "    time.sleep(1)\n"
        "    return {}\n",
    )
    found = {item["detector"] for item in detect(tmp_path)}
    _write(
        tmp_path,
        "calls.py",
        "import requests\n"
        "def fetch(url):\n"
        "    return requests.get(url)\n"
        "def rows(db, ids):\n"
        "    out = []\n"
        "    for item in ids:\n"
        "        out.append(db.execute('select 1'))\n"
        "    return out\n",
    )
    found = {item["detector"] for item in detect(tmp_path)}
    assert {
        "hardcoded_secret",
        "sql_interpolation",
        "shell_true",
        "resource_leak",
        "weak_jwt",
        "called_dependency",
        "missing_response_model",
        "fastapi_blocking_route",
        "missing_timeout",
        "missing_retry",
        "query_in_loop",
    } <= found


def test_timeout_patch_is_proven(tmp_path: Path):
    _write(tmp_path, "api.py", "import requests\n\ndef fetch(url):\n    return requests.get(url)\n")
    _write(
        tmp_path,
        "tests/test_api.py",
        "def test_fetch_sets_a_timeout():\n"
        "    text = open('api.py', encoding='utf-8').read()\n"
        "    assert 'timeout=' in text\n",
    )
    report = investigate(tmp_path, "", use_notes=False)
    assert report["root_cause"]["detector"] == "missing_timeout"
    assert report["status"] == "proven"
    assert report["proof"]["baseline"]["passed"] is False
    assert report["proof"]["patched"]["passed"] is True


def test_blocking_sleep_patch_is_proven(tmp_path: Path):
    _write(tmp_path, "worker.py", "import time\n\nasync def work():\n    time.sleep(1)\n")
    _write(
        tmp_path,
        "tests/test_worker.py",
        "def test_work_does_not_block():\n"
        "    text = open('worker.py', encoding='utf-8').read()\n"
        "    assert 'asyncio.sleep' in text\n"
        "    assert 'time.sleep' not in text\n",
    )
    report = investigate(tmp_path, "", use_notes=False)
    assert report["root_cause"]["detector"] == "blocking_in_async"
    assert report["status"] == "proven"


def test_depends_patch_is_proven(tmp_path: Path):
    _write(
        tmp_path,
        "routes.py",
        "from fastapi import Depends, FastAPI\n"
        "app = FastAPI()\n"
        "def get_db():\n"
        "    return {}\n"
        "@app.get('/items')\n"
        "def read_item(db=Depends(get_db())):\n"
        "    return db\n",
    )
    _write(
        tmp_path,
        "tests/test_routes.py",
        "def test_read_item_does_not_call_the_dependency():\n"
        "    text = open('routes.py', encoding='utf-8').read()\n"
        "    assert 'Depends(get_db())' not in text\n"
        "    assert 'Depends(get_db)' in text\n",
    )
    report = investigate(tmp_path, "", use_notes=False)
    assert report["root_cause"]["detector"] == "called_dependency"
    assert report["status"] == "proven"

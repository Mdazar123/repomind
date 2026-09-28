from pathlib import Path

from repomind.cases import LATENCY_CASE, TOKEN_CASE
from repomind.workflow import bundled_paystream, investigate


def test_token_case_rejects_the_latency_lead_and_proves_the_clock_fix():
    report = investigate(bundled_paystream(), TOKEN_CASE, use_notes=True)
    critiques = report["critiques"]
    assert critiques[0]["accepted"] is False
    assert critiques[-1]["accepted"] is True
    assert report["status"] == "proven"
    assert report["root_cause"]["category"] == "auth"
    assert report["root_cause"]["file"].endswith("tokens.py")
    assert report["proof"]["baseline"]["passed"] is False
    assert report["proof"]["patched"]["passed"] is True
    assert report["proof"]["proven"] is True
    assert any(item["category"] == "latency" for item in report["also_found"])
    assert "now_s * 1000" in report["patch"]["diff"]
    assert "+    return token[\"exp\"] > now_s" in report["patch"]["diff"]


def test_latency_case_proves_the_batch_fix():
    report = investigate(bundled_paystream(), LATENCY_CASE, use_notes=True)
    assert report["status"] == "proven"
    assert report["root_cause"]["category"] == "latency"
    assert report["root_cause"]["detector"] == "unused_batch_call"
    assert report["proof"]["proven"] is True
    assert "transactions_for_accounts" in report["patch"]["diff"]


def test_scan_lists_both_defects_without_using_the_notes_as_the_question():
    report = investigate(bundled_paystream(), "", use_notes=False)
    titles = [report["root_cause"]["title"]] + [item["title"] for item in report["also_found"]]
    blob = " ".join(titles)
    assert "wrong unit" in blob
    assert "transactions_for" in blob


def test_scan_on_a_normal_folder_lists_real_python_defects(tmp_path: Path):
    source = tmp_path / "app.py"
    source.write_text(
        "def login(user):\n"
        "    try:\n"
        "        return user.name\n"
        "    except:\n"
        "        return missing_name\n",
        encoding="utf-8",
    )
    report = investigate(tmp_path, "", use_notes=False)
    titles = " ".join(item["title"] for item in report["findings"])
    places = " ".join(f"{item['file']}:{item['line']}" for item in report["findings"])
    assert "F821" in titles
    assert "E722" in titles
    assert "app.py" in places

    explained = investigate(tmp_path, "Why does login fail?", use_notes=True)
    hit_names = " ".join(item["name"] for item in explained["index"]["hits"])
    assert "login" in hit_names


def test_fixture_sources_stay_unmodified():
    tokens = bundled_paystream() / "paystream" / "auth" / "tokens.py"
    before = tokens.read_text(encoding="utf-8")
    investigate(bundled_paystream(), TOKEN_CASE, use_notes=True)
    assert tokens.read_text(encoding="utf-8") == before

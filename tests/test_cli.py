from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    source = str(ROOT / "src")
    env["PYTHONPATH"] = source + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "chunk_offset_check", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def execute(tmp_path: Path, docs: bytes, chunks: bytes):
    doc_file = write(tmp_path / "docs.jsonl", docs)
    chunk_file = write(tmp_path / "chunks.jsonl", chunks)
    return run_cli(str(doc_file), str(chunk_file))


def result(process: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(process.stdout)


def test_unicode_codepoint_offsets_and_exclusive_end(tmp_path: Path):
    process = execute(
        tmp_path,
        '{"id":"d","text":"A😀éZ"}\n'.encode(),
        b'{"document":"d","start":1,"end":3}\n'
        b'{"document":"d","start":4,"end":5}\n'
        b'{"document":"d","start":5,"end":5}\n',
    )
    assert process.returncode == 0
    assert result(process) == {
        "status": "valid", "document_count": 1, "chunk_count": 3,
        "unknown_document_lines": [], "reversed_lines": [], "out_of_range_lines": [],
    }


def test_escaped_newlines_and_exact_end_boundary(tmp_path: Path):
    process = execute(
        tmp_path,
        b'{"id":"d","text":"a\\nb"}\n',
        b'{"document":"d","start":3,"end":3}\n'
        b'{"document":"d","start":4,"end":4}\n',
    )
    assert process.returncode == 1
    assert result(process)["out_of_range_lines"] == [2]


def test_empty_inputs_and_empty_document(tmp_path: Path):
    process = execute(tmp_path, b'{"id":"e","text":""}\n', b'{"document":"e","start":0,"end":0}\n')
    assert process.returncode == 0
    assert result(process)["status"] == "valid"
    process = execute(tmp_path, b"", b"")
    assert process.returncode == 0
    assert result(process) == {
        "status": "valid", "document_count": 0, "chunk_count": 0,
        "unknown_document_lines": [], "reversed_lines": [], "out_of_range_lines": [],
    }


def test_unknown_reversed_and_out_of_range_findings_are_independent(tmp_path: Path):
    process = execute(
        tmp_path,
        b'{"id":"d","text":"xy"}\n',
        b'{"document":"missing","start":4,"end":1}\n'
        b'{"document":"d","start":3,"end":1}\n'
        b'{"document":"d","start":2,"end":3}\n'
        b'{"document":"d","start":1,"end":1}\n',
    )
    assert process.returncode == 1
    assert result(process) == {
        "status": "offset_issues", "document_count": 1, "chunk_count": 4,
        "unknown_document_lines": [1], "reversed_lines": [1, 2],
        "out_of_range_lines": [2, 3],
    }


def test_repeated_chunks_and_physical_delimiters(tmp_path: Path):
    process = execute(
        tmp_path,
        b'{"id":"a","text":"x"}\r\n{"id":"b","text":"y"}\r',
        b'{"document":"a","start":0,"end":1}\r{"document":"a","start":0,"end":1}\n',
    )
    assert process.returncode == 0
    assert result(process)["chunk_count"] == 2


def test_unicode_line_separator_is_not_a_delimiter(tmp_path: Path):
    process = execute(
        tmp_path,
        '{"id":"a","text":"x"}\u2028{"id":"b","text":"y"}\n'.encode(),
        b"",
    )
    assert process.returncode == 2
    assert result(process) == {"status": "invalid_input"}


@pytest.mark.parametrize("bad", [
    b'{"id":"d","id":"x","text":"t"}\n',
    b'{"id":"d","text":"t","extra":1}\n',
    b'{"id":"d","text":1}\n',
    b'{"id":"","text":"t"}\n',
    b'{"id":"d","text":"t"}\n{"id":"d","text":"u"}\n',
    b'{"id":"d","text":"\\ud800"}\n',
    b'{"id":"d","text":"t"}\n\n',
    b'{"id":"d","text":"t"}\nNaN\n',
    b'{"id":"d","text":"t"}\n\xff',
])
def test_invalid_document_jsonl_is_generic_and_private(tmp_path: Path, bad: bytes):
    secret_path = tmp_path / "secret-doc-name.jsonl"
    write(secret_path, bad)
    chunks = write(tmp_path / "secret-chunks-name.jsonl", b"")
    process = run_cli(str(secret_path), str(chunks))
    assert process.returncode == 2
    assert process.stdout == '{"status":"invalid_input"}\n'
    assert process.stderr == ""
    assert "secret" not in process.stdout + process.stderr


@pytest.mark.parametrize("bad", [
    b'{"document":"d","start":0,"end":1,"extra":0}\n',
    b'{"document":"d","start":true,"end":1}\n',
    b'{"document":"d","start":-1,"end":1}\n',
    b'{"document":"d","start":0,"end":1000000001}\n',
    b'{"document":"","start":0,"end":0}\n',
    b'{"document":"d","start":0.0,"end":1}\n',
    b'{"document":"d","start":0,"end":NaN}\n',
    b'{"document":"d","start":0,"start":1,"end":1}\n',
    b'{"document":"\\ud800","start":0,"end":1}\n',
])
def test_invalid_chunk_schema(tmp_path: Path, bad: bytes):
    process = execute(tmp_path, b'{"id":"d","text":"x"}\n', bad)
    assert process.returncode == 2
    assert process.stdout == '{"status":"invalid_input"}\n'
    assert process.stderr == ""


def test_both_files_are_observed_even_if_first_is_invalid(tmp_path: Path, monkeypatch):
    from chunk_offset_check import core

    documents = write(tmp_path / "docs.jsonl", b"not json\n")
    chunks = write(tmp_path / "chunks.jsonl", b'{"document":"d","start":0,"end":0}\n')
    observed = []
    original = core._read_records

    def observed_read(path):
        observed.append(path)
        return original(path)

    monkeypatch.setattr(core, "_read_records", observed_read)
    with pytest.raises(core.InputError):
        core.inspect_files(str(documents), str(chunks))
    assert observed == [str(documents), str(chunks)]


def test_no_partial_output_and_private_argv_for_valid_files(tmp_path: Path):
    documents = write(tmp_path / "private-doc-name.jsonl", b'{"id":"PRIVATE_ID","text":"PRIVATE_TEXT"}\n')
    chunks = write(tmp_path / "private-chunk-name.jsonl", b'{"document":"PRIVATE_ID","start":4,"end":99}\n')
    process = run_cli(str(documents), str(chunks))
    assert process.returncode == 1
    assert process.stdout == (
        '{"status":"offset_issues","document_count":1,"chunk_count":1,'
        '"unknown_document_lines":[],"reversed_lines":[],"out_of_range_lines":[1]}\n'
    )
    assert process.stderr == ""
    for private in (str(documents), str(chunks), "PRIVATE_ID", "PRIVATE_TEXT", "4", "9"):
        assert private not in process.stdout + process.stderr


def test_missing_extra_unknown_arguments_are_generic(tmp_path: Path):
    for arguments in ((), ("one",), ("one", "two", "three"), ("--wat", "x")):
        process = run_cli(*arguments, cwd=tmp_path)
        assert process.returncode == 2
        assert process.stdout == '{"status":"invalid_input"}\n'
        assert process.stderr == ""


def test_help_succeeds_without_paths():
    for flag in ("-h", "--help"):
        process = run_cli(flag)
        assert process.returncode == 0
        assert "usage: chunk-offset-check" in process.stdout
        assert process.stderr == ""

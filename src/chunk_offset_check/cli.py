"""Command-line entry point with privacy-preserving failure output."""

from __future__ import annotations

import json
import sys

from .core import InputError, inspect_files

_HELP = """usage: chunk-offset-check DOCUMENTS.jsonl CHUNKS.jsonl

Check normalized chunk offsets against declared document text. Offsets are
zero-based Python Unicode codepoint indices with an exclusive end. The tool
reads local JSONL files only and never prints document content.
"""


def main() -> int:
    arguments = sys.argv[1:]
    if len(arguments) == 1 and arguments[0] in ("-h", "--help"):
        sys.stdout.write(_HELP)
        return 0
    if len(arguments) != 2 or any(argument in ("-h", "--help") for argument in arguments):
        return _invalid()
    try:
        result = inspect_files(arguments[0], arguments[1])
    except InputError:
        return _invalid()
    sys.stdout.write(json.dumps(result, ensure_ascii=True, separators=(",", ":")) + "\n")
    return 1 if result["status"] == "offset_issues" else 0


def _invalid() -> int:
    sys.stdout.write('{"status":"invalid_input"}\n')
    return 2

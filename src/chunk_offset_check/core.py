"""Strict JSONL parsing and offset checks for the frozen fixture contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class InputError(Exception):
    """An input could not be read or does not follow the data contract."""


def _reject_constant(value: str) -> None:
    raise ValueError("non-standard JSON constant")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate object key")
        result[key] = value
    return result


def _physical_lines(data: bytes):
    """Yield (1-based line number, bytes), recognizing only CR and LF."""
    start = 0
    number = 1
    index = 0
    while index < len(data):
        if data[index] in (10, 13):
            yield number, data[start:index]
            if data[index] == 13 and index + 1 < len(data) and data[index + 1] == 10:
                index += 1
            start = index + 1
            number += 1
        index += 1
    if start < len(data):
        yield number, data[start:]


def _strings_have_no_surrogates(value: Any) -> bool:
    if isinstance(value, str):
        return not any(0xD800 <= ord(character) <= 0xDFFF for character in value)
    if isinstance(value, list):
        return all(_strings_have_no_surrogates(item) for item in value)
    if isinstance(value, dict):
        return all(
            _strings_have_no_surrogates(key) and _strings_have_no_surrogates(item)
            for key, item in value.items()
        )
    return True


def _read_records(path: str) -> list[tuple[int, dict[str, Any]]]:
    try:
        data = Path(path).read_bytes()
    except (OSError, ValueError, UnicodeError):
        raise InputError from None

    records: list[tuple[int, dict[str, Any]]] = []
    try:
        for line_number, raw_line in _physical_lines(data):
            if not raw_line:
                raise InputError
            text = raw_line.decode("utf-8", errors="strict")
            record = json.loads(
                text,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
            if not isinstance(record, dict) or not _strings_have_no_surrogates(record):
                raise InputError
            records.append((line_number, record))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, InputError, RecursionError):
        raise InputError from None
    return records


def _has_exact_keys(record: dict[str, Any], keys: set[str]) -> bool:
    return set(record) == keys


def inspect_files(documents_path: str, chunks_path: str) -> dict[str, Any]:
    """Parse both files and return contract-defined counts and line findings."""
    documents_raw: list[tuple[int, dict[str, Any]]] | None = None
    chunks_raw: list[tuple[int, dict[str, Any]]] | None = None
    documents_error = chunks_error = False
    try:
        documents_raw = _read_records(documents_path)
    except InputError:
        documents_error = True
    try:
        chunks_raw = _read_records(chunks_path)
    except InputError:
        chunks_error = True
    if documents_error or chunks_error:
        raise InputError

    assert documents_raw is not None and chunks_raw is not None
    documents: dict[str, str] = {}
    for _, record in documents_raw:
        if not _has_exact_keys(record, {"id", "text"}):
            raise InputError
        identifier, text = record["id"], record["text"]
        if not isinstance(identifier, str) or not identifier or not isinstance(text, str):
            raise InputError
        if identifier in documents:
            raise InputError
        documents[identifier] = text

    unknown: list[int] = []
    reversed_offsets: list[int] = []
    out_of_range: list[int] = []
    for line_number, record in chunks_raw:
        if not _has_exact_keys(record, {"document", "start", "end"}):
            raise InputError
        identifier, start, end = record["document"], record["start"], record["end"]
        if not isinstance(identifier, str) or not identifier:
            raise InputError
        if type(start) is not int or type(end) is not int:
            raise InputError
        if not 0 <= start <= 1_000_000_000 or not 0 <= end <= 1_000_000_000:
            raise InputError
        if identifier not in documents:
            unknown.append(line_number)
        elif start > len(documents[identifier]) or end > len(documents[identifier]):
            out_of_range.append(line_number)
        if end < start:
            reversed_offsets.append(line_number)

    findings = bool(unknown or reversed_offsets or out_of_range)
    return {
        "status": "offset_issues" if findings else "valid",
        "document_count": len(documents),
        "chunk_count": len(chunks_raw),
        "unknown_document_lines": unknown,
        "reversed_lines": reversed_offsets,
        "out_of_range_lines": out_of_range,
    }

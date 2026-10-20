# Chunk Offset Check

`chunk-offset-check` is an offline Python 3.10+ command-line tool that checks
normalized chunk offsets against document text supplied in JSONL. It uses only
the Python standard library at runtime; installation requires no runtime
dependencies.

Offsets are zero-based Python Unicode codepoint indices into the decoded
`text` value. The `end` offset is exclusive. JSON escape sequences are decoded
before text length is measured, so an escaped newline counts as one codepoint.
Unicode text is used exactly as supplied; no normalization, tokenization,
chunking, overlap, coverage, extraction, or retrieval-quality checks occur.

## Input format

The first file contains one document per physical line:

```json
{"id":"guide","text":"Read the 🧭 first.\nThen continue."}
```

The second file contains chunk offsets:

```json
{"document":"guide","start":0,"end":15}
```

Each document object must contain exactly a nonempty string `id` and string
`text` (which may be empty). IDs must be unique. Each chunk object must contain
exactly a nonempty string `document` plus integer `start` and `end` values from
0 through 1,000,000,000. Repeated chunks are allowed. Booleans are not integers
for this format. The files must be strict UTF-8 JSONL with no duplicate JSON
object keys, nonstandard constants, blank records, or surrogate codepoints in
strings. CR, LF, and CRLF separate physical records. A final line terminator
is allowed; Unicode line-separator characters are not record delimiters.

Unknown document IDs, reversed ranges, and ranges beyond a known document's
text length are reported as independent line-number findings. An unknown ID is
valid input and is not checked for range. Endpoints equal to the text length,
including `0..0` for empty text, are allowed. The tool does not print input
content, IDs, offset values, paths, or exception details.

## Use

From a source checkout:

```console
python -m pip install .
chunk-offset-check examples/documents.jsonl examples/chunks.jsonl
```

For development, install pytest and run `python -m pytest`. The sample data is
synthetic; its unknown-document line intentionally demonstrates an issue
report.

Successful checks exit `0`; well-formed inputs with offset findings exit `1`;
invalid files or arguments exit `2`. Results are one JSON object on stdout.
Invalid input produces only `{"status":"invalid_input"}` and a newline.

This validates only the stated offset fixture contract. It does not evaluate
retrieval behavior, semantic quality, security, or novelty.

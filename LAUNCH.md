# Launch checklist

1. Use Python 3.10 or later. Install the project with `python -m pip install .`.
2. Prepare two strict UTF-8 JSONL files using the schemas documented in
   [README.md](README.md). Keep each document text and chunk record synthetic
   or otherwise appropriate for local processing.
3. Run `chunk-offset-check DOCUMENTS.jsonl CHUNKS.jsonl`.
4. Interpret exit `0` as no offset findings, `1` as one or more offset findings,
   and `2` as invalid input or command arguments. The JSON output includes
   counts and physical line numbers only.

For a local source checkout, use `python -m chunk_offset_check` instead of the
installed command. `python -m chunk_offset_check --help` prints usage.

The command reads both files fully into memory. It performs no network access,
text extraction, chunking, token counting, overlap checking, or retrieval
evaluation. It never displays IDs, document text, paths, or supplied offsets.

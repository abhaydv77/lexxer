# Tools

Dataset tools for the Data Analyst Agent — functions callable via LLM tool-use.

## Structure

- **`dataset.py`** — Tabular data inspection and query tools.

## Available Tools

All tools are defined in `dataset.py` and exposed via the `TOOLS` list (Anthropic-style schemas) and `FUNCTIONS` dict mapping names to callables.

### `load_dataset(path)`

**Load a CSV file into memory.** Returns column names, dtypes, row count, and a 5-row preview.

```python
result = load_dataset("data/cities.csv")
# → {"success": True, "data": {columns, row_count, preview}, "meta": {...}}
```

Parameters:
- `path` (str): Filesystem path to the CSV file.

### `describe_dataset()`

**Return statistics and null counts** for the loaded dataset. Uses `df.describe(include="all")` plus per-column null counts.

```python
result = describe_dataset()
# → {"success": True, "data": {describe, null_counts}, "meta": {...}}
```

Requires: A dataset must be loaded first via `load_dataset()`.

### `run_query(query)`

**Execute a SQL query** via DuckDB against the loaded DataFrame (registered as table `df`). Returns up to 20 rows.

```python
result = run_query("SELECT City, Population FROM df ORDER BY Population DESC LIMIT 5")
# → {"success": True, "data": {rows, row_count, truncated}, "meta": {...}}
```

Parameters:
- `query` (str): SQL query string. Must reference `df` as the table name.

Requires: A dataset must be loaded first.

## Response Format

All tools return a consistent envelope:

```python
{
    "success": bool,         # True on success, False on error
    "data": {...} | None,   # Tool-specific results
    "error": str | None,    # Error message if failed
    "meta": {               # Execution metadata
        "duration_ms": float,
        "rows_affected": int (for run_query)
    }
}
```

## Design Notes

- Tools use module-level `_df` state (single active dataset per session)
- No classes — pure functions designed for LLM tool-use
- Errors are caught and returned as structured data (never raised)
- DuckDB connection is ephemeral (`:memory:`) per query

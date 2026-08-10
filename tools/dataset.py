import logging
import time
from typing import Any

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)

_df: pd.DataFrame | None = None


def load_dataset(path: str) -> dict[str, Any]:
    """Load a CSV file into a module-level pandas DataFrame and return metadata."""
    start = time.perf_counter()
    try:
        global _df
        _df = pd.read_csv(path)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("load_dataset | path=%s | duration_ms=%.2f | success=True", path, elapsed_ms)
        return {
            "success": True,
            "data": {
                "columns": [
                    {"name": col, "dtype": str(dtype)}
                    for col, dtype in _df.dtypes.items()
                ],
                "row_count": len(_df),
                "preview": _df.head(5).to_dict(orient="records"),
            },
            "meta": {"duration_ms": round(elapsed_ms, 2)},
        }
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("load_dataset | path=%s | duration_ms=%.2f | success=False | error=%s", path, elapsed_ms, exc)
        return {
            "success": False,
            "error": str(exc),
            "meta": {"duration_ms": round(elapsed_ms, 2)},
        }


def describe_dataset() -> dict[str, Any]:
    """Return df.describe() output plus per-column null counts."""
    start = time.perf_counter()
    try:
        if _df is None:
            raise RuntimeError("No dataset loaded. Call load_dataset first.")
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("describe_dataset | duration_ms=%.2f | success=True", elapsed_ms)
        return {
            "success": True,
            "data": {
                "describe": _df.describe(include="all").to_dict(),
                "null_counts": {col: int(_df[col].isna().sum()) for col in _df.columns},
            },
            "meta": {"duration_ms": round(elapsed_ms, 2)},
        }
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("describe_dataset | duration_ms=%.2f | success=False | error=%s", elapsed_ms, exc)
        return {
            "success": False,
            "error": str(exc),
            "meta": {"duration_ms": round(elapsed_ms, 2)},
        }


def run_query(query: str) -> dict[str, Any]:
    """Run a SQL query via DuckDB against the loaded DataFrame and return up to 20 rows."""
    start = time.perf_counter()
    try:
        if _df is None:
            raise RuntimeError("No dataset loaded. Call load_dataset first.")
        con = duckdb.connect(database=":memory:")
        con.register("df", _df)
        result = con.execute(query).fetch_df()
        total_rows = len(result)
        rows = result.head(20).to_dict(orient="records")
        truncated = total_rows > 20
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("run_query | query=%s | duration_ms=%.2f | success=True | rows=%d", query, elapsed_ms, total_rows)
        return {
            "success": True,
            "data": {
                "query": query,
                "rows": rows,
                "row_count": total_rows,
                "truncated": truncated,
            },
            "meta": {"duration_ms": round(elapsed_ms, 2), "rows_affected": total_rows},
        }
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("run_query | query=%s | duration_ms=%.2f | success=False | error=%s", query, elapsed_ms, exc)
        return {
            "success": False,
            "error": str(exc),
            "meta": {"duration_ms": round(elapsed_ms, 2), "rows_affected": 0},
        }


TOOLS = [
    {
        "name": "load_dataset",
        "description": "Load a CSV file into memory and return column names, dtypes, row count, and a 5-row preview.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Filesystem path to the CSV file."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "describe_dataset",
        "description": "Return df.describe() statistics plus null counts for every column in the loaded dataset.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "run_query",
        "description": "Run a SQL query against the loaded dataset via DuckDB and return up to 20 rows.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SQL query string to execute against the dataframe."},
            },
            "required": ["query"],
        },
    },
]

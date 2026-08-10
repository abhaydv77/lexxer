import json
import logging
import os
import time
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)

_PLOT_DIR = Path("/tmp/plots")
_MAX_PREVIEW_ROWS = 5
_MAX_QUERY_ROWS = 50


class DatasetToolkit:
    """Registry-backed toolkit for an AI data-analyst agent to inspect and query tabular datasets."""

    def __init__(self, dataset_registry: dict[str, pd.DataFrame] | None = None):
        self.datasets: dict[str, pd.DataFrame] = dataset_registry or {}

    # ─── internal helpers ────────────────────────────────────────────────

    def _get_dataset(self, name: str) -> pd.DataFrame:
        if name not in self.datasets:
            raise KeyError(f"Dataset '{name}' is not loaded.")
        return self.datasets[name]

    @staticmethod
    def _envelope(
        success: bool,
        data: Any = None,
        error: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "success": success,
            "data": data,
            "error": error,
            "meta": meta or {},
        }

    def _log_call(self, tool_name: str, args: dict[str, Any], duration_ms: float, success: bool, error: str | None = None):
        logger.info(
            "tool_call | tool=%s | args=%s | duration_ms=%.2f | success=%s | error=%s",
            tool_name, json.dumps(args, default=str), duration_ms, success, error,
        )

    # ─── public tools ────────────────────────────────────────────────────

    def load_dataset(self, path: str, name: str | None = None) -> dict[str, Any]:
        """
        Load a tabular dataset from disk (CSV, Excel, Parquet, or JSON) into the in-memory registry.

        The dataset is keyed by `name` (default: the filename stem without extension), so it
        can be referenced by subsequent calls to describe_dataset, run_query, etc. Only metadata
        and a preview (first 5 rows) are returned — never the full dataframe.

        Parameters
        ----------
        path : str
            Filesystem path to the dataset. Supports .csv, .xlsx, .parquet, .json extensions.
        name : str, optional
            Registry key under which to store the dataframe. Defaults to the filename stem.

        Returns
        -------
        dict
            Envelope: {"success", "data": {name, row_count, columns, dtypes, memory_bytes, preview},
            "error", "meta": {duration_ms}}
        """
        start = time.perf_counter()
        args = {"path": path, "name": name}
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                raise FileNotFoundError(f"File not found: {path}")

            ext = path_obj.suffix.lower()
            if ext == ".csv":
                df = pd.read_csv(path)
            elif ext == ".xlsx":
                df = pd.read_excel(path)
            elif ext == ".parquet":
                df = pd.read_parquet(path)
            elif ext == ".json":
                df = pd.read_json(path)
            else:
                raise ValueError(f"Unsupported file extension: {ext}. Supported: .csv, .xlsx, .parquet, .json")

            if df.empty:
                raise ValueError(f"Dataset is empty: {path}")

            dataset_name = name or path_obj.stem

            self.datasets[dataset_name] = df.reset_index(drop=True)

            columns = [
                {"name": col, "dtype": str(dtype)}
                for col, dtype in df.dtypes.items()
            ]
            preview_rows = df.head(_MAX_PREVIEW_ROWS).to_dict(orient="records")
            result = {
                "name": dataset_name,
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": columns,
                "memory_bytes": int(df.memory_usage(deep=True).sum()),
                "preview": preview_rows,
                "source_path": str(path_obj),
            }
            elapsed_ms = (time.perf_counter() - start) * 1000
            self._log_call("load_dataset", args, elapsed_ms, True)
            return self._envelope(success=True, data=result, meta={"duration_ms": elapsed_ms})

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            err_msg = str(exc)
            self._log_call("load_dataset", args, elapsed_ms, False, err_msg)
            return self._envelope(success=False, error=err_msg, meta={"duration_ms": elapsed_ms})

    def describe_dataset(self, name: str) -> dict[str, Any]:
        """
        Generate a comprehensive statistical profile of a loaded dataset.

        Includes schema-level information (dtype, null counts/percentages, unique counts)
        and per-column statistics: for numeric columns (min, max, mean, median, std),
        for categorical columns (top 5 values with counts). Columns are flagged for
        likely data-quality issues: high-cardinality, >50% null, or constant.

        Parameters
        ----------
        name : str
            Registry key of the dataset (as returned by load_dataset).

        Returns
        -------
        dict
            Envelope: {"success", "data": {schema: [...], stats: {...}, flags: [...]},
            "error", "meta": {duration_ms}}
        """
        start = time.perf_counter()
        args = {"name": name}
        try:
            df = self._get_dataset(name)
            n_rows = len(df)

            schema = []
            stats: dict[str, Any] = {}
            flags = []

            for col in df.columns:
                series = df[col]
                null_count = int(series.isna().sum())
                null_pct = round(null_count / n_rows * 100, 2) if n_rows else 0.0
                unique_count = int(series.nunique())

                col_info = {
                    "column": col,
                    "dtype": str(series.dtype),
                    "null_count": null_count,
                    "null_pct": null_pct,
                    "unique_count": unique_count,
                }
                schema.append(col_info)

                if null_pct > 50:
                    flags.append({"column": col, "issue": "high_null_pct", "value": null_pct})

                if unique_count > n_rows * 0.5 and n_rows > 1:
                    flags.append({"column": col, "issue": "high_cardinality", "value": unique_count})

                if unique_count <= 1:
                    flags.append({"column": col, "issue": "constant_column", "value": unique_count})

                if pd.api.types.is_numeric_dtype(series):
                    col_stats = {
                        "min": _safe_float(series.min()),
                        "max": _safe_float(series.max()),
                        "mean": _safe_float(series.mean()),
                        "median": _safe_float(series.median()),
                        "std": _safe_float(series.std()),
                    }
                else:
                    top = series.dropna().value_counts().head(5)
                    col_stats = [
                        {"value": str(val), "count": int(cnt)}
                        for val, cnt in top.items()
                    ]

                stats[col] = col_stats

            result = {"schema": schema, "stats": stats, "flags": flags, "row_count": n_rows}
            elapsed_ms = (time.perf_counter() - start) * 1000
            self._log_call("describe_dataset", args, elapsed_ms, True)
            return self._envelope(success=True, data=result, meta={"duration_ms": elapsed_ms})

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            err_msg = str(exc)
            self._log_call("describe_dataset", args, elapsed_ms, False, err_msg)
            return self._envelope(success=False, error=err_msg, meta={"duration_ms": elapsed_ms})

    def run_query(
        self,
        name: str,
        query: str,
        engine: str = "pandas",
    ) -> dict[str, Any]:
        """
        Execute a data query against a registered dataset and return up to 50 rows.

        For the 'pandas' engine, the query is a pandas DataFrame.eval()/query() expression
        (e.g. ``age > 30 & salary < 100000``). For the 'sql' engine, the query is a SQL
        statement executed via DuckDB, which can query the in-memory dataframe directly
        (e.g. ``SELECT * FROM df WHERE age > 30``).

        Parameters
        ----------
        name : str
            Registry key of the dataset.
        query : str
            Pandas expression or SQL statement, depending on `engine`.
        engine : str
            Either ``"pandas"`` or ``"sql"``. Defaults to ``"pandas"``.

        Returns
        -------
        dict
            Envelope: {"success", "data": {query, engine, rows, truncated, row_count},
            "error", "meta": {duration_ms, rows_affected}}
        """
        start = time.perf_counter()
        args = {"name": name, "query": query, "engine": engine}
        try:
            df = self._get_dataset(name)

            if engine not in ("pandas", "sql"):
                raise ValueError(f"engine must be 'pandas' or 'sql', got '{engine}'")

            if engine == "pandas":
                filtered = df.query(query)
            else:
                con = duckdb.sql("").set_connection(None)
                con.register(name, df)
                filtered = con.execute(query).fetch_df()

            total_rows = len(filtered)
            truncated = total_rows > _MAX_QUERY_ROWS
            result_rows = filtered.head(_MAX_QUERY_ROWS).to_dict(orient="records")

            result = {
                "query": query,
                "engine": engine,
                "dataset_name": name,
                "row_count": total_rows,
                "rows": result_rows,
                "truncated": truncated,
            }
            elapsed_ms = (time.perf_counter() - start) * 1000
            self._log_call("run_query", args, elapsed_ms, True)
            return self._envelope(
                success=True,
                data=result,
                meta={"duration_ms": elapsed_ms, "rows_affected": total_rows},
            )

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            err_msg = str(exc)
            self._log_call("run_query", args, elapsed_ms, False, err_msg)
            return self._envelope(success=False, error=err_msg, meta={"duration_ms": elapsed_ms, "rows_affected": 0})

    def plot_dataset(
        self,
        name: str,
        spec: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Render a chart from a dataset and save it as a PNG file.

        The spec dict must include a "kind" key (``bar``, ``line``, ``scatter``, or ``hist``)
        and column references (``x``, ``y``). An optional ``group_by`` column can be
        supplied for color/grouped charts. The plot is saved to ``/tmp/plots/{uuid}.png``
        and only the file path is returned in the result — never base64-encoded image data.

        Parameters
        ----------
        name : str
            Registry key of the dataset.
        spec : dict
            Plotting specification, e.g.::

                {"kind": "bar", "x": "category", "y": "sales", "group_by": "region"}

        Returns
        -------
        dict
            Envelope: {"success", "data": {file_path, kind, x, y, group_by, row_count},
            "error", "meta": {duration_ms, rows_affected}}
        """
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        start = time.perf_counter()
        args = {"name": name, "spec": spec}
        try:
            df = self._get_dataset(name)

            kind: str = spec.get("kind", "hist")
            x_col: str | None = spec.get("x")
            y_col: str | None = spec.get("y")
            group_by: str | None = spec.get("group_by")

            if kind not in ("bar", "line", "scatter", "hist"):
                raise ValueError(f"kind must be bar|line|scatter|hist, got '{kind}'")

            if kind == "hist" and x_col:
                plot_df = df[[x_col]].dropna()
            else:
                cols = [c for c in [x_col, y_col, group_by] if c is not None]
                missing = [c for c in cols if c not in df.columns]
                if missing:
                    raise KeyError(f"Columns not found in dataset: {missing}")
                plot_df = df[cols].dropna()

            _PLOT_DIR.mkdir(parents=True, exist_ok=True)
            file_path = _PLOT_DIR / f"{uuid.uuid4()}.png"

            fig, ax = plt.subplots(figsize=(10, 6))

            if kind == "hist":
                ax.hist(plot_df[x_col].dropna(), bins=30, edgecolor="black")
                ax.set_xlabel(x_col or "value")
                ax.set_ylabel("Frequency")
                ax.set_title(f"Histogram of {x_col}")

            elif kind == "scatter":
                if group_by:
                    for grp, sub in plot_df.groupby(group_by):
                        ax.scatter(sub[x_col], sub[y_col], label=str(grp), alpha=0.6, s=30)
                    ax.legend(title=group_by)
                else:
                    ax.scatter(plot_df[x_col], plot_df[y_col], alpha=0.6, s=30)
                ax.set_xlabel(x_col)
                ax.set_ylabel(y_col)
                ax.set_title(f"Scatter: {x_col} vs {y_col}")

            elif kind == "bar":
                if group_by:
                    grouped = plot_df.groupby([x_col, group_by])[y_col].agg("count").unstack(fill_value=0)
                    grouped.plot(kind="bar", ax=ax, edgecolor="black")
                else:
                    grouped = plot_df.groupby(x_col)[y_col].agg("count")
                    ax.bar(grouped.index.astype(str), grouped.values, edgecolor="black")
                ax.set_xlabel(x_col)
                ax.set_ylabel("Count" if not y_col else f"{y_col} (count)")
                ax.tick_params(axis="x", rotation=45)

            elif kind == "line":
                if group_by:
                    grouped = plot_df.groupby([x_col, group_by])[y_col].mean().unstack()
                    grouped.plot(kind="line", ax=ax, marker="o")
                    ax.legend(title=group_by)
                else:
                    grouped = plot_df.groupby(x_col)[y_col].mean().sort_index()
                    ax.plot(grouped.index, grouped.values, marker="o")
                ax.set_xlabel(x_col)
                ax.set_ylabel(y_col)
                ax.tick_params(axis="x", rotation=45)

            plt.tight_layout()
            fig.savefig(file_path, dpi=150, format="png")
            plt.close(fig)

            result = {
                "file_path": str(file_path),
                "kind": kind,
                "x": x_col,
                "y": y_col,
                "group_by": group_by,
                "row_count": len(plot_df),
            }
            elapsed_ms = (time.perf_counter() - start) * 1000
            self._log_call("plot_dataset", args, elapsed_ms, True)
            return self._envelope(
                success=True,
                data=result,
                meta={"duration_ms": elapsed_ms, "rows_affected": len(plot_df)},
            )

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            err_msg = str(exc)
            try:
                plt.close("all")
            except Exception:
                pass
            self._log_call("plot_dataset", args, elapsed_ms, False, err_msg)
            return self._envelope(success=False, error=err_msg, meta={"duration_ms": elapsed_ms, "rows_affected": 0})


def _safe_float(val: Any) -> float | None:
    """Convert a value to float, returning None for NaN/None."""
    if val is None:
        return None
    f = float(val)
    return None if pd.isna(f) else f


# ─── Anthropic tool schemas ──────────────────────────────────────────────

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "load_dataset",
        "description": DatasetToolkit.load_dataset.__doc__.strip().split("\n\n")[0] if DatasetToolkit.load_dataset.__doc__ else "Load a dataset",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Filesystem path to the dataset. Supports .csv, .xlsx, .parquet, .json extensions."},
                "name": {"type": "string", "description": "Optional registry key for the dataset. Defaults to the filename stem without extension."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "describe_dataset",
        "description": "Generate a comprehensive statistical profile of a loaded dataset, including schema-level info, per-column statistics, and data-quality flags.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Registry key of the dataset (as returned by load_dataset)."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "run_query",
        "description": "Execute a data query against a registered dataset. The query is a pandas expression (engine='pandas') or a SQL statement (engine='sql'). Returns up to 50 rows with truncation info.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Registry key of the dataset."},
                "query": {"type": "string", "description": "Pandas expression (e.g. 'age > 30') or SQL statement (e.g. 'SELECT * FROM df WHERE age > 30'), depending on the engine."},
                "engine": {"type": "string", "enum": ["pandas", "sql"], "description": "Query engine. 'pandas' treats query as a DataFrame.query() expression. 'sql' executes via DuckDB.", "default": "pandas"},
            },
            "required": ["name", "query", "engine"],
        },
    },
    {
        "name": "plot_dataset",
        "description": "Render a chart (bar, line, scatter, or histogram) from a dataset and save it as a PNG file. Returns the file path, not image data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Registry key of the dataset."},
                "spec": {
                    "type": "object",
                    "description": "Plotting specification with keys: kind (bar|line|scatter|hist), x, y (optional), group_by (optional).",
                    "properties": {
                        "kind": {"type": "string", "enum": ["bar", "line", "scatter", "hist"]},
                        "x": {"type": "string"},
                        "y": {"type": "string"},
                        "group_by": {"type": "string"},
                    },
                    "required": ["kind", "x"],
                },
            },
            "required": ["name", "spec"],
        },
    },
]

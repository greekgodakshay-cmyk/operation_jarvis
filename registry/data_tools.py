"""
Tabular Data Profiling and Statistical Analysis for Operation JARVIS.
Performs automated profiling, summary statistics, and ASCII visualization for CSV and JSON datasets.
"""
import csv
import io
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from security.path_jail import path_jail, PathJailViolation

def _render_ascii_histogram(values: List[float], bins: int = 5) -> str:
    """Renders a simple ASCII histogram for a numeric list."""
    if not values:
        return "No data"
    min_v, max_v = min(values), max(values)
    if min_v == max_v:
        return f"[{min_v:.2f}]: " + "#" * min(len(values), 30)

    bin_width = (max_v - min_v) / bins
    counts = [0] * bins
    for v in values:
        idx = int((v - min_v) / bin_width)
        if idx >= bins:
            idx = bins - 1
        counts[idx] += 1

    max_c = max(counts) or 1
    lines = []
    for i in range(bins):
        low = min_v + i * bin_width
        high = low + bin_width
        bar = "#" * int((counts[i] / max_c) * 20)
        lines.append(f"[{low:6.1f} - {high:6.1f}]: {bar:<20} ({counts[i]})")
    return "\n".join(lines)

def tool_data_profile_tabular(
    path: Optional[str] = None,
    raw_data: Optional[str] = None,
    generate_chart: bool = False
) -> Dict[str, Any]:
    """
    Profiles tabular data from a CSV/JSON file or raw text string.
    Computes column types, row counts, missing values, numerical statistics, and distribution charts.
    """
    data_str = ""
    source_name = "inline data"

    if path:
        try:
            safe_path = path_jail.validate_path(path)
            if not safe_path.exists():
                return {"ok": False, "error": f"File '{path}' does not exist."}
            data_str = safe_path.read_text(encoding="utf-8", errors="ignore")
            source_name = safe_path.name
        except PathJailViolation as pe:
            return {"ok": False, "error": str(pe)}
        except Exception as e:
            return {"ok": False, "error": f"Failed to read data file: {str(e)}"}
    elif raw_data is not None:
        data_str = raw_data
    else:
        return {"ok": False, "error": "Either 'path' or 'raw_data' must be provided."}

    # Parse rows as CSV or JSON
    rows: List[Dict[str, Any]] = []
    data_stripped = data_str.strip()

    if data_stripped.startswith(("[", "{")):
        try:
            parsed_json = json.loads(data_stripped)
            if isinstance(parsed_json, list):
                rows = [r for r in parsed_json if isinstance(r, dict)]
            elif isinstance(parsed_json, dict):
                # Try table format {columns: [], data: []}
                if "data" in parsed_json and isinstance(parsed_json["data"], list):
                    rows = parsed_json["data"]
                else:
                    rows = [parsed_json]
        except Exception:
            pass

    if not rows:
        # Parse CSV
        try:
            reader = csv.DictReader(io.StringIO(data_str.strip()))
            rows = [dict(r) for r in reader if any(v and str(v).strip() for v in r.values())]
        except Exception as e:
            return {"ok": False, "error": f"Failed to parse tabular data: {str(e)}"}

    if not rows:
        return {"ok": False, "error": "Dataset contains 0 tabular rows."}

    total_rows = len(rows)
    all_columns = [col for col in rows[0].keys() if col is not None]

    # Profile each column
    column_profiles = {}
    charts = {}

    for col in all_columns:
        vals = [r.get(col) for r in rows]
        null_count = sum(1 for v in vals if v is None or str(v).strip() in ("", "NA", "null", "None", "NaN"))
        non_nulls = [v for v in vals if v is not None and str(v).strip() not in ("", "NA", "null", "None", "NaN")]

        # Determine type
        numeric_vals: List[float] = []
        is_numeric = False
        if non_nulls:
            try:
                numeric_vals = [float(v) for v in non_nulls]
                is_numeric = True
            except (ValueError, TypeError):
                is_numeric = False

        profile: Dict[str, Any] = {
            "null_count": null_count,
            "null_pct": round((null_count / total_rows) * 100.0, 1),
            "total_count": total_rows,
            "unique_count": len(set(str(v) for v in non_nulls))
        }

        if is_numeric and numeric_vals:
            profile["inferred_type"] = "integer" if all(float(v).is_integer() for v in numeric_vals) else "float"
            n = len(numeric_vals)
            sorted_v = sorted(numeric_vals)
            mean_v = sum(numeric_vals) / n
            variance = sum((x - mean_v) ** 2 for x in numeric_vals) / n
            std_v = math.sqrt(variance)
            median_v = sorted_v[n // 2] if n % 2 != 0 else (sorted_v[n // 2 - 1] + sorted_v[n // 2]) / 2.0

            profile["min"] = round(min(numeric_vals), 4)
            profile["max"] = round(max(numeric_vals), 4)
            profile["mean"] = round(mean_v, 4)
            profile["median"] = round(median_v, 4)
            profile["std_dev"] = round(std_v, 4)

            if generate_chart:
                charts[col] = _render_ascii_histogram(numeric_vals)
        else:
            profile["inferred_type"] = "string"
            # Frequency counts for top 3 values
            freq: Dict[str, int] = {}
            for v in non_nulls:
                s = str(v)
                freq[s] = freq.get(s, 0) + 1
            top_vals = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:3]
            profile["top_categories"] = [{"value": k, "count": v} for k, v in top_vals]

        column_profiles[col] = profile

    res: Dict[str, Any] = {
        "ok": True,
        "source": source_name,
        "total_rows": total_rows,
        "column_count": len(all_columns),
        "columns": all_columns,
        "profiles": column_profiles
    }
    if generate_chart and charts:
        res["distribution_charts"] = charts

    return res

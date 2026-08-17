import sys
import pandas as pd
import numpy as np


def load_data(path: str) -> pd.DataFrame:
    """Load CSV robustly, tolerating malformed rows/encoding issues."""
    df = pd.read_csv(
        path,
        engine="python",       # more forgiving parser for messy CSVs
        on_bad_lines="skip",   # skip rows with wrong column counts
        skipinitialspace=True,
        encoding="utf-8-sig",  # handles BOM / Excel exports
    )
    # Normalize column names (strip whitespace, consistent casing)
    df.columns = [c.strip() for c in df.columns]
    return df


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Type-cast and fill missing values based on column dtype."""
    df = df.copy()

    # --- Identify expected columns (adjust names to match your file) ---
    numeric_cols = [c for c in ["Revenue", "OrderValue", "Quantity", "Price"] if c in df.columns]
    categorical_cols = [c for c in ["Region", "Product", "Customer", "SalesRep"] if c in df.columns]
    date_cols = [c for c in ["OrderDate", "Date"] if c in df.columns]

    # Strip whitespace from string columns (vectorized, no loops)
    obj_cols = df.select_dtypes(include="object").columns
    df[obj_cols] = df[obj_cols].apply(lambda s: s.str.strip())

    # Numeric columns: coerce bad values to NaN, then fill sensibly
    for col in numeric_cols:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(r"[^\d.\-]", "", regex=True),
            errors="coerce",
        )
    if numeric_cols:
        # Fill numeric NaNs with the column median (robust to outliers)
        df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())

    # Categorical columns: fill missing with "Unknown"
    if categorical_cols:
        df[categorical_cols] = df[categorical_cols].fillna("Unknown")

    # Date columns: parse, drop rows where a required date is unparseable
    for col in date_cols:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    # Drop fully empty rows / exact duplicates (vectorized)
    df = df.dropna(how="all")
    df = df.drop_duplicates()

    return df


def aggregate_by_region(df: pd.DataFrame) -> pd.DataFrame:
    """Group by Region: total revenue + average order value (vectorized)."""
    if "Region" not in df.columns:
        raise KeyError("Expected a 'Region' column in the dataset.")

    revenue_col = "Revenue" if "Revenue" in df.columns else None
    order_val_col = "OrderValue" if "OrderValue" in df.columns else revenue_col

    if revenue_col is None:
        raise KeyError("Expected a 'Revenue' (or similar) numeric column.")

    agg_df = (
        df.groupby("Region", as_index=False)
        .agg(
            Total_Revenue=(revenue_col, "sum"),
            Average_Order_Value=(order_val_col, "mean"),
            Order_Count=(revenue_col, "count"),
        )
        .round(2)
        .sort_values("Total_Revenue", ascending=False)
        .reset_index(drop=True)
    )
    return agg_df


def main():
    if len(sys.argv) != 3:
        print("Usage: python sales_pipeline.py <input_csv> <output_csv>")
        sys.exit(1)

    input_path, output_path = sys.argv[1], sys.argv[2]

    raw_df = load_data(input_path)
    clean_df = clean_data(raw_df)
    result_df = aggregate_by_region(clean_df)

    result_df.to_csv(output_path, index=False)
    print(f"Aggregated data written to {output_path}")
    print(result_df)


if __name__ == "__main__":
    main()
import pandas as pd
import numpy as np


def coerce_to_object_int(series: pd.Series) -> pd.Series:
    """Convert string series to object dtype with int and pd.NA values."""
    numeric = pd.to_numeric(series, errors="coerce")

    arr = np.empty(len(numeric), dtype=object)

    # create a mask of where integers will live
    mask = numeric.notna()

    # fill non-integers with NaNs
    arr[~mask] = pd.NA

    # Direct array assignment avoids pandas indexing overhead
    arr[mask] = numeric[mask].astype(int).to_numpy()

    return pd.Series(arr, index=series.index, dtype=object)

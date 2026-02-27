import numpy as np
import pandas as pd


def calculate_ratio(
    series_a: pd.Series,
    series_b: pd.Series,
    method: str = "divide",
) -> pd.Series:
    """Calculate ratio between two aligned series."""
    aligned_a, aligned_b = series_a.align(series_b, join="inner")
    # Avoid division by zero
    aligned_b = aligned_b.replace(0, np.nan)
    ratio = aligned_a / aligned_b
    return ratio.dropna()


def calculate_zscore(series: pd.Series, window: int = 52) -> pd.Series:
    """Rolling z-score with configurable lookback window."""
    rolling_mean = series.rolling(window=window, min_periods=max(1, window // 4)).mean()
    rolling_std = series.rolling(window=window, min_periods=max(1, window // 4)).std()
    rolling_std = rolling_std.replace(0, np.nan)
    zscore = (series - rolling_mean) / rolling_std
    return zscore.fillna(0)


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Standard RSI calculation."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def detect_extremes(
    zscore: pd.Series,
    upper_threshold: float = 2.0,
    lower_threshold: float = -2.0,
) -> dict:
    """Detect if current z-score is at extremes."""
    if zscore.empty:
        return {"signal": "neutral", "current_zscore": 0.0}

    current = float(zscore.iloc[-1])
    if current >= upper_threshold:
        signal = "overbought"
    elif current <= lower_threshold:
        signal = "oversold"
    else:
        signal = "neutral"

    return {"signal": signal, "current_zscore": round(current, 4)}


def _pct_change(series: pd.Series, periods: int) -> float | None:
    if len(series) < periods + 1:
        return None
    current = series.iloc[-1]
    past = series.iloc[-(periods + 1)]
    if past == 0:
        return None
    return round(((current - past) / past) * 100, 2)


def get_ratio_chart_data(
    series_a: pd.Series,
    series_b: pd.Series,
    dates: pd.Series | None = None,
) -> dict:
    """Build full chart payload for the frontend."""
    ratio = calculate_ratio(series_a, series_b)

    if ratio.empty:
        return {
            "ratio": [],
            "zscore": [],
            "rsi": [],
            "signal": "neutral",
            "current_value": 0,
            "current_zscore": 0,
            "pct_change_1w": None,
            "pct_change_1m": None,
            "pct_change_3m": None,
        }

    zscore = calculate_zscore(ratio)
    rsi = calculate_rsi(ratio)
    extremes = detect_extremes(zscore)

    # Build date index
    if dates is not None:
        date_index = dates.iloc[ratio.index].tolist()
    else:
        date_index = ratio.index.tolist()

    # Ensure dates are strings
    date_strs = [str(d)[:10] for d in date_index]

    ratio_points = [
        {"time": d, "value": round(float(v), 6)}
        for d, v in zip(date_strs, ratio.values)
        if not np.isnan(v)
    ]
    zscore_points = [
        {"time": d, "value": round(float(v), 4)}
        for d, v in zip(date_strs, zscore.values)
        if not np.isnan(v)
    ]
    rsi_points = [
        {"time": d, "value": round(float(v), 2)}
        for d, v in zip(date_strs, rsi.values)
        if not np.isnan(v)
    ]

    return {
        "ratio": ratio_points,
        "zscore": zscore_points,
        "rsi": rsi_points,
        "signal": extremes["signal"],
        "current_value": round(float(ratio.iloc[-1]), 6),
        "current_zscore": extremes["current_zscore"],
        "pct_change_1w": _pct_change(ratio, 5),
        "pct_change_1m": _pct_change(ratio, 22),
        "pct_change_3m": _pct_change(ratio, 66),
    }

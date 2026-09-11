"""Plotly figures for the Streamlit app.

Series colours come from a categorical palette validated for colour-vision
deficiencies in light and dark mode. Slots are assigned in a fixed order, never
cycled; comparison series (the closest single ETF, cash, "other") are drawn in grey.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from factorlens.attribution import FACTOR_NAMES, AttributionResult
from factorlens.metrics import TRADING_DAYS, drawdown

SERIES = {
    "light": [
        "#2a78d6",
        "#eb6834",
        "#1baf7a",
        "#eda100",
        "#e87ba4",
        "#008300",
        "#4a3aa7",
        "#e34948",
    ],
    "dark": [
        "#3987e5",
        "#d95926",
        "#199e70",
        "#c98500",
        "#d55181",
        "#008300",
        "#9085e9",
        "#e66767",
    ],
}
INK = {
    "light": {
        "text": "#0b0b0b",
        "secondary": "#52514e",
        "muted": "#898781",
        "grid": "#e1e0d9",
        "axis": "#c3c2b7",
        "surface": "#ffffff",
    },
    "dark": {
        "text": "#ffffff",
        "secondary": "#c3c2b7",
        "muted": "#898781",
        "grid": "#2c2c2a",
        "axis": "#383835",
        "surface": "#0e1117",
    },
}
NEUTRAL = "#898781"  # closest single ETF and cash
OTHER = "#c3c2b7"  # ETFs folded into "Other"
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'
MAX_SERIES = 7  # named ETFs in the weights chart; the rest is folded into "Other"


def _style(
    fig: go.Figure,
    mode: str,
    height: int,
    y_format: str | None = None,
    legend: bool = True,
    hovermode: str = "x unified",
) -> go.Figure:
    ink = INK[mode]
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=8, t=36 if legend else 8, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=12, color=ink["secondary"]),
        showlegend=legend,
        legend=dict(
            orientation="h", x=0, xanchor="left", y=1.02, yanchor="bottom", bgcolor="rgba(0,0,0,0)"
        ),
        hovermode=hovermode,
        hoverlabel=dict(font_family=FONT),
    )
    fig.update_xaxes(
        showgrid=False,
        showline=True,
        linecolor=ink["axis"],
        ticks="",
        tickfont_color=ink["muted"],
        zeroline=False,
        automargin=True,
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=ink["grid"],
        gridwidth=1,
        showline=False,
        ticks="",
        tickfont_color=ink["muted"],
        zeroline=False,
        tickformat=y_format,
        automargin=True,
    )
    return fig


def _horizontal_bars(fig: go.Figure, mode: str, n_bars: int, x_format: str) -> go.Figure:
    ink = INK[mode]
    fig.add_vline(x=0, line_color=ink["axis"], line_width=1)
    fig = _style(fig, mode, height=60 + 34 * n_bars, legend=False, hovermode="closest")
    fig.update_layout(bargap=0.45)
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont_color=ink["secondary"])
    fig.update_xaxes(showgrid=True, gridcolor=ink["grid"], showline=False, tickformat=x_format)
    return fig


def allocation(weights: pd.Series, names: dict[str, str], mode: str = "light") -> go.Figure:
    """The clone's current weights as horizontal bars, largest first."""
    fig = go.Figure(
        go.Bar(
            x=weights.to_numpy(),
            y=list(weights.index),
            orientation="h",
            marker=dict(color=SERIES[mode][0], cornerradius=4),
            customdata=[names.get(ticker, ticker) for ticker in weights.index],
            hovertemplate="%{y} · %{customdata}: %{x:.1%}<extra></extra>",
        )
    )
    return _horizontal_bars(fig, mode, len(weights), ".0%")


def loadings(result: AttributionResult, mode: str = "light") -> go.Figure:
    """Factor loadings with 95% confidence intervals from the HAC standard errors."""
    fig = go.Figure(
        go.Bar(
            x=result.betas,
            y=[FACTOR_NAMES.get(f, f) for f in result.betas.index],
            orientation="h",
            marker=dict(color=SERIES[mode][0], cornerradius=4),
            error_x=dict(
                type="data",
                array=1.96 * result.std_errors,
                color=INK[mode]["secondary"],
                thickness=1,
                width=4,
            ),
            customdata=result.t_stats,
            hovertemplate="%{y}: %{x:.2f} (t = %{customdata:.2f})<extra></extra>",
        )
    )
    return _horizontal_bars(fig, mode, len(result.betas), ".1f")


def contributions(result: AttributionResult, mode: str = "light") -> go.Figure:
    """Annualised contribution of each factor (loading x mean factor return) and alpha."""
    fig = go.Figure(
        go.Bar(
            x=result.contributions,
            y=[FACTOR_NAMES.get(f, f) for f in result.contributions.index],
            orientation="h",
            marker=dict(color=SERIES[mode][0], cornerradius=4),
            hovertemplate="%{y}: %{x:.2%} p.a.<extra></extra>",
        )
    )
    return _horizontal_bars(fig, mode, len(result.contributions), ".1%")


def rolling_loadings(betas: pd.DataFrame, mode: str = "light") -> go.Figure:
    """Rolling loadings as small multiples, one panel per factor, on a shared scale."""
    ink = INK[mode]
    n_cols = 4 if betas.shape[1] > 6 else 3
    n_rows = math.ceil(betas.shape[1] / n_cols)
    fig = make_subplots(
        rows=n_rows,
        cols=n_cols,
        shared_xaxes=True,
        shared_yaxes="all",
        subplot_titles=[FACTOR_NAMES.get(f, f) for f in betas.columns],
        horizontal_spacing=0.03,
        vertical_spacing=0.16,
    )
    for k, factor in enumerate(betas.columns):
        row, col = divmod(k, n_cols)
        fig.add_scatter(
            x=betas.index,
            y=betas[factor],
            mode="lines",
            name=FACTOR_NAMES.get(factor, factor),
            line=dict(color=SERIES[mode][0], width=2),
            showlegend=False,
            hovertemplate="%{y:.2f}",
            row=row + 1,
            col=col + 1,
        )
        fig.add_hline(y=0, line_color=ink["axis"], line_width=1, row=row + 1, col=col + 1)
    fig = _style(fig, mode, height=190 * n_rows + 30, y_format=".1f", legend=False, hovermode="x")
    fig.update_layout(margin=dict(t=28))
    fig.update_annotations(font=dict(size=12, color=ink["secondary"]))
    return fig


def growth(
    returns: pd.DataFrame, labels: dict[str, str], base_date: pd.Timestamp, mode: str = "light"
) -> go.Figure:
    """Growth of 100 from `base_date` for the fund, the clone and the closest single ETF."""
    colors = {"fund": SERIES[mode][0], "clone": SERIES[mode][1], "closest": NEUTRAL}
    fig = go.Figure()
    for key in ("fund", "clone", "closest"):
        if key not in returns:
            continue
        path = 100 * (1 + returns[key]).cumprod()
        path = pd.concat([pd.Series({pd.Timestamp(base_date): 100.0}), path])
        fig.add_scatter(
            x=path.index,
            y=path,
            mode="lines",
            name=labels[key],
            line=dict(color=colors[key], width=2),
            hovertemplate="%{y:.1f}",
        )
    return _style(fig, mode, height=380, y_format=",.0f")


def drawdowns(returns: pd.DataFrame, labels: dict[str, str], mode: str = "light") -> go.Figure:
    """Drawdown from the running peak for the fund and the clone."""
    colors = {"fund": SERIES[mode][0], "clone": SERIES[mode][1]}
    fig = go.Figure()
    for key in ("fund", "clone"):
        fig.add_scatter(
            x=returns.index,
            y=drawdown(returns[key]),
            mode="lines",
            name=labels[key],
            line=dict(color=colors[key], width=2),
            hovertemplate="%{y:.1%}",
        )
    return _style(fig, mode, height=300, y_format=".0%")


def rolling_tracking_error(
    returns: pd.DataFrame, periods_per_year: int = TRADING_DAYS, mode: str = "light"
) -> go.Figure:
    """Annualised tracking error of the clone over a trailing year of observations."""
    active = returns["fund"] - returns["clone"]
    te = (active.rolling(periods_per_year).std() * np.sqrt(periods_per_year)).dropna()
    fig = go.Figure(
        go.Scatter(
            x=te.index,
            y=te,
            mode="lines",
            name="Tracking error",
            line=dict(color=SERIES[mode][0], width=2),
            hovertemplate="%{y:.1%}",
        )
    )
    return _style(fig, mode, height=300, y_format=".0%", legend=False, hovermode="x")


def weights(target_weights: pd.DataFrame, mode: str = "light") -> go.Figure:
    """ETF weights at each trade date as stacked columns, with cash as the remainder.

    The seven ETFs with the largest average weight get their own colour; the rest are
    folded into "Other". Negative values (short positions, borrowed cash) stack below zero.
    """
    held = target_weights.loc[:, target_weights.abs().max() > 1e-4]
    order = held.abs().mean().sort_values(ascending=False).index
    named = list(order[:MAX_SERIES])
    columns = {ticker: held[ticker] for ticker in named}
    colors = SERIES[mode][: len(named)]
    if len(order) > MAX_SERIES:
        columns["Other"] = held[order[MAX_SERIES:]].sum(axis=1)
        colors = [*colors, OTHER]
    cash = 1.0 - target_weights.sum(axis=1)
    if cash.abs().max() > 1e-4:
        columns["Cash"] = cash
        colors = [*colors, NEUTRAL]
    # A separating line between segments helps with a few dozen columns, but at a few
    # pixels per column it washes the colours out.
    gap = 1 if len(target_weights) <= 60 else 0
    fig = go.Figure()
    for (name, values), color in zip(columns.items(), colors, strict=True):
        fig.add_bar(
            x=values.index,
            y=values,
            name=name,
            marker=dict(color=color, line=dict(color=INK[mode]["surface"], width=gap)),
            hovertemplate="%{y:.1%}",
        )
    fig.update_layout(barmode="relative", bargap=0.1 if gap else 0)
    return _style(fig, mode, height=360, y_format=".0%")

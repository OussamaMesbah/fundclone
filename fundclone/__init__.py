"""Clone any fund or portfolio with a handful of low-cost ETFs, out of sample."""

from fundclone.analysis import Analysis, run_analysis
from fundclone.attribution import AttributionResult, factor_regression, rolling_betas
from fundclone.portfolio import parse_portfolio
from fundclone.replication import (
    ReplicationConfig,
    ReplicationResult,
    estimate_weights,
    simulate_clone,
    walk_forward,
)

__version__ = "0.6.0"

__all__ = [
    "Analysis",
    "AttributionResult",
    "ReplicationConfig",
    "ReplicationResult",
    "estimate_weights",
    "factor_regression",
    "parse_portfolio",
    "rolling_betas",
    "run_analysis",
    "simulate_clone",
    "walk_forward",
]

"""EdgeFinder NFL player-prop pipeline.

Modules:
    download  -- fetch raw hvpkod + nfldata CSVs into pipeline/data/raw
    load      -- raw CSVs -> tidy player-week + games DataFrames
    features  -- leak-free feature matrices per market
    train     -- per-market gradient-boosted models + probability curves
    explain   -- local factor attribution -> plain-English factors
    backtest  -- 2025 walk-forward evaluation + calibration
    export    -- write the contract JSON to pipeline/data/export
    validate  -- check every contract invariant on an export dir
"""

__version__ = "1.0.0"

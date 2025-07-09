"""Signals calculation routines."""

from tracemalloc import start


if __name__ == "__main__":
    import pandas as pd
    from signaltk import constants as cst
    import numpy as np
    from signaltk.config.signals import SignalsConfig

    dt_idx = pd.date_range(
        start=SignalsConfig.START_DT, end=SignalsConfig.END_DT, freq="ME"
    )

    crsp = pd.read_pickle(f"{cst.WDIR}/data/crsp.pkl")
    ff = pd.read_pickle(f"{cst.WDIR}/data/ff.pkl")
    fund = pd.read_pickle(f"{cst.WDIR}/data/fundamentals.pkl")

    signals = {}

    # Book-to-market ratio
    me = (crsp["shrout"] * crsp["altprc"]).abs().replace(0, np.nan).astype(float)
    me = me.unstack()
    me = me.resample("ME").last().reindex(dt_idx)
    be = fund["seqq"].fillna(fund["ceqq"])
    be = be[~be.index.duplicated(keep="last")]
    be = be.unstack()
    be = be.resample("ME").last().reindex(dt_idx)
    be = be.ffill(limit=2)
    bm = (be * 1000 / me).stack()

    signals["bm"] = bm

    # TODO: cashflow = ibq + dpq

    # Operating cash flow-to-price ratio (oancf - operating cash flow)
    # Sales-to-price (saleq - sales)
    # Earnings-to-price (ib - Income Before Extraordinary Items)
    # Book-to-market ratio (seq - shareholders' equity)

    # Price momentum 11-1
    # Residual momentum

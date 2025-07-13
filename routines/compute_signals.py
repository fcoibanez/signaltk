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

    # Excess returns
    xs_rt = crsp["excess_ret"].astype(float).add(1).apply(np.log)
    xs_rt = xs_rt.unstack()
    xs_rt = xs_rt.resample("ME").last()

    collect_signals = {}

    # Book-to-market ratio
    me = (crsp["shrout"] * crsp["altprc"]).abs().replace(0, np.nan).astype(float)
    me = me.unstack()
    me = me.resample("ME").last().reindex(dt_idx)
    be = fund["seqq"].fillna(fund["ceqq"])
    be = be[~be.index.duplicated(keep="last")]
    be = be.unstack()
    be = be.resample("ME").last().reindex(dt_idx)
    be = be.ffill(limit=2)
    b2m = (be * 1000 / me).stack()

    collect_signals["b2m"] = b2m

    # Cash flow-to-price ratio (ibq + dpq) / market capitalization
    cf = (fund["ibq"] + fund["dpq"])
    cf = cf[~cf.index.duplicated(keep="last")]
    cf = cf.unstack().resample("ME").last().reindex(dt_idx)
    cf = cf.ffill(limit=2)
    c2p = (cf * 1000 / me).stack()
    collect_signals["c2p"] = c2p

    # Sales-to-price (saleq - sales)
    sales = fund["saleq"]
    sales = sales[~sales.index.duplicated(keep="last")]
    sales = sales.unstack().resample("ME").last().reindex(dt_idx)
    sales = sales.ffill(limit=2)
    s2p = (sales * 1000 / me).stack()
    collect_signals["s2p"] = s2p

    # Earnings-to-price (ibq - Income Before Extraordinary Items)
    earnings = fund["ibq"]
    earnings = earnings[~earnings.index.duplicated(keep="last")]
    earnings = earnings.unstack().resample("ME").last().reindex(dt_idx)
    earnings = earnings.ffill(limit=2)
    e2p = (earnings * 1000 / me).stack()
    collect_signals["e2p"] = e2p

    # Price momentum 11-1
    OBS_THRESH = 12
    n_obs = xs_rt.rolling(12).count()
    valid_obs = n_obs == OBS_THRESH
    mom_12_1 = xs_rt.rolling(12).sum() - xs_rt

    # Residual momentum

    # Beta

    # Collect signals
    signals = pd.DataFrame(collect_signals)
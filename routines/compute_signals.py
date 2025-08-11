"""Signals calculation routines.
Source: Kewei Hou, Chen Xue and Lu Zhang (2020), Replicating Anomalies
Taking only significant signals into account, beta is not included for that reason
https://www.jstor.org/stable/pdf/48574457.pdf
"""

if __name__ == "__main__":
    import pandas as pd
    from signaltk import constants as cst
    import numpy as np
    from tqdm import tqdm
    from signaltk.config.signals import SignalsConfig
    import statsmodels.api as sm

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
    cf = fund["ibq"] + fund["dpq"]
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
    collect_signals["mom_12_1"] = mom_12_1[valid_obs].stack()

    # Price momentum 6-1 (Jagadeesh and Titman, 1993)
    OBS_THRESH = 6
    n_obs = xs_rt.rolling(6).count()
    valid_obs = n_obs == OBS_THRESH
    mom_6_1 = xs_rt.rolling(6).sum() - xs_rt
    collect_signals["mom_6_1"] = mom_6_1[valid_obs].stack()

    # Residual momentum 11 - 1 (Blitz, Huij, and Martens, 2011)
    OBS_THRESH = 36
    n_obs = xs_rt.rolling(36).count()
    valid_obs = n_obs == OBS_THRESH
    resid_mom = pd.DataFrame(index=xs_rt.index, columns=xs_rt.columns)
    for dt in tqdm(xs_rt.index):
        flags_t = valid_obs.xs(dt)
        valid_ids = flags_t[flags_t].index
        for sec_id in valid_ids:
            y = xs_rt.loc[:dt, sec_id].tail(36)
            X = ff.reindex(y.index).drop(["cma", "rmw", "umd", "rf"], axis=1)
            resid = sm.OLS(endog=y, exog=sm.add_constant(X.astype(float))).fit().resid
            resid_mom.loc[dt, sec_id] = (resid.iloc[-12:].sum() - resid.iloc[-1]).item()
    collect_signals["resid_mom"] = resid_mom.stack()

    # Short-term reversal (Jegadeesh, 1990)
    collect_signals["strev"] = -xs_rt.stack()

    # Collect signals
    signals = pd.DataFrame(collect_signals)
    signals.index.names = ["date", "permno"]
    signals.to_pickle(f"{cst.WDIR}/data/raw_signals.pkl")

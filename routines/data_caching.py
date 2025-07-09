if __name__ == "__main__":
    import wrds
    import pandas as pd
    import numpy as np
    from signaltk import constants as cst
    from signaltk.core.utils import assign_industry, assign_exchange

    DIR = cst.WDIR + "/data"

    # ---------------------------------------------------------------------
    # Preamble
    conn = wrds.Connection(wrds_username="fcoibanez")

    # ---------------------------------------------------------------------
    # F&F Factors
    query = f"""
     SELECT date, mktrf, smb, hml, rmw, cma, umd, rf
     FROM ff.fivefactors_monthly
     """
    ff = conn.raw_sql(query)
    ff["date"] = pd.DatetimeIndex(ff["date"]) + pd.offsets.MonthEnd(0)
    ff = ff.set_index("date")
    ff.to_pickle(rf"{DIR}/ff.pkl")

    # ---------------------------------------------------------------------
    # CRSP (borrowed from https://www.tidy-finance.org/python/wrds-crsp-and-compustat.html)
    query = """
        SELECT msf.permno, msf.date, date_trunc('month', msf.date)::date as month, msf.ret, msf.shrout, msf.vol, msf.prc, msf.altprc, msenames.exchcd, msenames.siccd, msedelist.dlret, msedelist.dlstcd
        FROM crsp.msf AS msf
        LEFT JOIN crsp.msenames as msenames ON msf.permno = msenames.permno AND msenames.namedt <= msf.date AND msf.date <= msenames.nameendt
        LEFT JOIN crsp.msedelist as msedelist
        ON msf.permno = msedelist.permno AND date_trunc('month', msf.date)::date = date_trunc('month', msedelist.dlstdt)::date
        WHERE msf.date BETWEEN '01/01/1960' AND '12/31/2024' AND msenames.shrcd IN (10, 11)
        """
    raw_crsp_monthly = conn.raw_sql(query)
    crsp_monthly = raw_crsp_monthly.copy()

    # Next, we follow Bali, Engle, and Murray (2016) in transforming listing exchange codes to explicit exchange names.
    crsp_monthly["exchange"] = crsp_monthly["exchcd"].apply(assign_exchange)
    crsp_monthly["industry"] = crsp_monthly["siccd"].apply(assign_industry)

    """
    The delisting of a security usually results when a company ceases operations, 
    declares bankruptcy, merges, does not meet listing requirements, or seeks to 
    become private.
    """

    conditions_delisting = [
        crsp_monthly["dlstcd"].isna(),
        (~crsp_monthly["dlstcd"].isna()) & (~crsp_monthly["dlret"].isna()),
        crsp_monthly["dlstcd"].isin([500, 520, 580, 584])
        | (
            (crsp_monthly["dlstcd"].astype(float) >= 551)
            & (crsp_monthly["dlstcd"].astype(float) <= 574)
        ),
        crsp_monthly["dlstcd"].astype(float) == 100,
    ]

    choices_delisting = [
        crsp_monthly["ret"].astype(float),
        crsp_monthly["dlret"].astype(float),
        -0.30,
        crsp_monthly["ret"].astype(float),
    ]

    crsp_monthly = crsp_monthly.assign(
        ret_adj=np.select(conditions_delisting, choices_delisting, default=-1)
    )
    crsp_monthly = crsp_monthly.drop(columns=["dlret", "dlstcd"])
    crsp_monthly["date"] = pd.DatetimeIndex(
        crsp_monthly["month"]
    ) + pd.offsets.MonthEnd(0)
    crsp_monthly = crsp_monthly.set_index(["date", "permno"])
    crsp_monthly = crsp_monthly.sort_index()
    crsp_monthly = crsp_monthly.join(ff["rf"], on="date")
    crsp_monthly["excess_ret"] = crsp_monthly["ret_adj"] - crsp_monthly["rf"]
    crsp_monthly["dollar_vol"] = crsp_monthly["prc"].mul(crsp_monthly["vol"])
    crsp_monthly.drop(["rf", "month"], axis=1, inplace=True)
    crsp_monthly["mktcap"] = (
        crsp_monthly["shrout"].mul(crsp_monthly["altprc"]).abs().replace(0, np.nan)
    )
    crsp_monthly.to_pickle(f"{DIR}/crsp.pkl")

    # ---------------------------------------------------------------------
    # GICS industry classification
    sec_id = pd.read_pickle(f"{DIR}/crsp.pkl").reset_index()["permno"].unique()
    permno_str = ",".join([f"{str(x)}" for x in sec_id])

    query = f"""
        SELECT link.lpermno AS permno, co.gvkey, co.conm, co.ggroup, co.gind, co.gsector, co.gsubind, co.dldte, co.dlrsn
        FROM comp.company as co
        LEFT JOIN crsp.ccmxpf_linktable AS link ON co.gvkey = link.gvkey
        WHERE link.linktype IN ('LU', 'LC')
        AND linkprim IN ('P', 'C')
        AND usedflag = 1
        AND link.lpermno IN ({permno_str})
        """

    gics = conn.raw_sql(query)
    gics.set_index("permno", inplace=True)
    gics = gics[~gics.index.duplicated(keep="first")]

    sector_mapping = {
        "10": "Energy",
        "15": "Materials",
        "20": "Industrials",
        "25": "Consumer Discretionary",
        "30": "Consumer Staples",
        "35": "Health Care",
        "40": "Financials",
        "45": "Information Technology",
        "50": "Communication Services",
        "55": "Utilities",
        "60": "Real Estate",
    }

    gics["sector"] = gics["gsector"].map(sector_mapping)
    gics.to_pickle(f"{DIR}/gics_mapping.pkl")

    # ---------------------------------------------------------------------
    # Fundamentals
    compustat_query = f"""
        SELECT link.lpermno AS permno, co.gvkey, co.datadate, co.ceqq, co.seqq, co.saleq, co.ibq, co.dpq
        FROM comp.fundq as co
        LEFT JOIN crsp.ccmxpf_linktable AS link ON co.gvkey = link.gvkey
        WHERE link.linktype IN ('LU', 'LC')
        AND linkprim IN ('P', 'C')
        AND usedflag = 1
        AND indfmt = 'INDL'
        AND datafmt = 'STD'
        AND consol = 'C'
        AND datadate BETWEEN '2023-01-01' AND '2024-12-31'
        AND link.lpermno IN ({permno_str})
        """

    # TODO: cashflow = idbq + dpq

    fund = conn.raw_sql(compustat_query)

    fund["datadate"] = pd.to_datetime(fund["datadate"])
    fund.rename(columns={"datadate": "date"}, inplace=True)
    fund.set_index(["date", "permno"], inplace=True)
    fund.drop("gvkey", axis=1, inplace=True)
    fund = fund.astype(float)
    fund.to_pickle(f"{DIR}/fundamentals.pkl")

# Operating cash flow-to-price ratio (oancf - operating cash flow)
# Sales-to-price (saleq - sales)
# Earnings-to-price (ib - Income Before Extraordinary Items)
# Book-to-market ratio (seq - shareholders' equity)

# Price momentum 11-1
# Residual momentum

"""AETHER v3.1 research utilities. No broker execution or live-data claims."""
from __future__ import annotations
import csv, io, math
from collections import defaultdict
import numpy as np

REQUIRED = {"date", "symbol", "open", "high", "low", "close", "volume"}

def parse_ohlcv_csv(csv_text: str):
    if not isinstance(csv_text, str) or not csv_text.strip(): raise ValueError("CSV is empty")
    reader=csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames: raise ValueError("CSV header is required")
    fields={x.strip().lower() for x in reader.fieldnames}
    missing=REQUIRED-fields
    if missing: raise ValueError("Missing required columns: "+", ".join(sorted(missing)))
    rows=[]; seen=set()
    for line,row in enumerate(reader, start=2):
        try:
            r={k.strip().lower():v for k,v in row.items() if k is not None}
            d=r["date"].strip(); sym=r["symbol"].strip().upper()
            if not sym: raise ValueError("symbol is blank")
            vals={k:float(r[k]) for k in ("open","high","low","close","volume")}
            if not all(math.isfinite(x) for x in vals.values()): raise ValueError("non-finite number")
            if min(vals[k] for k in ("open","high","low","close"))<=0 or vals["volume"]<0: raise ValueError("prices must be positive and volume non-negative")
            if vals["high"] < max(vals["open"],vals["close"],vals["low"]) or vals["low"] > min(vals["open"],vals["close"],vals["high"]): raise ValueError("inconsistent OHLC range")
            key=(sym,d)
            if key in seen: raise ValueError("duplicate symbol/date")
            seen.add(key); rows.append({"date":d,"symbol":sym,**vals})
        except Exception as e: raise ValueError(f"CSV line {line}: {e}") from e
    if not rows: raise ValueError("CSV contains no data rows")
    rows.sort(key=lambda x:(x["symbol"],x["date"]))
    for sym in {r["symbol"] for r in rows}:
        ds=[r["date"] for r in rows if r["symbol"]==sym]
        if ds != sorted(ds): raise ValueError(f"Dates for {sym} are not chronological")
    return {"rows":rows,"symbols":sorted({r["symbol"] for r in rows}),"row_count":len(rows),"provenance":{"source":"user_csv","live_data":False,"corporate_action_adjustment":"unknown; user must confirm","survivorship_bias":"not assessed","timezone":"not inferred"}}

def india_cost_estimate(notional: float, side: str, segment: str, rates: dict):
    """Estimate costs using explicitly supplied decimal rates; no tax-rate defaults."""
    if not math.isfinite(notional) or notional<0: raise ValueError("notional must be finite and >=0")
    if side not in ("BUY","SELL"): raise ValueError("side must be BUY or SELL")
    if segment not in ("CASH_DELIVERY","CASH_INTRADAY","FUTURES","OPTIONS"): raise ValueError("unsupported segment")
    allowed={"brokerage_per_order","stt_buy_rate","stt_sell_rate","exchange_txn_rate","sebi_rate","gst_rate","stamp_buy_rate","slippage_bps","impact_bps","other_per_order"}
    unknown=set(rates)-allowed
    if unknown: raise ValueError("unknown rate fields: "+", ".join(sorted(unknown)))
    r={k:float(v) for k,v in rates.items()}
    if any(not math.isfinite(v) or v<0 for v in r.values()): raise ValueError("all cost rates must be finite and non-negative")
    brokerage=r.get("brokerage_per_order",0.0); other=r.get("other_per_order",0.0)
    stt_rate=r.get("stt_buy_rate" if side=="BUY" else "stt_sell_rate",0.0)
    stt=notional*stt_rate; exchange=notional*r.get("exchange_txn_rate",0.0); sebi=notional*r.get("sebi_rate",0.0)
    stamp=notional*r.get("stamp_buy_rate",0.0) if side=="BUY" else 0.0
    taxable=brokerage+exchange+sebi
    gst=taxable*r.get("gst_rate",0.0)
    slippage=notional*(r.get("slippage_bps",0.0)+r.get("impact_bps",0.0))/10000.0
    total=brokerage+other+stt+exchange+sebi+stamp+gst+slippage
    return {"segment":segment,"side":side,"notional":notional,"components":{"brokerage":brokerage,"other":other,"stt":stt,"exchange_transaction":exchange,"sebi":sebi,"stamp_duty":stamp,"gst_on_brokerage_exchange_sebi":gst,"slippage_and_impact":slippage},"total_estimated_cost":total,"effective_cost_bps":(total/notional*10000 if notional else 0.0),"rates_are_user_supplied":True,"warning":"Estimate only. Confirm current broker contract notes, exchange circulars, tax treatment, instrument-specific STT/stamp duty and applicable caps. This is not a legal or tax calculation."}

def cash_equity_backtest(closes, signals, capital=50000.0, costs_per_side=None):
    """Long-only close-to-close research simulation. Signals at t-1 earn return t."""
    c=np.asarray(closes,dtype=float); s=np.asarray(signals,dtype=int)
    if c.ndim!=1 or len(c)<3 or not np.isfinite(c).all() or np.any(c<=0): raise ValueError("closes must be finite positive 1-D values with >=3 bars")
    if s.ndim!=1 or len(s)!=len(c)-1 or not np.isin(s,[0,1]).all(): raise ValueError("signals must be 0/1 and have len(closes)-1; each signal applies to next return")
    if not math.isfinite(capital) or capital<=0: raise ValueError("capital must be >0")
    cost=float(costs_per_side or 0.0)
    if not math.isfinite(cost) or cost<0 or cost>=1: raise ValueError("costs_per_side must be in [0,1)")
    rets=c[1:]/c[:-1]-1.0; prev=np.r_[0,s[:-1]]; turnover=np.abs(s-prev)
    net=s*rets-turnover*cost; nav=capital*np.cumprod(1+net); peak=np.maximum.accumulate(np.r_[capital,nav])[1:]; dd=nav/peak-1
    active=net[s==1]; gross_profit=float(net[net>0].sum()); gross_loss=float(-net[net<0].sum())
    std=float(np.std(net,ddof=1)) if len(net)>1 else 0.0
    return {"capital":capital,"ending_equity":float(nav[-1]),"total_return_net":float(nav[-1]/capital-1),"max_drawdown":float(dd.min()),"sharpe_zero_rf":float(np.mean(net)/std*math.sqrt(252)) if std else 0.0,"win_rate_active_days":float(np.mean(active>0)) if len(active) else 0.0,"profit_factor":gross_profit/gross_loss if gross_loss else (None if gross_profit else 0.0),"turnover_events":int(turnover.sum()),"exposure_fraction":float(np.mean(s)),"net_daily_returns":net.tolist(),"equity_curve":nav.tolist(),"research_only":True,"execution_assumption":"Signal formed at prior close; return earned next close-to-close. No intraday fill claim."}

def futures_contract_pnl(entry_price, exit_price, lot_size, lots, direction, entry_cost=0.0, exit_cost=0.0):
    vals=[entry_price,exit_price,lot_size,lots,entry_cost,exit_cost]
    if not all(math.isfinite(float(x)) for x in vals): raise ValueError("all inputs must be finite")
    if min(entry_price,exit_price,lot_size,lots)<=0 or min(entry_cost,exit_cost)<0: raise ValueError("prices, lot size and lots must be positive; costs non-negative")
    if direction not in ("LONG","SHORT"): raise ValueError("direction must be LONG or SHORT")
    qty=int(lot_size)*int(lots)
    if qty<=0 or qty!=lot_size*lots: raise ValueError("lot_size and lots must be positive integers")
    gross=(exit_price-entry_price)*qty*(1 if direction=="LONG" else -1)
    costs=float(entry_cost)+float(exit_cost)
    return {"quantity":qty,"gross_pnl":gross,"estimated_costs":costs,"net_pnl":gross-costs,"return_on_entry_notional":(gross-costs)/(entry_price*qty),"margin_not_inferred":True,"research_only":True}

def research_gate(metrics, min_trades=30, max_drawdown_limit=0.20):
    """Conservative status; never declares a strategy live-ready."""
    reasons=[]
    if int(metrics.get("trades",0))<min_trades: reasons.append("insufficient trade count")
    if float(metrics.get("net_return",-1))<=0: reasons.append("non-positive net return")
    if abs(float(metrics.get("max_drawdown",1)))>max_drawdown_limit: reasons.append("drawdown exceeds research limit")
    if not metrics.get("out_of_sample",False): reasons.append("out-of-sample validation missing")
    return {"status":"RESEARCH_REVIEW" if not reasons else "NO_GO", "reasons":reasons,"live_trading_authorized":False,"note":"Passing this preliminary gate is not proof of an edge or authorization for live trading."}

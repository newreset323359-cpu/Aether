import pytest
from app.engines.research_v31 import parse_ohlcv_csv, india_cost_estimate, cash_equity_backtest, futures_contract_pnl, research_gate

CSV="date,symbol,open,high,low,close,volume\n2026-01-01,ABC,10,12,9,11,100\n2026-01-02,ABC,11,13,10,12,120\n"
def test_csv_import_and_provenance():
    x=parse_ohlcv_csv(CSV); assert x["row_count"]==2 and x["symbols"]==["ABC"] and x["provenance"]["live_data"] is False
def test_csv_rejects_bad_ohlc():
    with pytest.raises(ValueError): parse_ohlcv_csv(CSV.replace("10,12,9,11","10,8,9,11"))
def test_csv_rejects_duplicate():
    with pytest.raises(ValueError,match="duplicate"): parse_ohlcv_csv(CSV+"2026-01-02,ABC,11,13,10,12,120\n")
def test_costs_add_up_and_no_hidden_defaults():
    r=india_cost_estimate(100000,"BUY","CASH_DELIVERY",{"brokerage_per_order":20,"stamp_buy_rate":0.0001,"gst_rate":0.18,"slippage_bps":2})
    assert r["total_estimated_cost"]>20 and r["rates_are_user_supplied"]
def test_costs_reject_negative():
    with pytest.raises(ValueError): india_cost_estimate(100,"SELL","FUTURES",{"stt_sell_rate":-1})
def test_cash_backtest_uses_prior_signal_and_costs():
    r=cash_equity_backtest([100,110,100],[1,0],50000,0.001)
    assert r["ending_equity"]==pytest.approx(50000*1.099*0.999)
    assert r["research_only"] is True
def test_cash_backtest_validates_lengths():
    with pytest.raises(ValueError): cash_equity_backtest([1,2,3],[1])
def test_futures_lot_pnl():
    r=futures_contract_pnl(100,105,25,2,"LONG",10,10)
    assert r["gross_pnl"]==250 and r["net_pnl"]==230 and r["margin_not_inferred"]
def test_futures_reject_invalid_direction():
    with pytest.raises(ValueError): futures_contract_pnl(100,105,25,1,"BUY")
def test_gate_never_authorizes_live():
    r=research_gate({"trades":100,"net_return":0.2,"max_drawdown":-0.1,"out_of_sample":True})
    assert r["status"]=="RESEARCH_REVIEW" and r["live_trading_authorized"] is False
def test_gate_blocks_weak_metrics():
    assert research_gate({"trades":2,"net_return":-0.1,"max_drawdown":-0.4})["status"]=="NO_GO"

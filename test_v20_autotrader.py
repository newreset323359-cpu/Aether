from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_paper_account_defaults_to_50000_and_is_paper_only():
    cfg = client.get("/api/v1/autotrader/config")
    assert cfg.status_code == 200
    assert cfg.json()["initial_capital"] == 50000
    assert cfg.json()["segments"] == ["CASH", "FNO"]
    assert cfg.json()["real_orders_enabled"] is False
    summary = client.get("/api/v1/autotrader/summary").json()
    assert summary["cash_balance"] == 50000
    assert summary["mode"] == "PAPER_ONLY"

def test_buy_then_partial_sell_updates_cash_and_realized_pnl():
    buy = client.post("/api/v1/autotrader/orders", json={
        "symbol":"RELIANCE","exchange":"NSE","segment":"CASH","side":"BUY",
        "quantity":10,"lot_size":1,"trade_style":"INTRADAY",
        "reference_price":100,"stop_loss_price":95,"client_order_id":"test-buy-0001"
    })
    assert buy.status_code == 200, buy.text
    assert buy.json()["real_orders_enabled"] is False
    assert buy.json()["status"] == "FILLED"
    summary = client.get("/api/v1/autotrader/summary").json()
    assert summary["cash_balance"] < 50000
    assert len(summary["positions"]) == 1
    sell = client.post("/api/v1/autotrader/orders", json={
        "symbol":"RELIANCE","exchange":"NSE","segment":"CASH","side":"SELL",
        "quantity":5,"lot_size":1,"trade_style":"INTRADAY",
        "reference_price":110,"client_order_id":"test-sell-0001"
    })
    assert sell.status_code == 200, sell.text
    assert sell.json()["realized_pnl"] > 0
    assert client.get("/api/v1/autotrader/summary").json()["positions"][0]["quantity"] == 5

def test_risk_limit_and_short_selling_are_rejected():
    too_risky = client.post("/api/v1/autotrader/orders", json={
        "symbol":"NIFTY26","exchange":"NSE","segment":"FNO","side":"BUY",
        "quantity":1,"lot_size":50,"trade_style":"INTRADAY",
        "reference_price":100,"stop_loss_price":80,"client_order_id":"test-risk-0001"
    })
    assert too_risky.status_code == 422
    short = client.post("/api/v1/autotrader/orders", json={
        "symbol":"BANKNIFTY","exchange":"NSE","segment":"FNO","side":"SELL",
        "quantity":1,"lot_size":15,"trade_style":"INTRADAY",
        "reference_price":100,"client_order_id":"test-short-0001"
    })
    assert short.status_code == 422

def test_duplicate_order_id_rejected():
    payload = {"symbol":"INFY","exchange":"NSE","segment":"CASH","side":"BUY",
               "quantity":1,"lot_size":1,"trade_style":"SWING",
               "reference_price":100,"stop_loss_price":95,"client_order_id":"same-order-001"}
    assert client.post("/api/v1/autotrader/orders", json=payload).status_code == 200
    assert client.post("/api/v1/autotrader/orders", json=payload).status_code == 409

def test_strategy_signal_returns_research_only_signal():
    bars = []
    for i in range(60):
        c = 100 + i * 0.5
        bars.append({"open":c-0.2,"high":c+0.3,"low":c-0.4,"close":c,"volume":1000+i*10})
    r = client.post("/api/v1/autotrader/signals/evaluate",
                    json={"strategy":"trend_following","bars":bars})
    assert r.status_code == 200, r.text
    assert r.json()["signal"] in {"BUY","HOLD","EXIT_OR_AVOID"}
    assert r.json()["execution"] == "DISABLED_PAPER_ONLY"

def test_groww_status_never_enables_order_execution():
    r = client.get("/api/v1/groww/status")
    assert r.status_code == 200
    assert r.json()["order_execution"] == "DISABLED_IN_THIS_BUILD"

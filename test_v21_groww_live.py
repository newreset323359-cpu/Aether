import os
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_groww_connection_is_encrypted_and_does_not_arm_live_trading(monkeypatch):
    from app.main import Session, select, GrowwConnection, _groww_token
    from cryptography.fernet import Fernet
    monkeypatch.setenv("GROWW_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("AETHER_ALLOW_INSECURE_GROWW_CONNECT", "true")
    token = "test-access-token-with-enough-length-123456"
    r = client.post("/api/v1/groww/connect", json={"access_token": token})
    assert r.status_code == 200, r.text
    assert r.json()["connected"] is True
    assert r.json()["live_trading_armed"] is False
    with Session() as db:
        row = db.scalar(select(GrowwConnection))
        assert row is not None
        assert token not in row.encrypted_access_token
        assert _groww_token(db, 1) == token

def test_live_order_gate_is_off_by_default(monkeypatch):
    monkeypatch.setenv("AETHER_LIVE_TRADING_ENABLED", "false")
    r = client.post("/api/v1/groww/orders", json={
        "symbol":"RELIANCE","exchange":"NSE","segment":"CASH","side":"BUY",
        "quantity":1,"lot_size":1,"product":"CNC","order_type":"LIMIT",
        "limit_price":100,"stop_loss_price":98
    })
    assert r.status_code == 423

def test_live_arm_requires_broker_approval_and_server_flag(monkeypatch):
    monkeypatch.setenv("AETHER_LIVE_TRADING_ENABLED", "true")
    monkeypatch.setenv("AETHER_GROWW_ALGO_APPROVED", "false")
    r = client.post("/api/v1/groww/live/enable", json={"confirmation":"I UNDERSTAND LIVE TRADING"})
    assert r.status_code == 423

def test_strategy_config_enforces_risk_budget():
    bad = client.post("/api/v1/autotrader/strategies", json={
        "name":"Too risky","symbol":"RELIANCE","groww_symbol":"NSE-RELIANCE",
        "exchange":"NSE","segment":"CASH","candle_interval":"5minute",
        "strategy":"trend_following","lot_size":1,"product":"MIS",
        "max_order_value":12500,"stop_loss_pct":0.10,"target_pct":0.04
    })
    assert bad.status_code == 422
    good = client.post("/api/v1/autotrader/strategies", json={
        "name":"Trend test","symbol":"RELIANCE","groww_symbol":"NSE-RELIANCE",
        "exchange":"NSE","segment":"CASH","candle_interval":"5minute",
        "strategy":"trend_following","lot_size":1,"product":"MIS",
        "max_order_value":10000,"stop_loss_pct":0.02,"target_pct":0.04
    })
    assert good.status_code == 200, good.text
    assert good.json()["enabled"] is False

def test_worker_stays_disabled_without_explicit_env_flag(monkeypatch):
    from app.main import run_auto_scan_once
    monkeypatch.setenv("AETHER_AUTO_WORKER_ENABLED", "false")
    assert run_auto_scan_once()["scanned"] == 0

def test_worker_eval_parses_groww_candle_arrays():
    from app.main import _worker_eval
    bars=[]
    for i in range(60):
        c=100+i*0.5
        bars.append([f"2026-01-{(i%28)+1:02d}T10:00:00",c-0.2,c+0.3,c-0.4,c,1000+i*10,None])
    signal, price, reason = _worker_eval("trend_following", bars)
    assert signal in {"BUY","HOLD","EXIT_OR_AVOID"}
    assert price > 0


def test_live_order_adapter_sends_groww_order_only_when_all_gates_armed(monkeypatch):
    from app.main import Session, select, LiveTradingState
    from cryptography.fernet import Fernet
    monkeypatch.setenv("GROWW_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("AETHER_ALLOW_INSECURE_GROWW_CONNECT", "true")
    monkeypatch.setenv("AETHER_LIVE_TRADING_ENABLED", "true")
    monkeypatch.setenv("AETHER_GROWW_ALGO_APPROVED", "true")
    token = "mocked-groww-token-123456789012345"
    connected = client.post("/api/v1/groww/connect", json={"access_token": token})
    assert connected.status_code == 200
    with Session() as db:
        state = db.scalar(select(LiveTradingState).where(LiveTradingState.user_id == 1))
        state.armed = True
        db.commit()

    from app import main as api
    calls = []
    def fake_request(g_token, method, path, params=None, body=None):
        calls.append((method, path, params, body))
        if path == "/v1/positions/user":
            return {"status":"SUCCESS","payload":{"positions":[]}}
        if path == "/v1/order/create":
            return {"status":"SUCCESS","payload":{"groww_order_id":"MOCK-GROWW-ORDER-1","order_status":"OPEN"}}
        raise AssertionError(path)
    monkeypatch.setattr(api, "_groww_request", fake_request)

    r = client.post("/api/v1/groww/orders", json={
        "symbol":"RELIANCE","exchange":"NSE","segment":"CASH","side":"BUY",
        "quantity":10,"lot_size":1,"product":"CNC","order_type":"LIMIT",
        "limit_price":100,"stop_loss_price":98
    })
    assert r.status_code == 200, r.text
    assert r.json()["groww_order_id"] == "MOCK-GROWW-ORDER-1"
    order_call = next(c for c in calls if c[1] == "/v1/order/create")
    assert order_call[3]["trading_symbol"] == "RELIANCE"
    assert order_call[3]["transaction_type"] == "BUY"
    assert order_call[3]["order_type"] == "LIMIT"

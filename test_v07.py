from fastapi.testclient import TestClient
import os, tempfile

def test_cash_fifo_and_exposure_api():
    # The test suite runs with the configured test database in isolated environment.
    from app.main import app
    client=TestClient(app)
    p=client.post("/api/v1/portfolios",json={"name":"v07-test"}).json()
    pid=p["id"]
    buy1={"symbol":"ABC","side":"BUY","quantity":10,"price":100,"fees":10,"trade_date":"2026-10-01"}
    buy2={"symbol":"ABC","side":"BUY","quantity":5,"price":120,"fees":0,"trade_date":"2026-10-02"}
    sell={"symbol":"ABC","side":"SELL","quantity":12,"price":130,"fees":12,"trade_date":"2026-10-03"}
    assert client.post(f"/api/v1/portfolios/{pid}/transactions",json=buy1).status_code==200
    assert client.post(f"/api/v1/portfolios/{pid}/transactions",json=buy2).status_code==200
    assert client.post(f"/api/v1/portfolios/{pid}/transactions",json=sell).status_code==200
    lots=client.get(f"/api/v1/portfolios/{pid}/fifo-lots").json()
    assert len(lots["open_lots"])==1
    assert lots["open_lots"][0]["remaining_quantity"]==3
    cash=client.get(f"/api/v1/portfolios/{pid}/cash-ledger").json()
    assert cash["balances"]["INR"]==((-(10*100+10))+(-(5*120))+((12*130)-12))
    dep=client.post(f"/api/v1/portfolios/{pid}/cash-entries",json={
        "entry_type":"DEPOSIT","amount":10000,"trade_date":"2026-10-01"})
    assert dep.status_code==200
    assert client.get(f"/api/v1/portfolios/{pid}/exposure").status_code==200

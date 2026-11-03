from app.engines.data_ingestion import parse_bars, parse_actions
import pytest

def test_parse_valid_bars():
    csv="symbol,date,open,high,low,close,volume\nRELIANCE,2026-10-30,100,110,95,105,1000\n"
    rows,bad=parse_bars(csv,source="test")
    assert len(rows)==1 and not bad
    assert rows[0]["symbol"]=="RELIANCE" and rows[0]["close"]==105

def test_reject_duplicate_and_invalid_ohlc():
    csv="symbol,date,open,high,low,close,volume\nABC,2026-10-30,10,12,8,11,100\nABC,2026-10-30,10,12,8,11,100\nXYZ,2026-10-30,10,9,8,11,100\n"
    rows,bad=parse_bars(csv)
    assert len(rows)==1 and len(bad)==2

def test_reject_missing_columns():
    with pytest.raises(ValueError):
        parse_bars("symbol,date,close\nABC,2026-01-01,10")

def test_parse_corporate_actions():
    csv="symbol,ex_date,action_type,value,currency\nABC,01-11-2026,dividend,2.5,INR\n"
    rows,bad=parse_actions(csv)
    assert len(rows)==1 and rows[0]["ex_date"]=="2026-11-01" and not bad

def test_reject_unsupported_action():
    csv="symbol,ex_date,action_type,value\nABC,2026-11-01,crypto-airdrop,2\n"
    rows,bad=parse_actions(csv)
    assert not rows and len(bad)==1

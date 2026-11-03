from app.engines.instruments import parse_instruments
import pytest

def test_parse_instrument_master():
    csv="symbol,exchange,name,isin,segment,lot_size,tick_size\nRELIANCE,NSE,Reliance Industries,INE002A01018,EQ,1,0.05\n"
    rows,bad=parse_instruments(csv)
    assert len(rows)==1 and not bad
    assert rows[0]["symbol"]=="RELIANCE" and rows[0]["exchange"]=="NSE"

def test_reject_bad_exchange_and_isin():
    csv="symbol,exchange,name,isin\nABC,XYZ,ABC Ltd,BAD\n"
    rows,bad=parse_instruments(csv)
    assert not rows and len(bad)==1

def test_missing_instrument_columns():
    with pytest.raises(ValueError):
        parse_instruments("symbol,name\nABC,ABC Ltd")

"""CSV parsing and validation for market bars and corporate actions."""
import csv, io
from datetime import date, datetime

BAR_REQUIRED={"symbol","date","open","high","low","close","volume"}
ACTION_REQUIRED={"symbol","ex_date","action_type","value"}

def _number(row, key, allow_zero=False):
    try: value=float(row[key])
    except (KeyError, TypeError, ValueError): raise ValueError(f"Invalid numeric field: {key}")
    if value < 0 or (not allow_zero and value <= 0):
        raise ValueError(f"{key} must be {'non-negative' if allow_zero else 'positive'}")
    return value

def _date(value):
    value=(value or "").strip()
    for fmt in ("%Y-%m-%d","%d-%m-%Y","%d/%m/%Y","%Y%m%d"):
        try: return datetime.strptime(value,fmt).date().isoformat()
        except ValueError: pass
    raise ValueError(f"Invalid date: {value}")

def parse_bars(csv_text, default_symbol=None, interval="1d", source="csv-import", adjusted=False):
    reader=csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames: raise ValueError("CSV is empty or has no header")
    headers={h.strip().lower():h for h in reader.fieldnames}
    missing=BAR_REQUIRED-set(headers)
    if missing: raise ValueError("Missing columns: "+", ".join(sorted(missing)))
    records=[]; rejected=[]; seen=set()
    for line,row0 in enumerate(reader,start=2):
        row={k.lower().strip(): (v or "").strip() for k,v in row0.items() if k}
        try:
            symbol=(row.get("symbol") or default_symbol or "").upper()
            if not symbol: raise ValueError("symbol is required")
            dt=_date(row.get("date"))
            vals={k:_number(row,k,allow_zero=(k=="volume")) for k in ("open","high","low","close","volume")}
            if vals["high"] < max(vals["open"],vals["close"],vals["low"]): raise ValueError("high is below another OHLC value")
            if vals["low"] > min(vals["open"],vals["close"],vals["high"]): raise ValueError("low is above another OHLC value")
            key=(symbol,dt,interval)
            if key in seen: raise ValueError("duplicate symbol/date/interval")
            seen.add(key)
            records.append(dict(symbol=symbol,bar_date=dt,interval=interval,**vals,source=source,adjusted=bool(adjusted)))
        except ValueError as e: rejected.append({"line":line,"reason":str(e)})
    if not records and not rejected: raise ValueError("CSV contains no data rows")
    return records,rejected

def parse_actions(csv_text, source="csv-import"):
    reader=csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames: raise ValueError("CSV is empty or has no header")
    headers={h.strip().lower() for h in reader.fieldnames}
    missing=ACTION_REQUIRED-headers
    if missing: raise ValueError("Missing columns: "+", ".join(sorted(missing)))
    records=[]; rejected=[]
    for line,row0 in enumerate(reader,start=2):
        row={k.lower().strip():(v or "").strip() for k,v in row0.items() if k}
        try:
            symbol=row["symbol"].upper()
            if not symbol: raise ValueError("symbol is required")
            action_type=row["action_type"].lower()
            if action_type not in {"dividend","split","bonus","rights","buyback","merger","other"}: raise ValueError("unsupported action_type")
            value=_number(row,"value",allow_zero=False)
            records.append(dict(symbol=symbol,ex_date=_date(row["ex_date"]),action_type=action_type,value=value,currency=(row.get("currency") or "INR").upper(),source=source))
        except ValueError as e: rejected.append({"line":line,"reason":str(e)})
    if not records and not rejected: raise ValueError("CSV contains no data rows")
    return records,rejected

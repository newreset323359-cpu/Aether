"""Reference instrument-master CSV parser. It does not connect to exchanges."""
import csv, io

REQUIRED={"symbol","exchange","name"}
def parse_instruments(csv_text, source="csv-import"):
    reader=csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames: raise ValueError("CSV is empty or has no header")
    headers={h.strip().lower() for h in reader.fieldnames}
    missing=REQUIRED-headers
    if missing: raise ValueError("Missing columns: "+", ".join(sorted(missing)))
    rows=[]; rejected=[]; seen=set()
    for line,raw in enumerate(reader,start=2):
        r={k.strip().lower():(v or "").strip() for k,v in raw.items() if k}
        try:
            symbol=r["symbol"].upper(); exchange=r["exchange"].upper(); name=r["name"]
            if not symbol or not name: raise ValueError("symbol and name are required")
            if exchange not in {"NSE","BSE"}: raise ValueError("exchange must be NSE or BSE")
            key=(symbol,exchange)
            if key in seen: raise ValueError("duplicate symbol/exchange in file")
            seen.add(key)
            lot=int(r.get("lot_size") or 1); tick=float(r.get("tick_size") or .05)
            if lot<1 or tick<=0: raise ValueError("lot_size and tick_size must be positive")
            isin=r.get("isin") or None
            if isin and len(isin)!=12: raise ValueError("ISIN must contain 12 characters")
            rows.append(dict(symbol=symbol,exchange=exchange,name=name,isin=isin,
                segment=(r.get("segment") or "EQ").upper(),
                instrument_type=(r.get("instrument_type") or "EQUITY").upper(),
                lot_size=lot,tick_size=tick,source=source))
        except (ValueError,TypeError) as e: rejected.append({"line":line,"reason":str(e)})
    if not rows and not rejected: raise ValueError("CSV contains no data rows")
    return rows,rejected

"""Provider-neutral market-data interface. Demo adapter never claims to be live."""
from abc import ABC, abstractmethod
from datetime import datetime, timezone

class MarketDataProvider(ABC):
    @abstractmethod
    def quote(self, symbol: str) -> dict: ...

class DemoMarketDataProvider(MarketDataProvider):
    DATA={"RELIANCE":2942.5,"HDFCBANK":1718.2,"INFY":1468.4,"TCS":4012.0,"NIFTY50":24185.4,"SENSEX":79486.3}
    def quote(self,symbol):
        key=symbol.upper().replace(" ","")
        if key not in self.DATA: raise KeyError(f"No demo quote for {symbol}")
        return {"symbol":symbol.upper(),"price":self.DATA[key],"currency":"INR",
                "source":"SYNTHETIC_DEMO","is_live":False,"timestamp":datetime.now(timezone.utc).isoformat()}

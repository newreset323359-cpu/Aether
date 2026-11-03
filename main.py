import os
import numpy as np
from fastapi import FastAPI, HTTPException, Query, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from .models import Base, Portfolio, Position, AuditEvent, MarketBar, CorporateAction, DataIngestion, Instrument, PortfolioTransaction, Benchmark, PortfolioBenchmark, CashEntry, AccessUser, PortfolioAccess, PaperAccount, PaperPosition, PaperOrder, GrowwConnection, LiveTradingState, AutoStrategyConfig, LiveBrokerOrder
from .engines.risk import historical_var_cvar, parametric_var_cvar, drawdown_stats
from .engines.options import black_scholes
from .engines.portfolio import portfolio_summary, mean_variance_weights, equal_weight
from .engines.backtest import run_backtest
from .engines.adaptive import adaptive_signal, validate_walk_forward
from .engines.marketdata import DemoMarketDataProvider

DB=os.getenv("AETHER_DATABASE_URL","sqlite:///./aether.db")
engine=create_engine(DB,connect_args={"check_same_thread":False} if DB.startswith("sqlite") else {})
Session=sessionmaker(bind=engine,expire_on_commit=False)
Base.metadata.create_all(engine)
# Lightweight additive migration for v0.9 SQLite/PostgreSQL databases.
from sqlalchemy import inspect, text
def _migrate_v10():
    insp=inspect(engine)
    if "access_users" in insp.get_table_names():
        cols={c["name"] for c in insp.get_columns("access_users")}
        with engine.begin() as conn:
            if "password_hash" not in cols: conn.execute(text("ALTER TABLE access_users ADD COLUMN password_hash VARCHAR(256) NOT NULL DEFAULT ''"))
            if "is_admin" not in cols: conn.execute(text("ALTER TABLE access_users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE"))
_migrate_v10()
app=FastAPI(title="AETHER AutoTrader API",version="3.1.0",description="India-first portfolio and risk research API.")
from fastapi.middleware.cors import CORSMiddleware
_cors_origins=[x.strip() for x in os.getenv("AETHER_CORS_ORIGINS","http://localhost:8000,http://127.0.0.1:8000").split(",") if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=_cors_origins,allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"],allow_headers=["Authorization","Content-Type","X-Aether-API-Key","X-Aether-Admin-Key"])

@app.middleware("http")
async def security_guard(request, call_next):
    from starlette.responses import JSONResponse
    path=request.url.path
    if os.getenv("AETHER_ENV")=="test" and path.startswith("/api/"):
        # Explicit test-only bypass; never enable AETHER_ENV=test in a deployed service.
        with Session() as db:
            u=db.get(AccessUser,1)
            if not u:
                u=AccessUser(id=1,username="test-admin",display_name="Test Admin",status="active",is_admin=True)
                db.add(u);db.commit()
        request.state.aether_user_id=1;request.state.aether_is_admin=True;request.state.aether_role="admin"
        return await call_next(request)
    if not path.startswith("/api/") or path in {"/api/v1/auth/bootstrap","/api/v1/auth/login"}:
        return await call_next(request)
    # Optional shared API key is an additional perimeter control, not user identity.
    configured=os.getenv("AETHER_API_KEY")
    if configured and request.headers.get("x-aether-api-key")!=configured:
        return JSONResponse({"detail":"Valid X-Aether-API-Key header required"},status_code=401)
    auth=request.headers.get("authorization","")
    if not auth.lower().startswith("bearer "):
        return JSONResponse({"detail":"Bearer access token required"},status_code=401)
    try:
        from .security.auth import decode_access_token
        claims=decode_access_token(auth.split(" ",1)[1])
        user_id=int(claims["sub"])
    except Exception:
        return JSONResponse({"detail":"Invalid or expired access token"},status_code=401)
    with Session() as db:
        user=db.get(AccessUser,user_id)
        if not user or user.status!="active":
            return JSONResponse({"detail":"User is inactive or unavailable"},status_code=403)
        request.state.aether_user_id=user.id
        request.state.aether_is_admin=bool(user.is_admin)
        request.state.aether_role="admin" if user.is_admin else "viewer"
        # Enforce portfolio-level authorization for all legacy and new portfolio routes.
        import re
        match=re.match(r"^/api/v1/portfolios/(\d+)(?:/|$)",path)
        if match and not user.is_admin:
            pid=int(match.group(1))
            grant=db.scalar(select(PortfolioAccess).where(PortfolioAccess.portfolio_id==pid,PortfolioAccess.user_id==user.id))
            if not grant:
                return JSONResponse({"detail":"No access to this portfolio"},status_code=403)
            request.state.aether_role=grant.role
            method=request.method.upper()
            if method not in {"GET","HEAD","OPTIONS"}:
                trade_write=path.endswith("/transactions") and grant.role=="trader"
                if grant.role not in {"owner","manager"} and not trade_write:
                    return JSONResponse({"detail":"Insufficient portfolio role for this action"},status_code=403)
        # Non-portfolio administrative writes require an administrator.
        admin_only_paths=(
            path.startswith("/api/v1/access/") or path.startswith("/api/v1/admin/") or
            path=="/api/v1/audit" or
            (path.startswith("/api/v1/reference/") and request.method.upper()!="GET") or
            (path=="/api/v1/benchmarks" and request.method.upper()!="GET")
        )
        if admin_only_paths and not user.is_admin:
            return JSONResponse({"detail":"Administrator role required"},status_code=403)
        if path.startswith("/api/v1/data/ingest/") and request.method.upper()!="GET" and not user.is_admin:
            return JSONResponse({"detail":"Administrator role required for data ingestion"},status_code=403)
    return await call_next(request)

provider=DemoMarketDataProvider()

class PortfolioIn(BaseModel):
    name:str=Field(min_length=1,max_length=120)
    base_currency:str="INR"
class PositionIn(BaseModel):
    symbol:str
    quantity:float=Field(gt=0)
    average_cost:float=Field(gt=0)
    last_price:float=Field(gt=0)
    asset_class:str="EQUITY"
class ReturnsIn(BaseModel):
    returns:list[float]
    confidence:float=Field(default=.95,gt=.5,lt=1)
    portfolio_value:float=Field(default=1,gt=0)
class OptionIn(BaseModel):
    spot:float=Field(gt=0); strike:float=Field(gt=0); time_years:float=Field(gt=0)
    rate:float; volatility:float=Field(gt=0); option_type:str="call"; dividend_yield:float=0
class BacktestIn(BaseModel):
    asset_returns:list[list[float]]
    weights:list[float]
    transaction_cost_bps:float=Field(default=10,ge=0)
    rebalance_every:int=Field(default=1,ge=1)

@app.get("/health")
def health(): return {"status":"ok","service":"AETHER API","version":"1.0.0","demo_mode":True}
@app.get("/api/v1/market/quote/{symbol}")
def quote(symbol:str):
    try:return provider.quote(symbol)
    except KeyError as e:raise HTTPException(404,str(e))
@app.post("/api/v1/portfolios")
def create_portfolio(data:PortfolioIn, request:Request):
    with Session() as s:
        p=Portfolio(name=data.name,base_currency=data.base_currency);s.add(p);s.flush()
        s.add(PortfolioAccess(portfolio_id=p.id,user_id=request.state.aether_user_id,role="owner"))
        s.add(AuditEvent(event_type="portfolio.created",payload={"portfolio_id":p.id,"name":p.name,"owner_user_id":request.state.aether_user_id}))
        s.commit();return {"id":p.id,"name":p.name,"base_currency":p.base_currency}
@app.get("/api/v1/portfolios")
def list_portfolios(request:Request):
    with Session() as s:
        if request.state.aether_is_admin:
            rows=s.scalars(select(Portfolio).order_by(Portfolio.id)).all()
        else:
            ids=[x.portfolio_id for x in s.scalars(select(PortfolioAccess).where(PortfolioAccess.user_id==request.state.aether_user_id)).all()]
            rows=s.scalars(select(Portfolio).where(Portfolio.id.in_(ids)).order_by(Portfolio.id)).all() if ids else []
        return [{"id":p.id,"name":p.name,"base_currency":p.base_currency} for p in rows]
@app.post("/api/v1/portfolios/{portfolio_id}/positions")
def add_position(portfolio_id:int,data:PositionIn):
    with Session() as s:
        if not s.get(Portfolio,portfolio_id):raise HTTPException(404,"Portfolio not found")
        p=Position(portfolio_id=portfolio_id,**data.model_dump());s.add(p)
        s.add(AuditEvent(event_type="position.created",payload={"portfolio_id":portfolio_id,**data.model_dump()}))
        s.commit();return {"id":p.id,**data.model_dump()}
@app.get("/api/v1/portfolios/{portfolio_id}/summary")
def summary(portfolio_id:int):
    with Session() as s:
        if not s.get(Portfolio,portfolio_id):raise HTTPException(404,"Portfolio not found")
        positions=s.scalars(select(Position).where(Position.portfolio_id==portfolio_id)).all()
        return portfolio_summary([{"symbol":p.symbol,"quantity":p.quantity,"price":p.last_price,"cost_price":p.average_cost} for p in positions])
@app.post("/api/v1/risk/var/historical")
def risk_hist(data:ReturnsIn):
    try:return historical_var_cvar(data.returns,data.confidence,data.portfolio_value)
    except ValueError as e:raise HTTPException(422,str(e))
@app.post("/api/v1/risk/var/parametric")
def risk_param(data:ReturnsIn):
    try:return parametric_var_cvar(data.returns,data.confidence,data.portfolio_value)
    except ValueError as e:raise HTTPException(422,str(e))
@app.post("/api/v1/risk/drawdown")
def drawdown(data:ReturnsIn):
    try:return drawdown_stats(data.returns)
    except ValueError as e:raise HTTPException(422,str(e))
@app.post("/api/v1/derivatives/black-scholes")
def option(data:OptionIn):
    try:return black_scholes(**data.model_dump())
    except ValueError as e:raise HTTPException(422,str(e))
@app.post("/api/v1/portfolio/optimize/equal-weight")
def optimize_equal(n:int=Query(ge=1)):
    try:return {"weights":equal_weight(n)}
    except ValueError as e:raise HTTPException(422,str(e))
@app.post("/api/v1/portfolio/optimize/mean-variance")
def optimize_mv(payload:dict):
    try:return {"weights":mean_variance_weights(payload["expected_returns"],payload["covariance"],payload.get("risk_aversion",4))}
    except (ValueError,KeyError) as e:raise HTTPException(422,str(e))
@app.post("/api/v1/backtest")
def backtest(data:BacktestIn):
    try:return run_backtest(data.asset_returns,data.weights,data.transaction_cost_bps,data.rebalance_every)
    except ValueError as e:raise HTTPException(422,str(e))
@app.get("/api/v1/audit")
def audit(limit:int=100):
    with Session() as s:
        rows=s.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(min(limit,500))).all()
        return [{"id":r.id,"event_type":r.event_type,"actor":r.actor,"payload":r.payload,"created_at":r.created_at} for r in rows]


# AETHER v0.3 advanced quantitative endpoints
from .engines.garch import fit_garch11, fit_egarch11
from .engines.hmm import fit_gaussian_hmm
from .engines.monte_carlo import simulate_portfolio
from .engines.implied_vol import implied_volatility
from .engines.optimization import risk_parity_weights, black_litterman_prior

@app.post("/api/v1/quant/garch")
def quant_garch(payload:dict):
    try:return fit_garch11(payload["returns"])
    except (ValueError,KeyError) as e:raise HTTPException(422,str(e))
@app.post("/api/v1/quant/egarch")
def quant_egarch(payload:dict):
    try:return fit_egarch11(payload["returns"])
    except (ValueError,KeyError) as e:raise HTTPException(422,str(e))
@app.post("/api/v1/quant/hmm")
def quant_hmm(payload:dict):
    try:return fit_gaussian_hmm(payload["returns"],payload.get("n_states",2),payload.get("max_iter",250))
    except (ValueError,KeyError) as e:raise HTTPException(422,str(e))
@app.post("/api/v1/risk/monte-carlo")
def risk_mc(payload:dict):
    try:return simulate_portfolio(**payload)
    except (ValueError,KeyError) as e:raise HTTPException(422,str(e))
@app.post("/api/v1/derivatives/implied-volatility")
def iv(payload:dict):
    try:return implied_volatility(**payload)
    except (ValueError,KeyError) as e:raise HTTPException(422,str(e))
@app.post("/api/v1/portfolio/optimize/risk-parity")
def risk_parity(payload:dict):
    try:return risk_parity_weights(payload["covariance"])
    except (ValueError,KeyError) as e:raise HTTPException(422,str(e))
@app.post("/api/v1/portfolio/black-litterman")
def black_litterman(payload:dict):
    try:return black_litterman_prior(**payload)
    except (ValueError,KeyError) as e:raise HTTPException(422,str(e))


# AETHER v0.4 research, stress and options-surface endpoints
from .engines.factors import factor_regression, fama_french_style_regression
from .engines.walkforward import walk_forward
from .engines.stress import portfolio_stress, historical_scenario_library
from .engines.options_surface import build_iv_surface

@app.post("/api/v1/research/factor-regression")
def factor_regression_api(payload:dict):
    try:
        return factor_regression(payload["asset_returns"],payload["factor_returns"],payload.get("factor_names"))
    except (ValueError,KeyError) as e: raise HTTPException(422,str(e))
@app.post("/api/v1/research/fama-french-style")
def ff_api(payload:dict):
    try:
        return fama_french_style_regression(payload["asset_returns"],payload["market"],payload["size"],payload["value"])
    except (ValueError,KeyError) as e: raise HTTPException(422,str(e))
@app.post("/api/v1/research/legacy-walk-forward")
def walk_forward_api(payload:dict):
    try:
        return walk_forward(payload["asset_returns"],payload["strategies"],payload.get("train_window",60),
                            payload.get("test_window",20),payload.get("transaction_cost_bps",10))
    except (ValueError,KeyError) as e: raise HTTPException(422,str(e))
@app.post("/api/v1/risk/stress")
def stress_api(payload:dict):
    try:
        return portfolio_stress(payload["weights"],payload["factor_exposures"],payload["factor_shocks"],
                                payload.get("portfolio_value",1),payload.get("asset_names"))
    except (ValueError,KeyError) as e: raise HTTPException(422,str(e))
@app.get("/api/v1/risk/stress/scenarios")
def stress_scenarios():
    return historical_scenario_library()
@app.post("/api/v1/derivatives/iv-surface")
def iv_surface_api(payload:dict):
    try:
        return build_iv_surface(payload["quotes"],payload["spot"],payload["rate"],payload.get("dividend_yield",0))
    except (ValueError,KeyError) as e: raise HTTPException(422,str(e))


# AETHER v0.5 data ingestion and provenance
from .engines.data_ingestion import parse_bars, parse_actions

class CSVImportIn(BaseModel):
    csv_text:str=Field(min_length=1)
    source:str=Field(default="csv-import",max_length=120)
    symbol:str|None=None
    interval:str=Field(default="1d",pattern="^(1d|1w|1m)$")
    adjusted:bool=False

class ActionImportIn(BaseModel):
    csv_text:str=Field(min_length=1)
    source:str=Field(default="csv-import",max_length=120)

@app.get("/api/v1/data/providers")
def data_providers():
    return {"active_provider":"demo-synthetic","providers":[
        {"id":"demo-synthetic","status":"available","live":False,"description":"Synthetic demo quotes; not exchange data"},
        {"id":"csv-import","status":"available","live":False,"description":"User-supplied historical CSV files"},
        {"id":"licensed-provider","status":"configuration_required","live":False,"description":"Adapter interface reserved for an authorized data vendor"}]}

@app.post("/api/v1/data/ingest/bars")
def ingest_bars(data:CSVImportIn):
    try: records,rejected=parse_bars(data.csv_text,data.symbol,data.interval,data.source,data.adjusted)
    except ValueError as e: raise HTTPException(422,str(e))
    with Session() as db:
        inserted=0
        for item in records:
            exists=db.scalar(select(MarketBar).where(MarketBar.symbol==item["symbol"],MarketBar.bar_date==item["bar_date"],MarketBar.interval==item["interval"]))
            if exists:
                rejected.append({"line":None,"reason":f"already stored: {item['symbol']} {item['bar_date']}"})
                continue
            db.add(MarketBar(**item)); inserted+=1
        job=DataIngestion(dataset="ohlcv",source=data.source,status="completed" if not rejected else ("partial" if inserted else "rejected"),
            rows_received=len(records)+len(rejected),rows_inserted=inserted,rows_rejected=len(rejected),
            details={"interval":data.interval,"adjusted":data.adjusted,"rejections":rejected[:100]})
        db.add(job); db.add(AuditEvent(event_type="market_data.csv_ingested",payload={"job_id":job.id,"source":data.source,"inserted":inserted,"rejected":len(rejected)}))
        db.commit()
        return {"ingestion_id":job.id,"dataset":"ohlcv","status":job.status,"rows_received":job.rows_received,"rows_inserted":inserted,"rows_rejected":len(rejected),"rejections":rejected[:100]}

@app.get("/api/v1/data/bars/{symbol}")
def get_bars(symbol:str,limit:int=Query(default=500,ge=1,le=10000),interval:str="1d"):
    with Session() as db:
        rows=db.scalars(select(MarketBar).where(MarketBar.symbol==symbol.upper(),MarketBar.interval==interval).order_by(MarketBar.bar_date.desc()).limit(limit)).all()
        return {"symbol":symbol.upper(),"interval":interval,"count":len(rows),"bars":[{"date":r.bar_date,"open":r.open,"high":r.high,"low":r.low,"close":r.close,"volume":r.volume,"source":r.source,"adjusted":r.adjusted} for r in reversed(rows)]}

@app.post("/api/v1/data/ingest/corporate-actions")
def ingest_actions(data:ActionImportIn):
    try: records,rejected=parse_actions(data.csv_text,data.source)
    except ValueError as e: raise HTTPException(422,str(e))
    with Session() as db:
        for item in records: db.add(CorporateAction(**item))
        job=DataIngestion(dataset="corporate-actions",source=data.source,status="completed" if not rejected else ("partial" if records else "rejected"),
            rows_received=len(records)+len(rejected),rows_inserted=len(records),rows_rejected=len(rejected),details={"rejections":rejected[:100]})
        db.add(job); db.commit()
        return {"ingestion_id":job.id,"dataset":"corporate-actions","status":job.status,"rows_received":job.rows_received,"rows_inserted":len(records),"rows_rejected":len(rejected),"rejections":rejected[:100]}

@app.get("/api/v1/data/corporate-actions/{symbol}")
def get_actions(symbol:str,limit:int=Query(default=500,ge=1,le=10000)):
    with Session() as db:
        rows=db.scalars(select(CorporateAction).where(CorporateAction.symbol==symbol.upper()).order_by(CorporateAction.ex_date.desc()).limit(limit)).all()
        return {"symbol":symbol.upper(),"count":len(rows),"actions":[{"ex_date":r.ex_date,"action_type":r.action_type,"value":r.value,"currency":r.currency,"source":r.source} for r in reversed(rows)]}

@app.get("/api/v1/data/ingestions")
def ingestion_history(limit:int=Query(default=100,ge=1,le=500)):
    with Session() as db:
        rows=db.scalars(select(DataIngestion).order_by(DataIngestion.id.desc()).limit(limit)).all()
        return [{"id":r.id,"dataset":r.dataset,"source":r.source,"status":r.status,"rows_received":r.rows_received,"rows_inserted":r.rows_inserted,"rows_rejected":r.rows_rejected,"details":r.details,"created_at":r.created_at} for r in rows]


@app.get("/api/v1/data/freshness")
def data_freshness(max_age_days:int=Query(default=3,ge=0,le=365)):
    from datetime import date
    with Session() as db:
        symbols=db.scalars(select(MarketBar.symbol).distinct()).all()
        items=[]
        for symbol in symbols:
            latest=db.scalar(select(MarketBar.bar_date).where(MarketBar.symbol==symbol).order_by(MarketBar.bar_date.desc()).limit(1))
            age=(date.today()-date.fromisoformat(latest)).days
            items.append({"symbol":symbol,"latest_date":latest,"calendar_days_old":age,
                          "status":"fresh" if age<=max_age_days else "stale"})
        return {"as_of":date.today().isoformat(),"max_age_days":max_age_days,
                "symbols":len(items),"fresh":sum(x["status"]=="fresh" for x in items),
                "stale":sum(x["status"]=="stale" for x in items),"items":items}


# AETHER v0.6 institutional reference data, portfolio ledger and benchmarks
from .engines.instruments import parse_instruments
from datetime import date

class InstrumentImportIn(BaseModel):
    csv_text:str=Field(min_length=1)
    source:str=Field(default="csv-import",max_length=120)

class TransactionIn(BaseModel):
    symbol:str=Field(min_length=1,max_length=32)
    side:str=Field(pattern="^(BUY|SELL|buy|sell)$")
    quantity:float=Field(gt=0)
    price:float=Field(gt=0)
    fees:float=Field(default=0,ge=0)
    trade_date:str
    notes:str|None=None

class BenchmarkIn(BaseModel):
    symbol:str=Field(min_length=1,max_length=32)
    name:str=Field(min_length=1,max_length=120)
    exchange:str=Field(default="NSE",pattern="^(NSE|BSE)$")

class AssignBenchmarkIn(BaseModel):
    benchmark_symbol:str=Field(min_length=1,max_length=32)

@app.post("/api/v1/reference/instruments/import")
def import_instruments(data:InstrumentImportIn):
    try: rows,rejected=parse_instruments(data.csv_text,data.source)
    except ValueError as e: raise HTTPException(422,str(e))
    with Session() as db:
        inserted=0; updated=0
        for row in rows:
            obj=db.scalar(select(Instrument).where(Instrument.symbol==row["symbol"],Instrument.exchange==row["exchange"]))
            if obj:
                for k,v in row.items(): setattr(obj,k,v)
                updated+=1
            else: db.add(Instrument(**row)); inserted+=1
        job=DataIngestion(dataset="instrument-master",source=data.source,
            status="completed" if not rejected else ("partial" if rows else "rejected"),
            rows_received=len(rows)+len(rejected),rows_inserted=inserted+updated,rows_rejected=len(rejected),
            details={"updated":updated,"rejections":rejected[:100]})
        db.add(job); db.add(AuditEvent(event_type="reference.instrument_master_imported",
            payload={"inserted":inserted,"updated":updated,"rejected":len(rejected),"source":data.source}))
        db.commit()
        return {"status":job.status,"inserted":inserted,"updated":updated,"rejected":len(rejected),"rejections":rejected[:100]}

@app.get("/api/v1/reference/instruments")
def list_instruments(exchange:str|None=None,query:str|None=None,limit:int=Query(default=500,ge=1,le=5000)):
    with Session() as db:
        stmt=select(Instrument)
        if exchange: stmt=stmt.where(Instrument.exchange==exchange.upper())
        if query: stmt=stmt.where((Instrument.symbol.contains(query.upper())) | (Instrument.name.contains(query)))
        rows=db.scalars(stmt.order_by(Instrument.symbol).limit(limit)).all()
        return [{"symbol":x.symbol,"exchange":x.exchange,"isin":x.isin,"name":x.name,"segment":x.segment,
                 "instrument_type":x.instrument_type,"lot_size":x.lot_size,"tick_size":x.tick_size,"source":x.source} for x in rows]

@app.post("/api/v1/benchmarks")
def create_benchmark(data:BenchmarkIn):
    with Session() as db:
        symbol=data.symbol.upper()
        obj=db.scalar(select(Benchmark).where(Benchmark.symbol==symbol))
        if obj: obj.name=data.name; obj.exchange=data.exchange
        else: obj=Benchmark(symbol=symbol,name=data.name,exchange=data.exchange); db.add(obj)
        db.commit()
        return {"symbol":symbol,"name":obj.name,"exchange":obj.exchange}

@app.get("/api/v1/benchmarks")
def list_benchmarks():
    with Session() as db:
        return [{"symbol":x.symbol,"name":x.name,"exchange":x.exchange,"source":x.source}
                for x in db.scalars(select(Benchmark).order_by(Benchmark.name)).all()]

@app.put("/api/v1/portfolios/{portfolio_id}/benchmark")
def assign_benchmark(portfolio_id:int,data:AssignBenchmarkIn):
    with Session() as db:
        if not db.get(Portfolio,portfolio_id): raise HTTPException(404,"Portfolio not found")
        symbol=data.benchmark_symbol.upper()
        if not db.scalar(select(Benchmark).where(Benchmark.symbol==symbol)): raise HTTPException(404,"Benchmark not found")
        link=db.scalar(select(PortfolioBenchmark).where(PortfolioBenchmark.portfolio_id==portfolio_id))
        if link: link.benchmark_symbol=symbol
        else: db.add(PortfolioBenchmark(portfolio_id=portfolio_id,benchmark_symbol=symbol))
        db.commit()
        return {"portfolio_id":portfolio_id,"benchmark_symbol":symbol}

@app.post("/api/v1/portfolios/{portfolio_id}/transactions")
def add_transaction(portfolio_id:int,data:TransactionIn):
    try: trade_date=date.fromisoformat(data.trade_date).isoformat()
    except ValueError: raise HTTPException(422,"trade_date must be YYYY-MM-DD")
    side=data.side.upper(); symbol=data.symbol.upper()
    with Session() as db:
        if not db.get(Portfolio,portfolio_id): raise HTTPException(404,"Portfolio not found")
        if side=="SELL":
            buys=db.scalars(select(PortfolioTransaction).where(PortfolioTransaction.portfolio_id==portfolio_id,
                PortfolioTransaction.symbol==symbol).order_by(PortfolioTransaction.trade_date,PortfolioTransaction.id)).all()
            net=sum(t.quantity if t.side=="BUY" else -t.quantity for t in buys)
            if data.quantity>net+1e-9: raise HTTPException(422,f"Insufficient available quantity: {max(0,net)}")
        tx=PortfolioTransaction(portfolio_id=portfolio_id,symbol=symbol,side=side,quantity=data.quantity,
            price=data.price,fees=data.fees,trade_date=trade_date,notes=data.notes)
        db.add(tx)
        cash_delta=-(data.quantity*data.price+data.fees) if side=="BUY" else (data.quantity*data.price-data.fees)
        db.add(CashEntry(portfolio_id=portfolio_id,entry_type=side,amount=cash_delta,
            trade_date=trade_date,reference=f"TRADE:{symbol}",notes="Auto-generated from portfolio transaction"))
        db.add(AuditEvent(event_type="portfolio.transaction_recorded",
            payload={"portfolio_id":portfolio_id,"symbol":symbol,"side":side,"quantity":data.quantity,"price":data.price}))
        db.commit()
        return {"id":tx.id,"portfolio_id":portfolio_id,"symbol":symbol,"side":side,"quantity":data.quantity,
                "price":data.price,"fees":data.fees,"trade_date":trade_date}

@app.get("/api/v1/portfolios/{portfolio_id}/transactions")
def list_transactions(portfolio_id:int,limit:int=Query(default=500,ge=1,le=5000)):
    with Session() as db:
        if not db.get(Portfolio,portfolio_id): raise HTTPException(404,"Portfolio not found")
        rows=db.scalars(select(PortfolioTransaction).where(PortfolioTransaction.portfolio_id==portfolio_id)
            .order_by(PortfolioTransaction.trade_date,PortfolioTransaction.id).limit(limit)).all()
        return [{"id":x.id,"symbol":x.symbol,"side":x.side,"quantity":x.quantity,"price":x.price,
                 "fees":x.fees,"trade_date":x.trade_date,"notes":x.notes} for x in rows]

@app.get("/api/v1/portfolios/{portfolio_id}/holdings")
def portfolio_holdings(portfolio_id:int):
    with Session() as db:
        if not db.get(Portfolio,portfolio_id): raise HTTPException(404,"Portfolio not found")
        txs=db.scalars(select(PortfolioTransaction).where(PortfolioTransaction.portfolio_id==portfolio_id)
            .order_by(PortfolioTransaction.trade_date,PortfolioTransaction.id)).all()
        book={}
        for t in txs:
            x=book.setdefault(t.symbol,{"quantity":0.0,"cost":0.0,"realized_pnl":0.0,"fees":0.0})
            if t.side=="BUY":
                x["cost"]+=t.quantity*t.price; x["quantity"]+=t.quantity; x["fees"]+=t.fees
            else:
                avg=x["cost"]/x["quantity"] if x["quantity"] else 0
                x["realized_pnl"]+=(t.price-avg)*t.quantity-t.fees
                x["cost"]-=avg*t.quantity; x["quantity"]-=t.quantity; x["fees"]+=t.fees
                if abs(x["quantity"])<1e-8: x["quantity"]=0; x["cost"]=0
        result=[]
        for symbol,x in book.items():
            qty=x["quantity"]; avg=x["cost"]/qty if qty else 0
            latest=db.scalar(select(MarketBar.close).where(MarketBar.symbol==symbol,MarketBar.interval=="1d")
                .order_by(MarketBar.bar_date.desc()).limit(1))
            market_value=qty*latest if latest is not None else None
            result.append({"symbol":symbol,"quantity":round(qty,8),"average_cost":round(avg,6),
                "market_price":latest,"market_value":market_value,"unrealized_pnl":(market_value-x["cost"]) if market_value is not None else None,
                "realized_pnl":round(x["realized_pnl"],2),"fees":round(x["fees"],2),
                "valuation_status":"priced_from_imported_daily_bar" if latest is not None else "awaiting_market_data"})
        return {"portfolio_id":portfolio_id,"holdings":result,"total_market_value":sum(x["market_value"] or 0 for x in result),
                "unpriced_positions":sum(x["market_value"] is None and x["quantity"]>0 for x in result)}

@app.get("/api/v1/portfolios/{portfolio_id}/benchmark-performance")
def benchmark_performance(portfolio_id:int):
    with Session() as db:
        if not db.get(Portfolio,portfolio_id): raise HTTPException(404,"Portfolio not found")
        link=db.scalar(select(PortfolioBenchmark).where(PortfolioBenchmark.portfolio_id==portfolio_id))
        if not link: raise HTTPException(404,"No benchmark assigned")
        bars=db.scalars(select(MarketBar).where(MarketBar.symbol==link.benchmark_symbol,MarketBar.interval=="1d")
            .order_by(MarketBar.bar_date)).all()
        if len(bars)<2: raise HTTPException(422,"At least two imported daily benchmark bars are required")
        first,last=bars[0],bars[-1]
        total_return=last.close/first.close-1
        return {"portfolio_id":portfolio_id,"benchmark_symbol":link.benchmark_symbol,
            "start_date":first.bar_date,"end_date":last.bar_date,"observations":len(bars),
            "start_level":first.close,"end_level":last.close,"total_return":total_return,
            "data_source":last.source,"note":"Benchmark index series must be supplied/imported; this is not a live index feed."}


# AETHER v0.7 cash management, FIFO lots and exposure analytics
class CashEntryIn(BaseModel):
    entry_type:str=Field(pattern="^(DEPOSIT|WITHDRAWAL|DIVIDEND|INTEREST|FEE|TAX|ADJUSTMENT)$")
    amount:float=Field(gt=0)
    trade_date:str
    currency:str=Field(default="INR",pattern="^[A-Z]{3}$")
    reference:str|None=None
    notes:str|None=None

@app.post("/api/v1/portfolios/{portfolio_id}/cash-entries")
def create_cash_entry(portfolio_id:int,data:CashEntryIn):
    try: trade_date=date.fromisoformat(data.trade_date).isoformat()
    except ValueError: raise HTTPException(422,"trade_date must be YYYY-MM-DD")
    sign=-1 if data.entry_type in {"WITHDRAWAL","FEE","TAX"} else 1
    with Session() as db:
        if not db.get(Portfolio,portfolio_id): raise HTTPException(404,"Portfolio not found")
        entry=CashEntry(portfolio_id=portfolio_id,entry_type=data.entry_type,amount=sign*data.amount,
            currency=data.currency,trade_date=trade_date,reference=data.reference,notes=data.notes)
        db.add(entry); db.add(AuditEvent(event_type="portfolio.cash_entry_recorded",
            payload={"portfolio_id":portfolio_id,"entry_type":data.entry_type,"amount":sign*data.amount,
                     "currency":data.currency,"reference":data.reference}))
        db.commit()
        return {"id":entry.id,"portfolio_id":portfolio_id,"entry_type":entry.entry_type,
                "amount":entry.amount,"currency":entry.currency,"trade_date":entry.trade_date}

@app.get("/api/v1/portfolios/{portfolio_id}/cash-ledger")
def cash_ledger(portfolio_id:int,limit:int=Query(default=1000,ge=1,le=10000)):
    with Session() as db:
        if not db.get(Portfolio,portfolio_id): raise HTTPException(404,"Portfolio not found")
        rows=db.scalars(select(CashEntry).where(CashEntry.portfolio_id==portfolio_id)
            .order_by(CashEntry.trade_date,CashEntry.id).limit(limit)).all()
        balances={}
        ledger=[]
        for x in rows:
            balances[x.currency]=balances.get(x.currency,0)+x.amount
            ledger.append({"id":x.id,"date":x.trade_date,"type":x.entry_type,"amount":x.amount,
                "currency":x.currency,"running_balance":round(balances[x.currency],2),
                "reference":x.reference,"notes":x.notes})
        return {"portfolio_id":portfolio_id,"balances":{k:round(v,2) for k,v in balances.items()},"entries":ledger}

@app.get("/api/v1/portfolios/{portfolio_id}/fifo-lots")
def fifo_lots(portfolio_id:int):
    with Session() as db:
        if not db.get(Portfolio,portfolio_id): raise HTTPException(404,"Portfolio not found")
        txs=db.scalars(select(PortfolioTransaction).where(PortfolioTransaction.portfolio_id==portfolio_id)
            .order_by(PortfolioTransaction.trade_date,PortfolioTransaction.id)).all()
        books={}; realized={}
        for t in txs:
            lots=books.setdefault(t.symbol,[])
            if t.side=="BUY":
                unit_cost=(t.quantity*t.price+t.fees)/t.quantity
                lots.append({"date":t.trade_date,"quantity":t.quantity,"remaining":t.quantity,"unit_cost":unit_cost})
            else:
                remaining=t.quantity; proceeds=t.quantity*t.price-t.fees
                while remaining>1e-9 and lots:
                    lot=lots[0]; take=min(remaining,lot["remaining"])
                    realized[t.symbol]=realized.get(t.symbol,0)+(t.price-lot["unit_cost"])*take
                    lot["remaining"]-=take; remaining-=take
                    if lot["remaining"]<=1e-9: lots.pop(0)
                if remaining>1e-8: raise HTTPException(409,"Ledger contains a sell without sufficient FIFO lots")
        output=[]
        for symbol,lots in books.items():
            for lot in lots:
                if lot["remaining"]>1e-9:
                    output.append({"symbol":symbol,"acquisition_date":lot["date"],
                        "remaining_quantity":round(lot["remaining"],8),"unit_cost_including_buy_fees":round(lot["unit_cost"],6)})
        return {"portfolio_id":portfolio_id,"open_lots":output,
            "realized_pnl_before_sell_fees":{k:round(v,2) for k,v in realized.items()},
            "note":"FIFO accounting estimate; realized P&L shown before allocating sell-side fees and excludes taxes/corporate actions."}

@app.get("/api/v1/portfolios/{portfolio_id}/exposure")
def portfolio_exposure(portfolio_id:int):
    with Session() as db:
        if not db.get(Portfolio,portfolio_id): raise HTTPException(404,"Portfolio not found")
        txs=db.scalars(select(PortfolioTransaction).where(PortfolioTransaction.portfolio_id==portfolio_id)
            .order_by(PortfolioTransaction.trade_date,PortfolioTransaction.id)).all()
        quantities={}
        for t in txs: quantities[t.symbol]=quantities.get(t.symbol,0)+(t.quantity if t.side=="BUY" else -t.quantity)
        rows=[]
        for symbol,qty in quantities.items():
            if qty<=1e-9: continue
            price=db.scalar(select(MarketBar.close).where(MarketBar.symbol==symbol,MarketBar.interval=="1d")
                .order_by(MarketBar.bar_date.desc()).limit(1))
            instrument=db.scalar(select(Instrument).where(Instrument.symbol==symbol).order_by(Instrument.exchange))
            rows.append({"symbol":symbol,"quantity":round(qty,8),"price":price,
                "market_value":qty*price if price is not None else None,
                "asset_type":instrument.instrument_type if instrument else "UNCLASSIFIED"})
        priced=[x for x in rows if x["market_value"] is not None]
        total=sum(x["market_value"] for x in priced)
        for x in rows: x["weight_of_priced_assets"]=x["market_value"]/total if total and x["market_value"] is not None else None
        asset_types={}
        for x in priced: asset_types[x["asset_type"]]=asset_types.get(x["asset_type"],0)+x["market_value"]
        return {"portfolio_id":portfolio_id,"priced_market_value":round(total,2),
            "unpriced_positions":sum(x["market_value"] is None for x in rows),
            "positions":rows,"asset_type_exposure":{k:{"market_value":round(v,2),"weight":v/total if total else 0} for k,v in asset_types.items()},
            "concentration_top_5_weight":round(sum(sorted([x["weight_of_priced_assets"] or 0 for x in rows],reverse=True)[:5]),6),
            "note":"Exposure uses latest imported daily close; it excludes cash, derivatives, accrued income and unpriced holdings."}


# AETHER v0.8 Performance & Risk Intelligence
from .engines.performance import xirr, performance_metrics, relative_metrics, attribution

@app.get("/api/v1/portfolios/{portfolio_id}/performance/nav")
def daily_portfolio_nav(portfolio_id:int, start_date:str|None=None, end_date:str|None=None):
    """Reconstruct daily NAV from transaction/cash ledgers and imported daily close bars."""
    try:
        if start_date: date.fromisoformat(start_date)
        if end_date: date.fromisoformat(end_date)
    except ValueError: raise HTTPException(422,"Dates must use YYYY-MM-DD")
    with Session() as db:
        if not db.get(Portfolio,portfolio_id): raise HTTPException(404,"Portfolio not found")
        txs=db.scalars(select(PortfolioTransaction).where(PortfolioTransaction.portfolio_id==portfolio_id)
            .order_by(PortfolioTransaction.trade_date,PortfolioTransaction.id)).all()
        cash=db.scalars(select(CashEntry).where(CashEntry.portfolio_id==portfolio_id)
            .order_by(CashEntry.trade_date,CashEntry.id)).all()
        bars=db.scalars(select(MarketBar).where(MarketBar.interval=="1d").order_by(MarketBar.bar_date)).all()
        if not txs and not cash: raise HTTPException(422,"Portfolio has no ledger activity")
        all_dates=sorted({x.trade_date for x in txs+cash} | {b.bar_date for b in bars})
        if start_date: all_dates=[d for d in all_dates if d>=start_date]
        if end_date: all_dates=[d for d in all_dates if d<=end_date]
        if not all_dates: raise HTTPException(422,"No dated data in requested range")
        symbols={x.symbol for x in txs}
        px={sym:{} for sym in symbols}
        for b in bars:
            if b.symbol in px: px[b.symbol][b.bar_date]=b.close
        quantities={}; cash_balance=0.0; txi=ci=0; nav_rows=[]; external=[]
        # Include ledger dates before requested start so opening holdings/cash are carried in.
        portfolio_start=min(x.trade_date for x in txs+cash)
        timeline=sorted(d for d in ({x.trade_date for x in txs+cash} | {b.bar_date for b in bars}) if d>=portfolio_start)
        for d in timeline:
            while txi<len(txs) and txs[txi].trade_date<=d:
                t=txs[txi]; quantities[t.symbol]=quantities.get(t.symbol,0)+(t.quantity if t.side=="BUY" else -t.quantity); txi+=1
            while ci<len(cash) and cash[ci].trade_date<=d:
                c=cash[ci]; cash_balance+=c.amount
                if c.entry_type=="DEPOSIT": external.append((d,-c.amount))
                elif c.entry_type=="WITHDRAWAL": external.append((d,-c.amount))
                ci+=1
            if d not in all_dates: continue
            holdings_value=0.0; missing=[]
            for sym,q in quantities.items():
                if abs(q)<1e-10: continue
                candidates=[k for k in px[sym] if k<=d]
                if not candidates: missing.append(sym)
                else: holdings_value+=q*px[sym][max(candidates)]
            if missing: continue
            nav=holdings_value+cash_balance
            nav_rows.append({"date":d,"nav":round(nav,6),"cash":round(cash_balance,6),"holdings_value":round(holdings_value,6)})
        if len(nav_rows)<1: raise HTTPException(422,"No fully priced NAV observations; import daily bars for every held symbol")
        return {"portfolio_id":portfolio_id,"currency":db.get(Portfolio,portfolio_id).base_currency,
            "observations":len(nav_rows),"nav":nav_rows,"external_flows":[{"date":d,"investor_cash_flow":v} for d,v in external],
            "data_note":"NAV is reconstructed from ledger events and last available imported daily close. Dates with unpriced holdings are omitted; no FX, accrued income or derivatives margin."}

@app.get("/api/v1/portfolios/{portfolio_id}/performance/analytics")
def portfolio_performance_analytics(portfolio_id:int, periods_per_year:int=Query(default=252,ge=1,le=366),
                                    risk_free_rate:float=0.0, sector_map:str|None=None):
    import json
    with Session() as db:
        if not db.get(Portfolio,portfolio_id): raise HTTPException(404,"Portfolio not found")
        nav_data=daily_portfolio_nav(portfolio_id)
        rows=nav_data["nav"]
        if len(rows)<2: raise HTTPException(422,"At least two daily NAV observations are required")
        nav=np.array([x["nav"] for x in rows],float)
        flows={x["date"]:x["investor_cash_flow"] for x in nav_data["external_flows"]}
        # Modified Dietz-style daily flow adjustment: flow is assumed at end of day.
        rets=[]
        for i in range(1,len(nav)):
            flow=flows.get(rows[i]["date"],0.0)
            if nav[i-1]==0: raise HTTPException(422,"Cannot calculate return from zero prior NAV; record opening deposit")
            rets.append((nav[i]-flow)/nav[i-1]-1)
        if len(rets)<2: raise HTTPException(422,"At least three NAV observations are required for risk ratios")
        metrics=performance_metrics(rets,periods_per_year,risk_free_rate)
        cf_dates=[]; cf_values=[]
        for d,v in nav_data["external_flows"]:
            cf_dates.append(d); cf_values.append(v)
        cf_dates.append(rows[-1]["date"]); cf_values.append(float(nav[-1]))
        try: money_weighted=xirr(cf_values,cf_dates)
        except ValueError as e: money_weighted=None
        twr=float(np.prod(1+np.asarray(rets))-1)
        link=db.scalar(select(PortfolioBenchmark).where(PortfolioBenchmark.portfolio_id==portfolio_id))
        relative=None
        if link:
            bmap={b.bar_date:b.close for b in db.scalars(select(MarketBar).where(MarketBar.symbol==link.benchmark_symbol,MarketBar.interval=="1d")).all()}
            matched=[(i,bmap.get(rows[i]["date"])) for i in range(len(rows)) if bmap.get(rows[i]["date"]) is not None]
            if len(matched)>=3:
                bvals=np.array([v for _,v in matched],float); pvals=np.array([nav[i] for i,_ in matched],float)
                pr=pvals[1:]/pvals[:-1]-1; br=bvals[1:]/bvals[:-1]-1
                relative=relative_metrics(pr,br,periods_per_year)
                relative["benchmark_symbol"]=link.benchmark_symbol
        return {"portfolio_id":portfolio_id,"start_date":rows[0]["date"],"end_date":rows[-1]["date"],
            "daily_twr":twr,"annualized_money_weighted_xirr":money_weighted,
            "money_weighted_note":"XIRR uses external deposits/withdrawals and terminal NAV; requires a valid positive and negative flow.",
            "risk_metrics":metrics,"benchmark_relative":relative,"daily_returns":rets,
            "return_method_note":"Daily TWR chain-links daily NAV returns with external flows treated as end-of-day flows. Import sufficiently frequent NAV/price data for institutional-grade flow timing."}

@app.get("/api/v1/portfolios/{portfolio_id}/performance/attribution")
def portfolio_attribution(portfolio_id:int, sector_map:str|None=None):
    import json
    with Session() as db:
        if not db.get(Portfolio,portfolio_id): raise HTTPException(404,"Portfolio not found")
        txs=db.scalars(select(PortfolioTransaction).where(PortfolioTransaction.portfolio_id==portfolio_id)
            .order_by(PortfolioTransaction.trade_date,PortfolioTransaction.id)).all()
        qty={}
        for t in txs: qty[t.symbol]=qty.get(t.symbol,0)+(t.quantity if t.side=="BUY" else -t.quantity)
        inst={x.symbol:x for x in db.scalars(select(Instrument)).all()}
        bars={}
        for sym in qty:
            b=db.scalar(select(MarketBar).where(MarketBar.symbol==sym,MarketBar.interval=="1d").order_by(MarketBar.bar_date.desc()).limit(1))
            if b: bars[sym]=b.close
        holdings=[{"symbol":sym,"market_value":q*bars[sym],"asset_class":(inst[sym].instrument_type if sym in inst else "EQUITY"),
                   "sector":(inst[sym].sector if sym in inst else "UNKNOWN")} for sym,q in qty.items() if sym in bars and q>0]
        try: overrides=json.loads(sector_map) if sector_map else {}
        except Exception: raise HTTPException(422,"sector_map must be a JSON object string")
        return {"portfolio_id":portfolio_id,**attribution(holdings,overrides)}

@app.post("/api/v1/performance/metrics")
def performance_metrics_api(payload:dict):
    try:
        result=performance_metrics(payload["returns"],payload.get("periods_per_year",252),payload.get("risk_free_rate",0))
        if "benchmark_returns" in payload:
            result["benchmark_relative"]=relative_metrics(payload["returns"],payload["benchmark_returns"],payload.get("periods_per_year",252))
        return result
    except (ValueError,KeyError) as e: raise HTTPException(422,str(e))

@app.post("/api/v1/performance/xirr")
def xirr_api(payload:dict):
    try:return {"xirr":xirr(payload["cash_flows"],payload["dates"]),"annualized":True}
    except (ValueError,KeyError) as e: raise HTTPException(422,str(e))

@app.get("/api/v1/risk/dashboard/{portfolio_id}")
def advanced_risk_dashboard(portfolio_id:int):
    with Session() as db:
        if not db.get(Portfolio,portfolio_id): raise HTTPException(404,"Portfolio not found")
    analytics=portfolio_performance_analytics(portfolio_id,252,0.0)
    risk=analytics["risk_metrics"]
    return {"portfolio_id":portfolio_id,"as_of":analytics["end_date"],"risk_metrics":risk,
        "benchmark_relative":analytics["benchmark_relative"],
        "risk_flags":{"drawdown_over_10pct":risk["max_drawdown"]<=-0.10,
                      "annualized_volatility_over_25pct":risk["annualized_volatility"]>=0.25,
                      "negative_sharpe":risk["sharpe_ratio"] is not None and risk["sharpe_ratio"]<0},
        "methodology":"Historical realized daily returns; annualization defaults to 252 trading days. Ratios are descriptive, not forecasts or investment advice."}


# AETHER v0.9 Institutional portfolio management
class AccessUserIn(BaseModel):
    username:str=Field(min_length=3,max_length=80,pattern="^[A-Za-z0-9_.-]+$")
    display_name:str=Field(default="",max_length=120)

class PortfolioGrantIn(BaseModel):
    username:str=Field(min_length=3,max_length=80)
    role:str=Field(pattern="^(owner|manager|analyst|trader|viewer)$")

def require_admin_key(x_aether_admin_key:str|None=Header(default=None)):
    expected=os.getenv("AETHER_ADMIN_KEY")
    if not expected:
        raise HTTPException(503,"Set AETHER_ADMIN_KEY before using access-administration endpoints")
    if x_aether_admin_key!=expected:
        raise HTTPException(401,"Invalid administrator key")

@app.post("/api/v1/access/users",dependencies=[__import__("fastapi").Depends(require_admin_key)])
def create_access_user(data:AccessUserIn):
    with Session() as db:
        if db.scalar(select(AccessUser).where(AccessUser.username==data.username)):
            raise HTTPException(409,"Username already exists")
        u=AccessUser(username=data.username,display_name=data.display_name,status="active")
        db.add(u);db.commit()
        return {"id":u.id,"username":u.username,"display_name":u.display_name,"status":u.status}

@app.post("/api/v1/access/portfolios/{portfolio_id}/grant",dependencies=[__import__("fastapi").Depends(require_admin_key)])
def grant_portfolio_access(portfolio_id:int,data:PortfolioGrantIn):
    with Session() as db:
        if not db.get(Portfolio,portfolio_id): raise HTTPException(404,"Portfolio not found")
        u=db.scalar(select(AccessUser).where(AccessUser.username==data.username))
        if not u: raise HTTPException(404,"User not found")
        a=db.scalar(select(PortfolioAccess).where(PortfolioAccess.portfolio_id==portfolio_id,PortfolioAccess.user_id==u.id))
        if a: a.role=data.role
        else: db.add(PortfolioAccess(portfolio_id=portfolio_id,user_id=u.id,role=data.role))
        db.add(AuditEvent(event_type="access.role_granted",payload={"portfolio_id":portfolio_id,"username":u.username,"role":data.role}))
        db.commit()
        return {"portfolio_id":portfolio_id,"username":u.username,"role":data.role}

@app.get("/api/v1/access/portfolios/{portfolio_id}",dependencies=[__import__("fastapi").Depends(require_admin_key)])
def list_portfolio_access(portfolio_id:int):
    with Session() as db:
        if not db.get(Portfolio,portfolio_id): raise HTTPException(404,"Portfolio not found")
        rows=db.scalars(select(PortfolioAccess).where(PortfolioAccess.portfolio_id==portfolio_id)).all()
        return [{"username":db.get(AccessUser,x.user_id).username,"role":x.role} for x in rows]

@app.get("/api/v1/portfolios/consolidated")
def consolidated_portfolios(request:Request):
    """Consolidated valuation grouped by base currency; never silently converts FX."""
    with Session() as db:
        if request.state.aether_is_admin:
            portfolios=db.scalars(select(Portfolio).order_by(Portfolio.id)).all()
        else:
            ids=[x.portfolio_id for x in db.scalars(select(PortfolioAccess).where(PortfolioAccess.user_id==request.state.aether_user_id)).all()]
            portfolios=db.scalars(select(Portfolio).where(Portfolio.id.in_(ids)).order_by(Portfolio.id)).all() if ids else []
        groups={}
        detail=[]
        for p in portfolios:
            txs=db.scalars(select(PortfolioTransaction).where(PortfolioTransaction.portfolio_id==p.id)
                .order_by(PortfolioTransaction.trade_date,PortfolioTransaction.id)).all()
            qty={}
            for t in txs: qty[t.symbol]=qty.get(t.symbol,0)+(t.quantity if t.side=="BUY" else -t.quantity)
            total=0.0; unpriced=[]
            for sym,q in qty.items():
                if q<=1e-10: continue
                price=db.scalar(select(MarketBar.close).where(MarketBar.symbol==sym,MarketBar.interval=="1d")
                    .order_by(MarketBar.bar_date.desc()).limit(1))
                if price is None: unpriced.append(sym)
                else: total+=q*price
            cash_rows=db.scalars(select(CashEntry).where(CashEntry.portfolio_id==p.id)).all()
            cash=sum(x.amount for x in cash_rows)
            nav=total+cash
            g=groups.setdefault(p.base_currency,{"currency":p.base_currency,"portfolio_count":0,"market_value":0.0,"cash":0.0,"nav":0.0})
            g["portfolio_count"]+=1;g["market_value"]+=total;g["cash"]+=cash;g["nav"]+=nav
            detail.append({"portfolio_id":p.id,"name":p.name,"base_currency":p.base_currency,"market_value":total,
                "cash":cash,"nav":nav,"unpriced_symbols":unpriced})
        return {"currency_groups":list(groups.values()),"portfolios":detail,
            "note":"Values are consolidated only within matching base currencies. No FX translation; unpriced holdings are excluded from market value and listed."}

@app.get("/api/v1/portfolios/{portfolio_id}/performance/attribution/contribution")
def portfolio_return_contribution(portfolio_id:int):
    """Daily security return contribution, aggregated by sector and asset class using prior-day weights."""
    with Session() as db:
        if not db.get(Portfolio,portfolio_id): raise HTTPException(404,"Portfolio not found")
        txs=db.scalars(select(PortfolioTransaction).where(PortfolioTransaction.portfolio_id==portfolio_id)
            .order_by(PortfolioTransaction.trade_date,PortfolioTransaction.id)).all()
        symbols=sorted({t.symbol for t in txs})
        if not symbols: raise HTTPException(422,"No transaction history")
        bars=db.scalars(select(MarketBar).where(MarketBar.symbol.in_(symbols),MarketBar.interval=="1d")
            .order_by(MarketBar.bar_date)).all()
        price={s:{} for s in symbols}
        for b in bars: price[b.symbol][b.bar_date]=b.close
        dates=sorted(set().union(*(set(x.keys()) for x in price.values())))
        instruments={x.symbol:x for x in db.scalars(select(Instrument).where(Instrument.symbol.in_(symbols))).all()}
        q={s:0.0 for s in symbols}; ti=0; by_sector={};by_asset={}; daily=[]
        for idx,d in enumerate(dates):
            if idx==0:
                while ti<len(txs) and txs[ti].trade_date<=d:
                    t=txs[ti];q[t.symbol]+=t.quantity if t.side=="BUY" else -t.quantity;ti+=1
                continue
            prev=dates[idx-1]
            while ti<len(txs) and txs[ti].trade_date<=prev:
                t=txs[ti];q[t.symbol]+=t.quantity if t.side=="BUY" else -t.quantity;ti+=1
            denom=0.0; rows=[]
            for s in symbols:
                if prev not in price[s] or d not in price[s]: continue
                prev_val=q[s]*price[s][prev]
                if prev_val<=0: continue
                ret=price[s][d]/price[s][prev]-1
                rows.append((s,prev_val,ret))
                denom+=prev_val
            if denom<=0: continue
            ds={}; da={}; total=0.0
            for s,v,r in rows:
                contrib=(v/denom)*r; total+=contrib
                inst=instruments.get(s); sector=inst.sector if inst else "UNKNOWN"
                asset=inst.instrument_type if inst else "EQUITY"
                ds[sector]=ds.get(sector,0)+contrib; da[asset]=da.get(asset,0)+contrib
            for k,v in ds.items():by_sector[k]=by_sector.get(k,0)+v
            for k,v in da.items():by_asset[k]=by_asset.get(k,0)+v
            daily.append({"date":d,"portfolio_return_contribution":total,"sector_contribution":ds,"asset_contribution":da})
            while ti<len(txs) and txs[ti].trade_date<=d:
                t=txs[ti];q[t.symbol]+=t.quantity if t.side=="BUY" else -t.quantity;ti+=1
        return {"portfolio_id":portfolio_id,"method":"prior-close market-value weighted security returns; daily contribution series",
            "daily":daily,"cumulative_sector_contribution":by_sector,"cumulative_asset_contribution":by_asset,
            "note":"Approximate contribution. Assumes trades execute at close on trade date; excludes fees, cash yield, FX, corporate actions and securities without matched adjacent daily bars. Contributions are normalized to priced risky holdings, not total NAV."}

@app.get("/api/v1/reports/portfolio-summary")
def institutional_portfolio_report(request:Request):
    data=consolidated_portfolios(request)
    with Session() as db:
        audit_count=db.scalar(select(__import__("sqlalchemy").func.count(AuditEvent.id))) or 0
        ingestion_count=db.scalar(select(__import__("sqlalchemy").func.count(DataIngestion.id))) or 0
    return {"report_type":"institutional_portfolio_summary","generated_at":date.today().isoformat(),
        "consolidated":data,"governance":{"audit_event_count":audit_count,"data_ingestion_jobs":ingestion_count},
        "limitations":"FX is grouped, not translated. This report is not a regulated statement or broker reconciliation."}


# AETHER v1.0 authentication, authorization and integration operations
class BootstrapAdminIn(BaseModel):
    bootstrap_key:str=Field(min_length=16)
    username:str=Field(min_length=3,max_length=80,pattern="^[A-Za-z0-9_.-]+$")
    display_name:str=Field(default="Platform Administrator",max_length=120)
    password:str=Field(min_length=12,max_length=256)

class LoginIn(BaseModel):
    username:str=Field(min_length=3,max_length=80)
    password:str=Field(min_length=1,max_length=256)

class AdminCreateUserIn(BaseModel):
    username:str=Field(min_length=3,max_length=80,pattern="^[A-Za-z0-9_.-]+$")
    display_name:str=Field(default="",max_length=120)
    password:str=Field(min_length=12,max_length=256)

class AdminGrantIn(BaseModel):
    username:str=Field(min_length=3,max_length=80)
    role:str=Field(pattern="^(owner|manager|analyst|trader|viewer)$")

class UserStatusIn(BaseModel):
    status:str=Field(pattern="^(active|disabled)$")

def _require_admin(request:Request):
    if not getattr(request.state,"aether_is_admin",False):
        raise HTTPException(403,"Administrator role required")

@app.post("/api/v1/auth/bootstrap")
def bootstrap_admin(data:BootstrapAdminIn):
    expected=os.getenv("AETHER_BOOTSTRAP_KEY")
    if not expected or not __import__("hmac").compare_digest(expected,data.bootstrap_key):
        raise HTTPException(401,"Invalid bootstrap key")
    from .security.auth import hash_password,create_access_token
    with Session() as db:
        if db.scalar(select(AccessUser.id).where(AccessUser.is_admin==True)) is not None:
            raise HTTPException(409,"Bootstrap is already complete")
        if db.scalar(select(AccessUser).where(AccessUser.username==data.username)):
            raise HTTPException(409,"Username already exists")
        u=AccessUser(username=data.username,display_name=data.display_name,status="active",
                     password_hash=hash_password(data.password),is_admin=True)
        db.add(u);db.commit();db.refresh(u)
        token=create_access_token(u.id,u.username,True)
        db.add(AuditEvent(event_type="security.bootstrap_admin_created",payload={"user_id":u.id,"username":u.username}))
        db.commit()
        return {"access_token":token,"token_type":"bearer","expires_in":3600,"user":{"id":u.id,"username":u.username,"is_admin":True}}

@app.post("/api/v1/auth/login")
def login(data:LoginIn):
    from .security.auth import verify_password,create_access_token
    with Session() as db:
        u=db.scalar(select(AccessUser).where(AccessUser.username==data.username))
        if not u or u.status!="active" or not u.password_hash or not verify_password(data.password,u.password_hash):
            raise HTTPException(401,"Invalid username or password")
        token=create_access_token(u.id,u.username,u.is_admin)
        db.add(AuditEvent(event_type="security.login",payload={"user_id":u.id,"username":u.username}))
        db.commit()
        return {"access_token":token,"token_type":"bearer","expires_in":3600,
                "user":{"id":u.id,"username":u.username,"display_name":u.display_name,"is_admin":u.is_admin}}

@app.get("/api/v1/auth/me")
def auth_me(request:Request):
    with Session() as db:
        u=db.get(AccessUser,request.state.aether_user_id)
        return {"id":u.id,"username":u.username,"display_name":u.display_name,"is_admin":u.is_admin,"status":u.status}

@app.post("/api/v1/admin/users")
def admin_create_user(data:AdminCreateUserIn,request:Request):
    _require_admin(request)
    from .security.auth import hash_password
    with Session() as db:
        if db.scalar(select(AccessUser.id).where(AccessUser.username==data.username)):
            raise HTTPException(409,"Username already exists")
        u=AccessUser(username=data.username,display_name=data.display_name,status="active",
                     password_hash=hash_password(data.password),is_admin=False)
        db.add(u);db.commit();db.refresh(u)
        db.add(AuditEvent(event_type="security.user_created",payload={"user_id":u.id,"username":u.username}))
        db.commit()
        return {"id":u.id,"username":u.username,"display_name":u.display_name,"status":u.status}

@app.post("/api/v1/admin/portfolios/{portfolio_id}/grant")
def admin_grant_portfolio(portfolio_id:int,data:AdminGrantIn,request:Request):
    _require_admin(request)
    with Session() as db:
        if not db.get(Portfolio,portfolio_id):raise HTTPException(404,"Portfolio not found")
        u=db.scalar(select(AccessUser).where(AccessUser.username==data.username))
        if not u:raise HTTPException(404,"User not found")
        row=db.scalar(select(PortfolioAccess).where(PortfolioAccess.portfolio_id==portfolio_id,PortfolioAccess.user_id==u.id))
        if row:row.role=data.role
        else:db.add(PortfolioAccess(portfolio_id=portfolio_id,user_id=u.id,role=data.role))
        db.add(AuditEvent(event_type="security.portfolio_access_granted",payload={"portfolio_id":portfolio_id,"user_id":u.id,"role":data.role}))
        db.commit()
        return {"portfolio_id":portfolio_id,"username":u.username,"role":data.role}

@app.post("/api/v1/admin/users/{username}/status")
def admin_user_status(username:str,data:UserStatusIn,request:Request):
    _require_admin(request)
    with Session() as db:
        u=db.scalar(select(AccessUser).where(AccessUser.username==username))
        if not u:raise HTTPException(404,"User not found")
        if u.id==request.state.aether_user_id and data.status=="disabled":
            raise HTTPException(422,"Administrator cannot disable their own account")
        u.status=data.status
        db.add(AuditEvent(event_type="security.user_status_changed",payload={"username":username,"status":data.status}))
        db.commit()
        return {"username":username,"status":u.status}

@app.get("/api/v1/integrations/status")
def integrations_status(request:Request):
    with Session() as db:
        admin=bool(request.state.aether_is_admin)
    return {"market_data":[
        {"provider":"csv-import","status":"available","live":False},
        {"provider":"licensed-market-data","status":"credentials_required" if not os.getenv("AETHER_MARKET_DATA_PROVIDER") else "adapter_not_installed",
         "live":False,"configured_provider":os.getenv("AETHER_MARKET_DATA_PROVIDER")},
        {"provider":"demo-synthetic","status":"available","live":False}],
        "brokers":[{"provider":x,"status":"credentials_required" if not os.getenv(x+"_CLIENT_ID") or not os.getenv(x+"_CLIENT_SECRET") else "adapter_not_installed",
                    "live":False} for x in ["ZERODHA","UPSTOX","ANGELONE","FYERS"]],
        "security":{"jwt_authentication":True,"portfolio_rbac":True,"shared_api_key_enabled":bool(os.getenv("AETHER_API_KEY")),
                    "admin_bootstrap_configured":bool(os.getenv("AETHER_BOOTSTRAP_KEY"))},
        "note":"No live adapter is enabled in this package. Provider credentials alone do not establish data entitlements or authorize order placement."}

@app.get("/ready")
def readiness():
    try:
        with engine.connect() as conn: conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return {"status":"ready","database":"connected","version":"1.0.0"}
    except Exception as e:
        raise HTTPException(503,"Database readiness check failed")


class ChangePasswordIn(BaseModel):
    current_password:str=Field(min_length=1,max_length=256)
    new_password:str=Field(min_length=12,max_length=256)

@app.post("/api/v1/auth/change-password")
def change_password(data:ChangePasswordIn,request:Request):
    from .security.auth import verify_password,hash_password
    with Session() as db:
        u=db.get(AccessUser,request.state.aether_user_id)
        if not verify_password(data.current_password,u.password_hash):
            raise HTTPException(401,"Current password is incorrect")
        u.password_hash=hash_password(data.new_password)
        db.add(AuditEvent(event_type="security.password_changed",payload={"user_id":u.id}))
        db.commit()
        return {"status":"password_changed","message":"Sign in again using your new password."}

@app.get("/api/v1/admin/users")
def admin_list_users(request:Request):
    _require_admin(request)
    with Session() as db:
        return [{"id":u.id,"username":u.username,"display_name":u.display_name,"status":u.status,"is_admin":u.is_admin}
                for u in db.scalars(select(AccessUser).order_by(AccessUser.id)).all()]

@app.delete("/api/v1/admin/portfolios/{portfolio_id}/users/{username}")
def admin_revoke_portfolio(portfolio_id:int,username:str,request:Request):
    _require_admin(request)
    with Session() as db:
        u=db.scalar(select(AccessUser).where(AccessUser.username==username))
        if not u:raise HTTPException(404,"User not found")
        row=db.scalar(select(PortfolioAccess).where(PortfolioAccess.portfolio_id==portfolio_id,PortfolioAccess.user_id==u.id))
        if not row:raise HTTPException(404,"Grant not found")
        db.delete(row)
        db.add(AuditEvent(event_type="security.portfolio_access_revoked",payload={"portfolio_id":portfolio_id,"user_id":u.id}))
        db.commit()
        return {"status":"revoked","portfolio_id":portfolio_id,"username":username}


# ---------------------------------------------------------------------------
# AETHER AutoTrader v2.0 — paper-only execution. No broker order endpoints.
# Groww integration is read-only for live quotes; real order routing is absent.
# ---------------------------------------------------------------------------
import uuid as _uuid
import math as _math
from datetime import datetime as _datetime, timedelta as _timedelta
from zoneinfo import ZoneInfo as _ZoneInfo

PAPER_INITIAL_CAPITAL = float(os.getenv("AETHER_PAPER_INITIAL_CAPITAL", "50000"))
PAPER_RISK_PER_TRADE = float(os.getenv("AETHER_PAPER_RISK_PER_TRADE", "0.01"))
PAPER_DAILY_LOSS_LIMIT = float(os.getenv("AETHER_PAPER_DAILY_LOSS_LIMIT", "0.02"))
PAPER_MAX_POSITION = float(os.getenv("AETHER_PAPER_MAX_POSITION", "0.25"))
PAPER_MAX_GROSS_EXPOSURE = float(os.getenv("AETHER_PAPER_MAX_GROSS_EXPOSURE", "1.0"))
PAPER_COST_BPS = float(os.getenv("AETHER_PAPER_COST_BPS", "5.0"))
PAPER_SLIPPAGE_BPS = float(os.getenv("AETHER_PAPER_SLIPPAGE_BPS", "2.5"))

class PaperOrderIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    exchange: str = "NSE"
    segment: str = "CASH"
    side: str
    quantity: int = Field(gt=0, le=1000000)
    lot_size: int = Field(default=1, gt=0, le=100000)
    trade_style: str = "INTRADAY"
    reference_price: float = Field(gt=0)
    stop_loss_price: float | None = Field(default=None, gt=0)
    client_order_id: str | None = Field(default=None, max_length=48)

class PaperMarkIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    segment: str = "CASH"
    last_price: float = Field(gt=0)

class StrategyEvaluateIn(BaseModel):
    strategy: str = "trend_following"
    bars: list[dict] = Field(min_length=30, max_length=1000)

def _paper_today():
    return _datetime.now(_ZoneInfo("Asia/Kolkata")).date().isoformat()

def _paper_account(db, user_id: int):
    account = db.scalar(select(PaperAccount).where(PaperAccount.user_id == user_id))
    if not account:
        account = PaperAccount(user_id=user_id, initial_capital=PAPER_INITIAL_CAPITAL,
                               cash_balance=PAPER_INITIAL_CAPITAL, daily_realized_pnl=0.0,
                               daily_pnl_date=_paper_today())
        db.add(account)
        db.flush()
    elif account.daily_pnl_date != _paper_today():
        account.daily_pnl_date = _paper_today()
        account.daily_realized_pnl = 0.0
        db.flush()
    return account

def _paper_positions(db, user_id: int):
    return db.scalars(select(PaperPosition).where(PaperPosition.user_id == user_id)
                      .order_by(PaperPosition.symbol, PaperPosition.segment)).all()

def _paper_summary(db, user_id: int):
    account = _paper_account(db, user_id)
    positions = _paper_positions(db, user_id)
    gross = sum(p.quantity * p.lot_size * p.last_price for p in positions)
    unrealized = sum((p.last_price - p.average_price) * p.quantity * p.lot_size for p in positions)
    equity = account.cash_balance + gross
    return {
        "mode": "PAPER_ONLY", "broker": "GROWW_CONFIGURABLE_READ_ONLY",
        "initial_capital": round(account.initial_capital, 2),
        "cash_balance": round(account.cash_balance, 2),
        "gross_exposure": round(gross, 2), "equity": round(equity, 2),
        "total_unrealized_pnl": round(unrealized, 2),
        "daily_realized_pnl": round(account.daily_realized_pnl, 2),
        "total_pnl": round(equity - account.initial_capital, 2),
        "daily_loss_limit": round(account.initial_capital * PAPER_DAILY_LOSS_LIMIT, 2),
        "risk_per_trade_limit": round(account.initial_capital * PAPER_RISK_PER_TRADE, 2),
        "max_position_notional": round(account.initial_capital * PAPER_MAX_POSITION, 2),
        "positions": [{
            "symbol": p.symbol, "exchange": p.exchange, "segment": p.segment,
            "quantity": p.quantity, "lot_size": p.lot_size,
            "average_price": round(p.average_price, 4), "last_price": round(p.last_price, 4),
            "market_value": round(p.quantity * p.lot_size * p.last_price, 2),
            "unrealized_pnl": round((p.last_price - p.average_price) * p.quantity * p.lot_size, 2),
            "realized_pnl": round(p.realized_pnl, 2)
        } for p in positions],
        "guardrails": {
            "max_risk_per_trade_pct": PAPER_RISK_PER_TRADE * 100,
            "max_daily_realized_loss_pct": PAPER_DAILY_LOSS_LIMIT * 100,
            "max_single_position_pct": PAPER_MAX_POSITION * 100,
            "max_gross_exposure_pct": PAPER_MAX_GROSS_EXPOSURE * 100,
            "fno_short_positions": False,
            "real_orders_enabled": False
        },
        "valuation_note": "Positions are marked at the last paper fill or manually supplied mark. No exchange quote is implied."
    }

@app.get("/api/v1/autotrader/config")
def autotrader_config(request: Request):
    with Session() as db:
        account = _paper_account(db, request.state.aether_user_id)
        db.commit()
        return {
            "mode": "PAPER_ONLY", "broker": "GROWW",
            "initial_capital": account.initial_capital,
            "segments": ["CASH", "FNO"], "styles": ["INTRADAY", "SWING"],
            "real_orders_enabled": False, "live_market_data_enabled": False,
            "risk_limits": {
                "risk_per_trade_pct": PAPER_RISK_PER_TRADE * 100,
                "daily_realized_loss_pct": PAPER_DAILY_LOSS_LIMIT * 100,
                "max_single_position_pct": PAPER_MAX_POSITION * 100,
                "max_gross_exposure_pct": PAPER_MAX_GROSS_EXPOSURE * 100,
                "estimated_cost_bps": PAPER_COST_BPS,
                "slippage_bps": PAPER_SLIPPAGE_BPS
            },
            "message": "Paper trading is enabled. Groww order placement is not present or callable."
        }

@app.get("/api/v1/autotrader/summary")
def autotrader_summary(request: Request):
    with Session() as db:
        result = _paper_summary(db, request.state.aether_user_id)
        db.commit()
        return result

@app.get("/api/v1/autotrader/orders")
def autotrader_orders(request: Request, limit: int = Query(default=100, ge=1, le=500)):
    with Session() as db:
        rows = db.scalars(select(PaperOrder).where(PaperOrder.user_id == request.state.aether_user_id)
                          .order_by(PaperOrder.id.desc()).limit(limit)).all()
        return [{
            "id": o.id, "client_order_id": o.client_order_id, "symbol": o.symbol,
            "exchange": o.exchange, "segment": o.segment, "side": o.side,
            "quantity": o.quantity, "lot_size": o.lot_size, "trade_style": o.trade_style,
            "reference_price": o.reference_price, "fill_price": o.fill_price,
            "stop_loss_price": o.stop_loss_price, "notional": o.notional,
            "estimated_costs": o.estimated_costs, "realized_pnl": o.realized_pnl,
            "status": o.status, "price_source": o.price_source,
            "created_at": o.created_at.isoformat() if o.created_at else None
        } for o in rows]

@app.post("/api/v1/autotrader/orders")
def autotrader_place_paper_order(data: PaperOrderIn, request: Request):
    symbol = data.symbol.strip().upper()
    exchange = data.exchange.strip().upper()
    segment = data.segment.strip().upper()
    side = data.side.strip().upper()
    style = data.trade_style.strip().upper()
    if exchange not in {"NSE", "BSE"}: raise HTTPException(422, "Exchange must be NSE or BSE")
    if segment not in {"CASH", "FNO"}: raise HTTPException(422, "Segment must be CASH or FNO")
    if side not in {"BUY", "SELL"}: raise HTTPException(422, "Side must be BUY or SELL")
    if style not in {"INTRADAY", "SWING"}: raise HTTPException(422, "Trade style must be INTRADAY or SWING")
    if segment == "CASH" and data.lot_size != 1:
        raise HTTPException(422, "Cash equity lot_size must be 1")
    if data.stop_loss_price is not None and side == "BUY" and data.stop_loss_price >= data.reference_price:
        raise HTTPException(422, "For a BUY, stop loss must be below the reference price")
    if side == "BUY" and data.stop_loss_price is None:
        raise HTTPException(422, "A stop-loss price is required for every new long position")
    client_id = data.client_order_id or _uuid.uuid4().hex
    with Session() as db:
        uid = request.state.aether_user_id
        existing = db.scalar(select(PaperOrder).where(PaperOrder.user_id == uid,
                                                       PaperOrder.client_order_id == client_id))
        if existing:
            raise HTTPException(409, "Duplicate client_order_id; order was already recorded")
        account = _paper_account(db, uid)
        if side == "BUY" and account.daily_realized_pnl <= -account.initial_capital * PAPER_DAILY_LOSS_LIMIT:
            raise HTTPException(422, "Daily realized-loss limit reached; new BUY orders are blocked")
        pos = db.scalar(select(PaperPosition).where(PaperPosition.user_id == uid,
            PaperPosition.symbol == symbol, PaperPosition.segment == segment))
        if pos and pos.lot_size != data.lot_size:
            raise HTTPException(422, "Lot size differs from the existing paper position")
        units = data.quantity * data.lot_size
        slip = PAPER_SLIPPAGE_BPS / 10000.0
        fill = data.reference_price * (1 + slip if side == "BUY" else 1 - slip)
        notional = fill * units
        costs = notional * PAPER_COST_BPS / 10000.0
        realized = 0.0
        if side == "BUY":
            risk = (data.reference_price - data.stop_loss_price) * units
            if risk > account.initial_capital * PAPER_RISK_PER_TRADE + 1e-8:
                raise HTTPException(422, f"Trade risk ₹{risk:.2f} exceeds 1% capital risk budget ₹{account.initial_capital * PAPER_RISK_PER_TRADE:.2f}")
            if notional > account.initial_capital * PAPER_MAX_POSITION + 1e-8:
                raise HTTPException(422, "Single order exceeds the 25% capital position limit")
            current_gross = sum(p.quantity * p.lot_size * p.last_price for p in _paper_positions(db, uid))
            if current_gross + notional > account.initial_capital * PAPER_MAX_GROSS_EXPOSURE + 1e-8:
                raise HTTPException(422, "Gross exposure would exceed 100% of paper capital")
            if notional + costs > account.cash_balance + 1e-8:
                raise HTTPException(422, "Insufficient paper cash")
            if not pos:
                pos = PaperPosition(user_id=uid, symbol=symbol, exchange=exchange, segment=segment,
                    quantity=0, lot_size=data.lot_size, average_price=0.0, last_price=fill, realized_pnl=0.0)
                db.add(pos)
            old_units = pos.quantity * pos.lot_size
            new_units = old_units + units
            pos.average_price = ((old_units * pos.average_price) + notional + costs) / new_units
            pos.quantity += data.quantity
            pos.last_price = fill
            account.cash_balance -= (notional + costs)
        else:
            if not pos or pos.quantity < data.quantity:
                raise HTTPException(422, "SELL quantity exceeds the existing long paper position; short selling is disabled")
            realized = (fill - pos.average_price) * units - costs
            pos.quantity -= data.quantity
            pos.last_price = fill
            pos.realized_pnl += realized
            account.daily_realized_pnl += realized
            account.cash_balance += (notional - costs)
            if pos.quantity == 0:
                db.delete(pos)
        order = PaperOrder(user_id=uid, client_order_id=client_id, symbol=symbol, exchange=exchange,
            segment=segment, side=side, quantity=data.quantity, lot_size=data.lot_size,
            trade_style=style, reference_price=data.reference_price, fill_price=fill,
            stop_loss_price=data.stop_loss_price or 0.0, notional=notional,
            estimated_costs=costs, realized_pnl=realized, status="FILLED",
            price_source="MANUAL_REFERENCE")
        db.add(order)
        db.add(AuditEvent(event_type="autotrader.paper_order_filled",
            payload={"user_id": uid, "symbol": symbol, "segment": segment, "side": side,
                     "quantity": data.quantity, "fill_price": round(fill, 6),
                     "client_order_id": client_id, "real_orders_enabled": False}))
        db.commit()
        db.refresh(order)
        return {"status": "FILLED", "mode": "PAPER_ONLY", "order_id": order.id,
                "client_order_id": client_id, "symbol": symbol, "segment": segment,
                "side": side, "quantity": data.quantity, "lot_size": data.lot_size,
                "reference_price": data.reference_price, "fill_price": round(fill, 6),
                "notional": round(notional, 2), "estimated_costs": round(costs, 2),
                "realized_pnl": round(realized, 2), "real_orders_enabled": False,
                "note": "Simulated fill only; no Groww order was submitted."}

@app.post("/api/v1/autotrader/mark")
def autotrader_mark_position(data: PaperMarkIn, request: Request):
    symbol = data.symbol.strip().upper()
    segment = data.segment.strip().upper()
    if segment not in {"CASH", "FNO"}: raise HTTPException(422, "Segment must be CASH or FNO")
    with Session() as db:
        pos = db.scalar(select(PaperPosition).where(PaperPosition.user_id == request.state.aether_user_id,
            PaperPosition.symbol == symbol, PaperPosition.segment == segment))
        if not pos: raise HTTPException(404, "Paper position not found")
        pos.last_price = data.last_price
        db.commit()
        return {"status": "marked", "symbol": symbol, "segment": segment,
                "last_price": data.last_price, "source": "MANUAL_REFERENCE"}

@app.post("/api/v1/autotrader/reset")
def autotrader_reset(request: Request, confirm: bool = Query(default=False)):
    if not confirm: raise HTTPException(422, "Pass confirm=true to reset this paper account")
    with Session() as db:
        uid = request.state.aether_user_id
        account = _paper_account(db, uid)
        db.query(PaperOrder).filter(PaperOrder.user_id == uid).delete(synchronize_session=False)
        db.query(PaperPosition).filter(PaperPosition.user_id == uid).delete(synchronize_session=False)
        account.initial_capital = PAPER_INITIAL_CAPITAL
        account.cash_balance = PAPER_INITIAL_CAPITAL
        account.daily_realized_pnl = 0.0
        account.daily_pnl_date = _paper_today()
        db.add(AuditEvent(event_type="autotrader.paper_account_reset",
            payload={"user_id": uid, "capital": PAPER_INITIAL_CAPITAL}))
        db.commit()
        return {"status": "reset", "initial_capital": PAPER_INITIAL_CAPITAL, "mode": "PAPER_ONLY"}

def _ema(values, period):
    alpha = 2.0 / (period + 1.0)
    out = [values[0]]
    for value in values[1:]:
        out.append(alpha * value + (1.0 - alpha) * out[-1])
    return out

def _rsi(values, period=14):
    changes = [values[i] - values[i-1] for i in range(1, len(values))]
    gains = [max(x, 0.0) for x in changes[-period:]]
    losses = [max(-x, 0.0) for x in changes[-period:]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0: return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

@app.post("/api/v1/autotrader/signals/evaluate")
def autotrader_evaluate_signal(data: StrategyEvaluateIn, request: Request):
    strategy = data.strategy.strip().lower()
    if strategy not in {"trend_following", "breakout", "swing_trend", "mean_reversion"}:
        raise HTTPException(422, "Unknown strategy")
    try:
        closes = [float(x["close"]) for x in data.bars]
        highs = [float(x["high"]) for x in data.bars]
        volumes = [float(x.get("volume", 0)) for x in data.bars]
        if any(not _math.isfinite(x) or x <= 0 for x in closes + highs):
            raise ValueError("OHLC values must be finite and positive")
        if len(closes) < 30: raise ValueError("At least 30 bars are required")
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(422, f"Invalid bars: {exc}")
    rsi = _rsi(closes)
    ema9, ema21, ema50 = _ema(closes, 9)[-1], _ema(closes, 21)[-1], _ema(closes, 50)[-1]
    signal, reasons, confidence = "HOLD", [], 0.50
    if strategy == "trend_following":
        if ema9 > ema21 and closes[-1] > ema21 and 45 <= rsi <= 72:
            signal, confidence = "BUY", 0.62
            reasons.append("EMA 9 above EMA 21; close above EMA 21; RSI confirms positive momentum")
        elif ema9 < ema21 and closes[-1] < ema21:
            signal, confidence = "EXIT_OR_AVOID", 0.62
            reasons.append("Short-term trend is below EMA 21")
        else: reasons.append("Trend confirmation is incomplete")
    elif strategy == "swing_trend":
        if closes[-1] > ema21 > ema50 and 50 <= rsi <= 72:
            signal, confidence = "BUY", 0.65
            reasons.append("Close above EMA 21 above EMA 50 with positive RSI")
        else: reasons.append("Swing trend filter is not fully satisfied")
    elif strategy == "breakout":
        prior_high = max(highs[-21:-1])
        avg_volume = sum(volumes[-21:-1]) / 20.0
        if closes[-1] > prior_high and (avg_volume <= 0 or volumes[-1] >= 1.2 * avg_volume):
            signal, confidence = "BUY", 0.64
            reasons.append("Close broke the prior 20-bar high with volume confirmation")
        else: reasons.append("No confirmed 20-bar breakout")
    else:
        if rsi <= 30:
            signal, confidence = "BUY", 0.58
            reasons.append("RSI is at or below 30; mean-reversion candidate only")
        elif rsi >= 70:
            signal, confidence = "EXIT_OR_AVOID", 0.58
            reasons.append("RSI is at or above 70")
        else: reasons.append("RSI is not at an extreme")
    return {"strategy": strategy, "signal": signal, "confidence_heuristic": confidence,
            "rsi_14": round(rsi, 2), "ema_9": round(ema9, 4), "ema_21": round(ema21, 4),
            "ema_50": round(ema50, 4), "bar_count": len(closes), "reasons": reasons,
            "execution": "DISABLED_PAPER_ONLY",
            "warning": "Heuristic research signal, not a validated predictive model or a recommendation."}

@app.get("/api/v1/groww/status")
def groww_readonly_status(request: Request):
    import importlib.util
    token_set = bool(os.getenv("GROWW_ACCESS_TOKEN"))
    sdk_installed = importlib.util.find_spec("growwapi") is not None
    return {"provider": "Groww", "credentials_configured": token_set,
            "sdk_installed": sdk_installed, "market_data_mode": "READ_ONLY",
            "live_quotes_available": bool(token_set and sdk_installed),
            "order_execution": "DISABLED_IN_THIS_BUILD",
            "note": "Set GROWW_ACCESS_TOKEN on the backend and install growwapi to request read-only quotes. Access tokens expire daily at 06:00 IST; never send tokens from the browser."}

class GrowwLTPIn(BaseModel):
    exchange: str = "NSE"
    segment: str = "CASH"
    exchange_token: str = Field(min_length=1, max_length=40)

@app.post("/api/v1/groww/ltp")
def groww_readonly_ltp(data: GrowwLTPIn, request: Request):
    token = os.getenv("GROWW_ACCESS_TOKEN")
    if not token: raise HTTPException(409, "GROWW_ACCESS_TOKEN is not configured on the backend")
    if data.exchange not in {"NSE", "BSE"} or data.segment not in {"CASH", "FNO"}:
        raise HTTPException(422, "Use NSE/BSE and CASH/FNO")
    try:
        from growwapi import GrowwAPI, GrowwFeed
        client = GrowwAPI(token)
        feed = GrowwFeed(client)
        instruments = [{"exchange": data.exchange, "segment": data.segment,
                        "exchange_token": data.exchange_token}]
        feed.subscribe_ltp(instruments)
        payload = feed.get_ltp()
        feed.unsubscribe_ltp(instruments)
        item = payload.get("ltp", {}).get(data.exchange, {}).get(data.segment, {}).get(data.exchange_token)
        if not item: raise HTTPException(502, "Groww feed returned no LTP for this instrument token")
        return {"provider": "Groww", "exchange": data.exchange, "segment": data.segment,
                "exchange_token": data.exchange_token, "ltp": item.get("ltp"),
                "timestamp_ms": item.get("tsInMillis"), "mode": "READ_ONLY"}
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(503, "Install the optional Groww SDK with: pip install growwapi")
    except Exception as exc:
        raise HTTPException(502, f"Groww read-only quote request failed: {type(exc).__name__}")



# ---------------------------------------------------------------------------
# AETHER v2.1 — Groww API connection and gated live automation.
# Live order routing is OFF unless explicit server-side approvals are set.
# ---------------------------------------------------------------------------
import json as _json
import httpx as _httpx
from urllib.parse import urlencode as _urlencode
from cryptography.fernet import Fernet as _Fernet, InvalidToken as _InvalidFernetToken

GROWW_API_BASE = "https://api.groww.in"
LIVE_CAPITAL = float(os.getenv("AETHER_LIVE_CAPITAL", "50000"))
LIVE_RISK_PER_TRADE = float(os.getenv("AETHER_LIVE_RISK_PER_TRADE", "0.01"))
LIVE_MAX_ORDER_VALUE = float(os.getenv("AETHER_LIVE_MAX_ORDER_VALUE", "12500"))
LIVE_MAX_DAILY_ORDERS = int(os.getenv("AETHER_LIVE_MAX_DAILY_ORDERS", "5"))
LIVE_MAX_DAILY_NOTIONAL = float(os.getenv("AETHER_LIVE_MAX_DAILY_NOTIONAL", "50000"))

class GrowwConnectIn(BaseModel):
    access_token: str = Field(min_length=20, max_length=4096)

class LiveArmIn(BaseModel):
    confirmation: str

class AutoStrategyIn(BaseModel):
    name: str = Field(default="AETHER strategy", min_length=1, max_length=80)
    symbol: str = Field(min_length=1, max_length=64)
    groww_symbol: str = Field(min_length=3, max_length=100)
    exchange: str = "NSE"
    segment: str = "CASH"
    candle_interval: str = "5minute"
    strategy: str = "trend_following"
    lot_size: int = Field(default=1, gt=0, le=100000)
    product: str = "MIS"
    max_order_value: float = Field(default=10000, gt=0, le=12500)
    stop_loss_pct: float = Field(default=0.02, gt=0.001, le=0.10)
    target_pct: float = Field(default=0.04, gt=0.002, le=0.30)

class LiveOrderIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    exchange: str = "NSE"
    segment: str = "CASH"
    side: str
    quantity: int = Field(gt=0, le=1000000)
    lot_size: int = Field(default=1, gt=0, le=100000)
    product: str
    order_type: str = "LIMIT"
    limit_price: float | None = Field(default=None, gt=0)
    stop_loss_price: float = Field(gt=0)
    source_strategy_id: int | None = None

def _fernet():
    key = os.getenv("GROWW_TOKEN_ENCRYPTION_KEY", "").strip()
    if not key:
        raise HTTPException(409, "Set GROWW_TOKEN_ENCRYPTION_KEY on the backend before connecting Groww")
    try:
        return _Fernet(key.encode())
    except Exception:
        raise HTTPException(500, "GROWW_TOKEN_ENCRYPTION_KEY is invalid; generate a Fernet key")

def _groww_token(db, user_id):
    row = db.scalar(select(GrowwConnection).where(GrowwConnection.user_id == user_id))
    if not row:
        # Optional single-user deployment secret; per-user encrypted connection is preferred.
        return os.getenv("GROWW_ACCESS_TOKEN", "").strip()
    try:
        return _fernet().decrypt(row.encrypted_access_token.encode()).decode()
    except _InvalidFernetToken:
        raise HTTPException(500, "Stored Groww token could not be decrypted; reconnect Groww")
    except HTTPException:
        raise

def _groww_request(token, method, path, params=None, body=None):
    headers = {"Accept": "application/json", "Content-Type": "application/json",
               "Authorization": "Bearer " + token, "X-API-VERSION": "1.0"}
    try:
        with _httpx.Client(timeout=12.0) as client:
            response = client.request(method, GROWW_API_BASE + path, params=params,
                                      json=body, headers=headers)
        data = response.json()
    except Exception as exc:
        raise HTTPException(502, f"Groww API connection failed: {type(exc).__name__}")
    if response.status_code >= 400 or data.get("status") == "FAILURE":
        error = data.get("error", {}) if isinstance(data, dict) else {}
        message = error.get("message") or data.get("message") or "Groww rejected the request"
        raise HTTPException(502, f"Groww API error ({response.status_code}): {message}")
    return data

def _live_state(db, user_id):
    state = db.scalar(select(LiveTradingState).where(LiveTradingState.user_id == user_id))
    if not state:
        state = LiveTradingState(user_id=user_id, armed=False, daily_date=_paper_today(),
                                 daily_order_count=0, daily_notional=0.0)
        db.add(state); db.flush()
    if state.daily_date != _paper_today():
        state.daily_date = _paper_today()
        state.daily_order_count = 0
        state.daily_notional = 0.0
        db.flush()
    return state

def _live_gate(db, user_id):
    if os.getenv("AETHER_LIVE_TRADING_ENABLED", "false").lower() != "true":
        raise HTTPException(423, "Live order routing is disabled by the server kill switch")
    if os.getenv("AETHER_GROWW_ALGO_APPROVED", "false").lower() != "true":
        raise HTTPException(423, "Broker/exchange algo approval is not confirmed in server configuration")
    state = _live_state(db, user_id)
    if not state.armed:
        raise HTTPException(423, "Live trading is not armed by the user")
    token = _groww_token(db, user_id)
    if not token:
        raise HTTPException(409, "Connect Groww API credentials first")
    return state, token

def _live_positions(token, segment):
    data = _groww_request(token, "GET", "/v1/positions/user", params={"segment": segment})
    return data.get("payload", {}).get("positions", [])

def _live_order(token, symbol, exchange, segment, side, quantity, product,
                order_type, reference_id, price=None):
    body = {
        "trading_symbol": symbol, "quantity": int(quantity), "validity": "DAY",
        "exchange": exchange, "segment": segment, "product": product,
        "order_type": order_type, "transaction_type": side,
        "order_reference_id": reference_id
    }
    if price is not None:
        body["price"] = round(float(price), 2)
    return _groww_request(token, "POST", "/v1/order/create", body=body)

@app.post("/api/v1/groww/connect")
def groww_connect(data: GrowwConnectIn, request: Request):
    if request.url.scheme != "https" and os.getenv("AETHER_ALLOW_INSECURE_GROWW_CONNECT", "false").lower() != "true":
        raise HTTPException(400, "Connect Groww only over HTTPS. For local-only testing, explicitly set AETHER_ALLOW_INSECURE_GROWW_CONNECT=true.")
    cipher = _fernet()
    encrypted = cipher.encrypt(data.access_token.strip().encode()).decode()
    with Session() as db:
        uid = request.state.aether_user_id
        row = db.scalar(select(GrowwConnection).where(GrowwConnection.user_id == uid))
        if row:
            row.encrypted_access_token = encrypted
            row.connected_at = _datetime.now(_ZoneInfo("Asia/Kolkata"))
        else:
            db.add(GrowwConnection(user_id=uid, encrypted_access_token=encrypted))
        state = _live_state(db, uid)
        state.armed = False
        db.add(AuditEvent(event_type="groww.api_connected", payload={"user_id": uid, "token_stored_encrypted": True}))
        db.commit()
    return {"connected": True, "credential_storage": "encrypted_server_database",
            "live_trading_armed": False,
            "note": "Groww API token stored encrypted. Tokens generated through Groww access-token flow expire daily at 06:00 IST."}

@app.post("/api/v1/groww/disconnect")
def groww_disconnect(request: Request):
    with Session() as db:
        uid = request.state.aether_user_id
        state = _live_state(db, uid); state.armed = False
        row = db.scalar(select(GrowwConnection).where(GrowwConnection.user_id == uid))
        if row: db.delete(row)
        db.add(AuditEvent(event_type="groww.api_disconnected", payload={"user_id": uid}))
        db.commit()
    return {"connected": False, "live_trading_armed": False}

@app.get("/api/v1/groww/connection")
def groww_connection_status(request: Request):
    with Session() as db:
        uid = request.state.aether_user_id
        row = db.scalar(select(GrowwConnection).where(GrowwConnection.user_id == uid))
        state = _live_state(db, uid)
        db.commit()
        return {"connected": bool(row or os.getenv("GROWW_ACCESS_TOKEN")),
                "live_trading_armed": bool(state.armed),
                "server_live_switch": os.getenv("AETHER_LIVE_TRADING_ENABLED", "false").lower() == "true",
                "algo_approval_flag": os.getenv("AETHER_GROWW_ALGO_APPROVED", "false").lower() == "true",
                "auto_worker_enabled": os.getenv("AETHER_AUTO_WORKER_ENABLED", "false").lower() == "true",
                "note": "Groww API connection is not an OAuth login. User supplies a Groww-generated API access token; no Groww password or OTP is collected."}

@app.post("/api/v1/groww/live/enable")
def groww_live_enable(data: LiveArmIn, request: Request):
    if data.confirmation != "I UNDERSTAND LIVE TRADING":
        raise HTTPException(422, "Exact confirmation phrase required")
    with Session() as db:
        uid = request.state.aether_user_id
        if os.getenv("AETHER_LIVE_TRADING_ENABLED", "false").lower() != "true":
            raise HTTPException(423, "Server live-trading kill switch is OFF")
        if os.getenv("AETHER_GROWW_ALGO_APPROVED", "false").lower() != "true":
            raise HTTPException(423, "Set approval only after Groww confirms your API/algo setup and applicable exchange requirements")
        if not _groww_token(db, uid):
            raise HTTPException(409, "Connect Groww first")
        state = _live_state(db, uid); state.armed = True
        state.armed_at = _datetime.now(_ZoneInfo("Asia/Kolkata"))
        db.add(AuditEvent(event_type="groww.live_trading_armed", payload={"user_id": uid, "capital_limit": LIVE_CAPITAL}))
        db.commit()
        return {"live_trading_armed": True, "capital_limit": LIVE_CAPITAL,
                "max_order_value": LIVE_MAX_ORDER_VALUE, "max_daily_orders": LIVE_MAX_DAILY_ORDERS}

@app.post("/api/v1/groww/live/disable")
def groww_live_disable(request: Request):
    with Session() as db:
        state = _live_state(db, request.state.aether_user_id)
        state.armed = False
        db.add(AuditEvent(event_type="groww.live_trading_disarmed", payload={"user_id": request.state.aether_user_id}))
        db.commit()
    return {"live_trading_armed": False, "note": "New AETHER orders are disabled. Existing broker orders and positions are not automatically cancelled or closed."}

@app.post("/api/v1/groww/orders")
def groww_place_live_order(data: LiveOrderIn, request: Request):
    symbol = data.symbol.strip().upper()
    exchange, segment, side = data.exchange.upper(), data.segment.upper(), data.side.upper()
    product, order_type = data.product.upper(), data.order_type.upper()
    if exchange not in {"NSE", "BSE"} or segment not in {"CASH", "FNO"}:
        raise HTTPException(422, "Exchange must be NSE/BSE and segment CASH/FNO")
    if side not in {"BUY", "SELL"}: raise HTTPException(422, "Side must be BUY or SELL")
    if product not in {"CNC", "MIS", "NRML"}: raise HTTPException(422, "Unsupported Groww product")
    if order_type not in {"LIMIT", "MARKET"}: raise HTTPException(422, "Live AETHER orders currently allow LIMIT or MARKET only")
    if segment == "CASH" and data.lot_size != 1: raise HTTPException(422, "Cash equity lot_size must be 1")
    if segment == "FNO" and data.quantity % data.lot_size != 0:
        raise HTTPException(422, "F&O quantity must be a multiple of the configured lot size")
    if order_type == "LIMIT" and not data.limit_price:
        raise HTTPException(422, "LIMIT orders require limit_price")
    if side == "BUY" and data.stop_loss_price >= (data.limit_price or data.stop_loss_price * 1.01):
        raise HTTPException(422, "BUY stop-loss must be below the entry price")
    ref = _uuid.uuid4().hex[:16]
    notional = data.quantity * (data.limit_price or 0.0)
    if data.limit_price and notional > LIVE_MAX_ORDER_VALUE:
        raise HTTPException(422, f"Order notional exceeds configured ₹{LIVE_MAX_ORDER_VALUE:.0f} cap")
    with Session() as db:
        uid = request.state.aether_user_id
        state, token = _live_gate(db, uid)
        if state.daily_order_count >= LIVE_MAX_DAILY_ORDERS:
            raise HTTPException(423, "Daily live order count limit reached")
        if data.limit_price and state.daily_notional + notional > LIVE_MAX_DAILY_NOTIONAL:
            raise HTTPException(423, "Daily live notional cap would be exceeded")
        # Refuse entries if broker position snapshot is unavailable or already too large.
        positions = _live_positions(token, segment)
        gross = 0.0
        for p in positions:
            try: gross += abs(float(p.get("quantity", 0)) * float(p.get("net_price", 0)))
            except (TypeError, ValueError): pass
        if side == "BUY" and gross + notional > LIVE_CAPITAL:
            raise HTTPException(423, "Broker position snapshot plus this order would exceed ₹50,000 configured gross exposure cap")
        response = _live_order(token, symbol, exchange, segment, side, data.quantity,
                               product, order_type, ref, data.limit_price)
        payload = response.get("payload", {})
        groww_id = str(payload.get("groww_order_id", ""))
        status = str(payload.get("order_status", response.get("status", "SUBMITTED")))
        db.add(LiveBrokerOrder(user_id=uid, client_reference_id=ref, groww_order_id=groww_id,
            symbol=symbol, exchange=exchange, segment=segment, side=side,
            quantity=data.quantity, product=product, order_type=order_type, status=status,
            source_strategy_id=data.source_strategy_id, response_json=_json.dumps(response)))
        state.daily_order_count += 1
        state.daily_notional += notional
        db.add(AuditEvent(event_type="groww.live_order_submitted",
            payload={"user_id": uid, "symbol": symbol, "segment": segment, "side": side,
                     "quantity": data.quantity, "groww_order_id": groww_id, "reference": ref}))
        db.commit()
        return {"submitted": True, "groww_order_id": groww_id, "order_status": status,
                "reference_id": ref, "notional_estimate": notional,
                "warning": "Groww accepted the order request; this does not mean it is filled. Check broker order status."}

@app.get("/api/v1/groww/orders")
def groww_live_orders(request: Request, limit: int = Query(default=100, ge=1, le=500)):
    with Session() as db:
        rows = db.scalars(select(LiveBrokerOrder).where(LiveBrokerOrder.user_id == request.state.aether_user_id)
                          .order_by(LiveBrokerOrder.id.desc()).limit(limit)).all()
        return [{"groww_order_id": x.groww_order_id, "reference_id": x.client_reference_id,
                 "symbol": x.symbol, "exchange": x.exchange, "segment": x.segment,
                 "side": x.side, "quantity": x.quantity, "product": x.product,
                 "status": x.status, "created_at": x.created_at.isoformat() if x.created_at else None}
                for x in rows]

@app.post("/api/v1/autotrader/strategies")
def create_auto_strategy(data: AutoStrategyIn, request: Request):
    exchange, segment = data.exchange.upper(), data.segment.upper()
    product, interval, strategy = data.product.upper(), data.candle_interval, data.strategy.lower()
    if exchange not in {"NSE", "BSE"} or segment not in {"CASH", "FNO"}:
        raise HTTPException(422, "Use NSE/BSE and CASH/FNO")
    if interval not in {"5minute", "15minute", "30minute", "1hour", "1day"}:
        raise HTTPException(422, "Unsupported candle interval")
    if strategy not in {"trend_following", "breakout", "swing_trend", "mean_reversion"}:
        raise HTTPException(422, "Unsupported strategy")
    if product not in {"CNC", "MIS", "NRML"}: raise HTTPException(422, "Unsupported Groww product")
    if segment == "CASH" and data.lot_size != 1: raise HTTPException(422, "Cash lot size must be 1")
    if data.max_order_value > LIVE_MAX_ORDER_VALUE: raise HTTPException(422, "Strategy order value exceeds ₹12,500 cap")
    if data.max_order_value * data.stop_loss_pct > LIVE_CAPITAL * LIVE_RISK_PER_TRADE + 1e-6:
        raise HTTPException(422, "Configured stop-loss risk exceeds ₹500 (1% of ₹50,000)")
    if segment == "FNO" and product == "CNC": raise HTTPException(422, "F&O cannot use CNC product")
    with Session() as db:
        uid = request.state.aether_user_id
        row = AutoStrategyConfig(user_id=uid, name=data.name, symbol=data.symbol.strip().upper(),
            groww_symbol=data.groww_symbol.strip(), exchange=exchange, segment=segment,
            candle_interval=interval, strategy=strategy, lot_size=data.lot_size,
            product=product, max_order_value=data.max_order_value,
            stop_loss_pct=data.stop_loss_pct, target_pct=data.target_pct, enabled=False)
        db.add(row); db.commit(); db.refresh(row)
        return {"id": row.id, "enabled": False, "symbol": row.symbol,
                "note": "Strategy saved disabled. It will not trade until server approvals, Groww connection and user live-arm are all active."}

@app.get("/api/v1/autotrader/strategies")
def list_auto_strategies(request: Request):
    with Session() as db:
        rows = db.scalars(select(AutoStrategyConfig).where(AutoStrategyConfig.user_id == request.state.aether_user_id)
                          .order_by(AutoStrategyConfig.id.desc())).all()
        return [{"id": x.id, "name": x.name, "symbol": x.symbol, "groww_symbol": x.groww_symbol,
                 "exchange": x.exchange, "segment": x.segment, "interval": x.candle_interval,
                 "strategy": x.strategy, "lot_size": x.lot_size, "product": x.product,
                 "max_order_value": x.max_order_value, "stop_loss_pct": x.stop_loss_pct,
                 "target_pct": x.target_pct, "enabled": x.enabled}
                for x in rows]

@app.post("/api/v1/autotrader/strategies/{strategy_id}/enable")
def enable_auto_strategy(strategy_id: int, request: Request):
    with Session() as db:
        row = db.scalar(select(AutoStrategyConfig).where(AutoStrategyConfig.id == strategy_id,
            AutoStrategyConfig.user_id == request.state.aether_user_id))
        if not row: raise HTTPException(404, "Strategy not found")
        row.enabled = True; db.commit()
        return {"id": row.id, "enabled": True, "note": "Strategy is scheduled, but execution remains gated by live-trading approvals and the user's live-arm."}

@app.post("/api/v1/autotrader/strategies/{strategy_id}/disable")
def disable_auto_strategy(strategy_id: int, request: Request):
    with Session() as db:
        row = db.scalar(select(AutoStrategyConfig).where(AutoStrategyConfig.id == strategy_id,
            AutoStrategyConfig.user_id == request.state.aether_user_id))
        if not row: raise HTTPException(404, "Strategy not found")
        row.enabled = False; db.commit()
        return {"id": row.id, "enabled": False}

@app.delete("/api/v1/autotrader/strategies/{strategy_id}")
def delete_auto_strategy(strategy_id: int, request: Request):
    with Session() as db:
        row = db.scalar(select(AutoStrategyConfig).where(AutoStrategyConfig.id == strategy_id,
            AutoStrategyConfig.user_id == request.state.aether_user_id))
        if not row: raise HTTPException(404, "Strategy not found")
        row.enabled = False; db.delete(row); db.commit()
        return {"deleted": True}

def _worker_eval(strategy, bars):
    def field(bar, key, idx):
        return float(bar[idx] if isinstance(bar, (list, tuple)) else bar[key])
    closes=[field(b, "close", 4) for b in bars]
    highs=[field(b, "high", 2) for b in bars]
    volumes=[float(b[5] if isinstance(b, (list,tuple)) else b.get("volume",0)) for b in bars]
    if len(closes) < 50: return "HOLD", closes[-1], "Not enough bars"
    rsi=_rsi(closes)
    ema9,ema21,ema50=_ema(closes,9)[-1],_ema(closes,21)[-1],_ema(closes,50)[-1]
    if strategy=="trend_following":
        return ("BUY" if ema9>ema21 and closes[-1]>ema21 and 45<=rsi<=72 else
                "EXIT_OR_AVOID" if ema9<ema21 and closes[-1]<ema21 else "HOLD", closes[-1], "EMA/RSI trend filter")
    if strategy=="swing_trend":
        return ("BUY" if closes[-1]>ema21>ema50 and 50<=rsi<=72 else
                "EXIT_OR_AVOID" if closes[-1]<ema50 else "HOLD", closes[-1], "EMA 21/50 swing filter")
    if strategy=="breakout":
        prior=max(highs[-21:-1])
        avg=sum(volumes[-21:-1])/20
        return ("BUY" if closes[-1]>prior and (avg<=0 or volumes[-1]>=1.2*avg) else "HOLD",
                closes[-1], "20-bar breakout and volume filter")
    return ("BUY" if rsi<=30 else "EXIT_OR_AVOID" if rsi>=70 else "HOLD",
            closes[-1], "RSI mean-reversion filter")

def run_auto_scan_once():
    if os.getenv("AETHER_AUTO_WORKER_ENABLED", "false").lower() != "true":
        return {"scanned": 0, "reason": "AETHER_AUTO_WORKER_ENABLED is false"}
    if os.getenv("AETHER_LIVE_TRADING_ENABLED", "false").lower() != "true" or os.getenv("AETHER_GROWW_ALGO_APPROVED", "false").lower() != "true":
        return {"scanned": 0, "reason": "Live server gate or broker approval flag is false"}
    now=_datetime.now(_ZoneInfo("Asia/Kolkata"))
    if now.weekday()>=5 or (now.hour,now.minute)<(9,20) or (now.hour,now.minute)>(15,20):
        return {"scanned": 0, "reason": "Outside configured NSE regular-session window"}
    results=[]
    with Session() as db:
        configs=db.scalars(select(AutoStrategyConfig).where(AutoStrategyConfig.enabled == True)).all()
        for cfg in configs:
            try:
                state=_live_state(db,cfg.user_id)
                if not state.armed: continue
                token=_groww_token(db,cfg.user_id)
                if not token: continue
                end=now.strftime("%Y-%m-%d %H:%M:%S")
                days=10 if cfg.candle_interval in {"5minute","15minute","30minute","1hour"} else 180
                start=(now-_timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
                hist=_groww_request(token,"GET","/v1/historical/candles",params={
                    "exchange":cfg.exchange,"segment":cfg.segment,"groww_symbol":cfg.groww_symbol,
                    "start_time":start,"end_time":end,"candle_interval":cfg.candle_interval})
                candles=hist.get("payload",{}).get("candles",[])
                if len(candles)<50: continue
                signal, close, reason=_worker_eval(cfg.strategy,candles)
                q=_groww_request(token,"GET","/v1/live-data/quote",params={
                    "exchange":cfg.exchange,"segment":cfg.segment,"trading_symbol":cfg.symbol})
                ltp=float(q.get("payload",{}).get("last_price") or close)
                # Reconcile a previously submitted order before considering another order.
                if cfg.pending_order_id:
                    try:
                        detail=_groww_request(token,"GET",f"/v1/order/detail/{cfg.pending_order_id}",
                                              params={"segment":cfg.segment})
                        order_payload=detail.get("payload",{})
                        order_status=str(order_payload.get("order_status","")).upper()
                        if order_status in {"REJECTED","FAILED","CANCELLED"}:
                            if cfg.pending_order_side=="BUY":
                                cfg.open_quantity=0; cfg.entry_price=0.0
                            cfg.pending_order_id=""; cfg.pending_order_side=""; cfg.pending_reference_id=""
                        elif order_status in {"EXECUTED","COMPLETED","DELIVERY_AWAITED"}:
                            if cfg.pending_order_side=="SELL":
                                cfg.open_quantity=0; cfg.entry_price=0.0
                                cfg.smart_order_id=""; cfg.smart_order_type=""
                            cfg.pending_order_id=""; cfg.pending_order_side=""; cfg.pending_reference_id=""
                    except Exception:
                        # Unknown order status: never submit a duplicate.
                        continue
                positions=_live_positions(token,cfg.segment)
                all_positions=_live_positions(token,"CASH")+_live_positions(token,"FNO")
                pos=next((p for p in positions if p.get("trading_symbol")==cfg.symbol and p.get("exchange")==cfg.exchange),None)
                net_qty=int((pos or {}).get("quantity",0) or 0)
                if cfg.open_quantity>0 and net_qty==0 and not cfg.pending_order_id:
                    cfg.open_quantity=0; cfg.entry_price=0.0
                    cfg.smart_order_id=""; cfg.smart_order_type=""
                # Only manage the quantity recorded as opened by this AETHER strategy.
                if cfg.open_quantity>0 and net_qty>0:
                    if ltp <= cfg.entry_price*(1-cfg.stop_loss_pct) or ltp >= cfg.entry_price*(1+cfg.target_pct) or signal=="EXIT_OR_AVOID":
                        qty=min(cfg.open_quantity,abs(net_qty))
                        if qty>0:
                            if cfg.smart_order_id:
                                try:
                                    _groww_request(token,"POST",f"/v1/order-advance/cancel/{cfg.segment}/{cfg.smart_order_type}/{cfg.smart_order_id}")
                                except Exception:
                                    results.append({"strategy_id":cfg.id,"action":"EXIT_HELD","reason":"Could not cancel protective smart order"})
                                    continue
                            ref=cfg.pending_reference_id or _uuid.uuid4().hex[:16]
                            cfg.pending_reference_id=ref
                            cfg.pending_order_side="SELL"
                            db.commit()
                            # Limit exit near the current LTP to bound execution price; may remain unfilled.
                            px=ltp*0.999
                            r=_live_order(token,cfg.symbol,cfg.exchange,cfg.segment,"SELL",qty,cfg.product,"LIMIT",ref,px)
                            payload=r.get("payload",{})
                            db.add(LiveBrokerOrder(user_id=cfg.user_id,client_reference_id=ref,
                                groww_order_id=str(payload.get("groww_order_id","")),symbol=cfg.symbol,
                                exchange=cfg.exchange,segment=cfg.segment,side="SELL",quantity=qty,
                                product=cfg.product,order_type="LIMIT",status=str(payload.get("order_status","SUBMITTED")),
                                source_strategy_id=cfg.id,response_json=_json.dumps(r)))
                            cfg.pending_order_id=str(payload.get("groww_order_id",""))
                            cfg.pending_order_side="SELL"
                            cfg.smart_order_id=""; cfg.smart_order_type=""
                            results.append({"strategy_id":cfg.id,"action":"EXIT_SUBMITTED","symbol":cfg.symbol})
                    elif not cfg.smart_order_id and net_qty>=cfg.open_quantity:
                        # Broker-native protective order: OCO where supported, otherwise GTT stop.
                        smart_ref=_uuid.uuid4().hex[:16]
                        stop=cfg.entry_price*(1-cfg.stop_loss_pct)
                        target=cfg.entry_price*(1+cfg.target_pct)
                        if (cfg.segment=="CASH" and cfg.product=="MIS") or (cfg.segment=="FNO" and cfg.product=="NRML"):
                            body={"reference_id":smart_ref,"smart_order_type":"OCO","segment":cfg.segment,
                                  "trading_symbol":cfg.symbol,"quantity":cfg.open_quantity,
                                  "net_position_quantity":net_qty,"transaction_type":"SELL",
                                  "target":{"trigger_price":f"{target:.2f}","order_type":"LIMIT","price":f"{target*0.999:.2f}"},
                                  "stop_loss":{"trigger_price":f"{stop:.2f}","order_type":"SL_M","price":None},
                                  "product_type":cfg.product,"exchange":cfg.exchange,"duration":"DAY"}
                            typ="OCO"
                        else:
                            body={"reference_id":smart_ref,"smart_order_type":"GTT","segment":cfg.segment,
                                  "trading_symbol":cfg.symbol,"quantity":cfg.open_quantity,
                                  "trigger_price":f"{stop:.2f}","trigger_direction":"DOWN",
                                  "order":{"order_type":"MARKET","transaction_type":"SELL"},
                                  "product_type":cfg.product,"exchange":cfg.exchange,"duration":"DAY"}
                            typ="GTT"
                        smart=_groww_request(token,"POST","/v1/order-advance/create",body=body)
                        cfg.smart_order_id=str(smart.get("payload",{}).get("smart_order_id",""))
                        cfg.smart_order_type=typ
                        results.append({"strategy_id":cfg.id,"action":"PROTECTION_SUBMITTED","type":typ,"symbol":cfg.symbol})
                elif cfg.open_quantity==0 and not cfg.pending_order_id and signal=="BUY":
                    # Do not pyramid into a pre-existing broker position.
                    if net_qty != 0: continue
                    risk_budget=LIVE_CAPITAL*LIVE_RISK_PER_TRADE
                    per_unit_risk=ltp*cfg.stop_loss_pct
                    raw_qty=min(cfg.max_order_value/ltp,risk_budget/per_unit_risk)
                    qty=int(raw_qty//cfg.lot_size)*cfg.lot_size
                    if qty<=0: continue
                    notional=qty*ltp
                    if notional>LIVE_MAX_ORDER_VALUE or state.daily_order_count>=LIVE_MAX_DAILY_ORDERS:
                        continue
                    if state.daily_notional+notional>LIVE_MAX_DAILY_NOTIONAL: continue
                    gross=sum(abs(float(p.get("quantity",0) or 0)*float(p.get("net_price",0) or 0)) for p in all_positions)
                    if gross+notional>LIVE_CAPITAL: continue
                    ref=cfg.pending_reference_id or _uuid.uuid4().hex[:16]
                    cfg.pending_reference_id=ref
                    cfg.pending_order_side="BUY"
                    cfg.entry_price=ltp
                    cfg.open_quantity=qty
                    db.commit()
                    # Small marketable limit buffer; avoids unbounded market-order slippage.
                    px=ltp*1.001
                    product=cfg.product
                    r=_live_order(token,cfg.symbol,cfg.exchange,cfg.segment,"BUY",qty,product,"LIMIT",ref,px)
                    payload=r.get("payload",{})
                    groww_id=str(payload.get("groww_order_id",""))
                    cfg.pending_order_id=groww_id
                    cfg.pending_order_side="BUY"
                    cfg.entry_price=ltp
                    cfg.open_quantity=qty
                    state.daily_order_count+=1; state.daily_notional+=notional
                    db.add(LiveBrokerOrder(user_id=cfg.user_id,client_reference_id=ref,
                        groww_order_id=groww_id,symbol=cfg.symbol,exchange=cfg.exchange,
                        segment=cfg.segment,side="BUY",quantity=qty,product=product,
                        order_type="LIMIT",status=str(payload.get("order_status","SUBMITTED")),
                        source_strategy_id=cfg.id,response_json=_json.dumps(r)))
                    results.append({"strategy_id":cfg.id,"action":"ENTRY_SUBMITTED","symbol":cfg.symbol,"quantity":qty})
                cfg.last_run_at=now
            except Exception as exc:
                results.append({"strategy_id":cfg.id,"error":type(exc).__name__})
        db.commit()
    return {"scanned":len(results),"results":results}

@app.post("/api/v1/autotrader/worker/scan-once")
def auto_worker_scan_once(request: Request):
    if not request.state.aether_is_admin:
        raise HTTPException(403, "Admin access required to trigger the shared worker scan")
    with Session() as db:
        state=_live_state(db,request.state.aether_user_id)
        if not state.armed: raise HTTPException(423,"Arm live trading before a scan")
    return run_auto_scan_once()


# AETHER v3.0 Adaptive Quant Research — strictly research-only endpoints.
@app.post("/api/v1/research/adaptive-signal")
def research_adaptive_signal(payload: dict):
    try:
        return adaptive_signal(
            payload.get("closes", []), payload.get("highs"), payload.get("lows"),
            payload.get("volumes"), float(payload.get("min_confidence", 0.60)),
            bool(payload.get("allow_short", True)))
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc))

@app.post("/api/v1/research/walk-forward")
def research_walk_forward(payload: dict):
    try:
        return validate_walk_forward(
            payload.get("closes", []), payload.get("highs"), payload.get("lows"),
            payload.get("volumes"), int(payload.get("train_window", 120)),
            float(payload.get("cost_bps_per_turnover", 15.0)),
            float(payload.get("min_confidence", 0.60)),
            bool(payload.get("allow_short", True)),
            int(payload.get("bootstrap_iterations", 1000)))
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc))


# AETHER v3.1 historical-data research endpoints (research only; never place orders).
from .engines.research_v31 import parse_ohlcv_csv, india_cost_estimate, cash_equity_backtest, futures_contract_pnl, research_gate

@app.post("/api/v1/research/v31/import-csv")
def research_v31_import_csv(payload: dict):
    try: return parse_ohlcv_csv(payload.get("csv_text", ""))
    except (ValueError, TypeError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/estimate-costs")
def research_v31_costs(payload: dict):
    try: return india_cost_estimate(float(payload["notional"]), payload["side"], payload["segment"], payload.get("rates", {}))
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/cash-backtest")
def research_v31_cash_backtest(payload: dict):
    try: return cash_equity_backtest(payload["closes"], payload["signals"], float(payload.get("capital",50000)), float(payload.get("costs_per_side",0)))
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/futures-pnl")
def research_v31_futures_pnl(payload: dict):
    try: return futures_contract_pnl(**payload)
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/gate")
def research_v31_gate(payload: dict):
    try: return research_gate(payload["metrics"], int(payload.get("min_trades",30)), float(payload.get("max_drawdown_limit",0.20)))
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))


# AETHER v3.1 historical-data research endpoints (research only; never place orders).
from .engines.research_v31 import parse_ohlcv_csv, india_cost_estimate, cash_equity_backtest, futures_contract_pnl, research_gate

@app.post("/api/v1/research/v31/import-csv")
def research_v31_import_csv(payload: dict):
    try: return parse_ohlcv_csv(payload.get("csv_text", ""))
    except (ValueError, TypeError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/estimate-costs")
def research_v31_costs(payload: dict):
    try: return india_cost_estimate(float(payload["notional"]), payload["side"], payload["segment"], payload.get("rates", {}))
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/cash-backtest")
def research_v31_cash_backtest(payload: dict):
    try: return cash_equity_backtest(payload["closes"], payload["signals"], float(payload.get("capital",50000)), float(payload.get("costs_per_side",0)))
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/futures-pnl")
def research_v31_futures_pnl(payload: dict):
    try: return futures_contract_pnl(**payload)
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/gate")
def research_v31_gate(payload: dict):
    try: return research_gate(payload["metrics"], int(payload.get("min_trades",30)), float(payload.get("max_drawdown_limit",0.20)))
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))


# AETHER v3.1 historical-data research endpoints (research only; never place orders).
from .engines.research_v31 import parse_ohlcv_csv, india_cost_estimate, cash_equity_backtest, futures_contract_pnl, research_gate

@app.post("/api/v1/research/v31/import-csv")
def research_v31_import_csv(payload: dict):
    try: return parse_ohlcv_csv(payload.get("csv_text", ""))
    except (ValueError, TypeError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/estimate-costs")
def research_v31_costs(payload: dict):
    try: return india_cost_estimate(float(payload["notional"]), payload["side"], payload["segment"], payload.get("rates", {}))
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/cash-backtest")
def research_v31_cash_backtest(payload: dict):
    try: return cash_equity_backtest(payload["closes"], payload["signals"], float(payload.get("capital",50000)), float(payload.get("costs_per_side",0)))
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/futures-pnl")
def research_v31_futures_pnl(payload: dict):
    try: return futures_contract_pnl(**payload)
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/gate")
def research_v31_gate(payload: dict):
    try: return research_gate(payload["metrics"], int(payload.get("min_trades",30)), float(payload.get("max_drawdown_limit",0.20)))
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))


# AETHER v3.1 historical-data research endpoints (research only; never place orders).
from .engines.research_v31 import parse_ohlcv_csv, india_cost_estimate, cash_equity_backtest, futures_contract_pnl, research_gate

@app.post("/api/v1/research/v31/import-csv")
def research_v31_import_csv(payload: dict):
    try: return parse_ohlcv_csv(payload.get("csv_text", ""))
    except (ValueError, TypeError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/estimate-costs")
def research_v31_costs(payload: dict):
    try: return india_cost_estimate(float(payload["notional"]), payload["side"], payload["segment"], payload.get("rates", {}))
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/cash-backtest")
def research_v31_cash_backtest(payload: dict):
    try: return cash_equity_backtest(payload["closes"], payload["signals"], float(payload.get("capital",50000)), float(payload.get("costs_per_side",0)))
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/futures-pnl")
def research_v31_futures_pnl(payload: dict):
    try: return futures_contract_pnl(**payload)
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/gate")
def research_v31_gate(payload: dict):
    try: return research_gate(payload["metrics"], int(payload.get("min_trades",30)), float(payload.get("max_drawdown_limit",0.20)))
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))


# AETHER v3.1 historical-data research endpoints (research only; never place orders).
from .engines.research_v31 import parse_ohlcv_csv, india_cost_estimate, cash_equity_backtest, futures_contract_pnl, research_gate

@app.post("/api/v1/research/v31/import-csv")
def research_v31_import_csv(payload: dict):
    try: return parse_ohlcv_csv(payload.get("csv_text", ""))
    except (ValueError, TypeError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/estimate-costs")
def research_v31_costs(payload: dict):
    try: return india_cost_estimate(float(payload["notional"]), payload["side"], payload["segment"], payload.get("rates", {}))
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/cash-backtest")
def research_v31_cash_backtest(payload: dict):
    try: return cash_equity_backtest(payload["closes"], payload["signals"], float(payload.get("capital",50000)), float(payload.get("costs_per_side",0)))
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/futures-pnl")
def research_v31_futures_pnl(payload: dict):
    try: return futures_contract_pnl(**payload)
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/gate")
def research_v31_gate(payload: dict):
    try: return research_gate(payload["metrics"], int(payload.get("min_trades",30)), float(payload.get("max_drawdown_limit",0.20)))
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))


# AETHER v3.1 historical-data research endpoints (research only; never place orders).
from .engines.research_v31 import parse_ohlcv_csv, india_cost_estimate, cash_equity_backtest, futures_contract_pnl, research_gate

@app.post("/api/v1/research/v31/import-csv")
def research_v31_import_csv(payload: dict):
    try: return parse_ohlcv_csv(payload.get("csv_text", ""))
    except (ValueError, TypeError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/estimate-costs")
def research_v31_costs(payload: dict):
    try: return india_cost_estimate(float(payload["notional"]), payload["side"], payload["segment"], payload.get("rates", {}))
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/cash-backtest")
def research_v31_cash_backtest(payload: dict):
    try: return cash_equity_backtest(payload["closes"], payload["signals"], float(payload.get("capital",50000)), float(payload.get("costs_per_side",0)))
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/futures-pnl")
def research_v31_futures_pnl(payload: dict):
    try: return futures_contract_pnl(**payload)
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))

@app.post("/api/v1/research/v31/gate")
def research_v31_gate(payload: dict):
    try: return research_gate(payload["metrics"], int(payload.get("min_trades",30)), float(payload.get("max_drawdown_limit",0.20)))
    except (ValueError, TypeError, KeyError) as exc: raise HTTPException(422, str(exc))

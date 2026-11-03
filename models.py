from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, Integer, DateTime, JSON, func, Text, Boolean

class Base(DeclarativeBase): pass

class Portfolio(Base):
    __tablename__="portfolios"
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(120))
    base_currency: Mapped[str]=mapped_column(String(3),default="INR")
    created_at: Mapped[object]=mapped_column(DateTime(timezone=True),server_default=func.now())

class Position(Base):
    __tablename__="positions"
    id: Mapped[int]=mapped_column(primary_key=True)
    portfolio_id: Mapped[int]=mapped_column(Integer,index=True)
    symbol: Mapped[str]=mapped_column(String(32),index=True)
    quantity: Mapped[float]=mapped_column(Float)
    average_cost: Mapped[float]=mapped_column(Float)
    last_price: Mapped[float]=mapped_column(Float)
    asset_class: Mapped[str]=mapped_column(String(40),default="EQUITY")

class AuditEvent(Base):
    __tablename__="audit_events"
    id: Mapped[int]=mapped_column(primary_key=True)
    event_type: Mapped[str]=mapped_column(String(80))
    actor: Mapped[str]=mapped_column(String(120),default="local-demo")
    payload: Mapped[dict]=mapped_column(JSON)
    created_at: Mapped[object]=mapped_column(DateTime(timezone=True),server_default=func.now())


class MarketBar(Base):
    __tablename__="market_bars"
    id: Mapped[int]=mapped_column(primary_key=True)
    symbol: Mapped[str]=mapped_column(String(32),index=True)
    bar_date: Mapped[str]=mapped_column(String(32),index=True)
    interval: Mapped[str]=mapped_column(String(12),default="1d")
    open: Mapped[float]=mapped_column(Float)
    high: Mapped[float]=mapped_column(Float)
    low: Mapped[float]=mapped_column(Float)
    close: Mapped[float]=mapped_column(Float)
    volume: Mapped[float]=mapped_column(Float,default=0)
    source: Mapped[str]=mapped_column(String(120),default="csv-import")
    adjusted: Mapped[bool]=mapped_column(default=False)

class CorporateAction(Base):
    __tablename__="corporate_actions"
    id: Mapped[int]=mapped_column(primary_key=True)
    symbol: Mapped[str]=mapped_column(String(32),index=True)
    ex_date: Mapped[str]=mapped_column(String(32),index=True)
    action_type: Mapped[str]=mapped_column(String(32))
    value: Mapped[float]=mapped_column(Float)
    currency: Mapped[str]=mapped_column(String(3),default="INR")
    source: Mapped[str]=mapped_column(String(120),default="csv-import")

class DataIngestion(Base):
    __tablename__="data_ingestions"
    id: Mapped[int]=mapped_column(primary_key=True)
    dataset: Mapped[str]=mapped_column(String(32))
    source: Mapped[str]=mapped_column(String(120))
    status: Mapped[str]=mapped_column(String(20))
    rows_received: Mapped[int]=mapped_column(Integer,default=0)
    rows_inserted: Mapped[int]=mapped_column(Integer,default=0)
    rows_rejected: Mapped[int]=mapped_column(Integer,default=0)
    details: Mapped[dict]=mapped_column(JSON,default=dict)
    created_at: Mapped[object]=mapped_column(DateTime(timezone=True),server_default=func.now())


class Instrument(Base):
    __tablename__="instruments"
    id: Mapped[int]=mapped_column(primary_key=True)
    symbol: Mapped[str]=mapped_column(String(32),index=True)
    exchange: Mapped[str]=mapped_column(String(8),index=True)
    isin: Mapped[str|None]=mapped_column(String(12),index=True,nullable=True)
    name: Mapped[str]=mapped_column(String(200))
    segment: Mapped[str]=mapped_column(String(40),default="EQ")
    instrument_type: Mapped[str]=mapped_column(String(24),default="EQUITY")
    sector: Mapped[str]=mapped_column(String(80),default="UNKNOWN")
    lot_size: Mapped[int]=mapped_column(Integer,default=1)
    tick_size: Mapped[float]=mapped_column(Float,default=0.05)
    source: Mapped[str]=mapped_column(String(120),default="csv-import")

class PortfolioTransaction(Base):
    __tablename__="portfolio_transactions"
    id: Mapped[int]=mapped_column(primary_key=True)
    portfolio_id: Mapped[int]=mapped_column(Integer,index=True)
    symbol: Mapped[str]=mapped_column(String(32),index=True)
    side: Mapped[str]=mapped_column(String(4))
    quantity: Mapped[float]=mapped_column(Float)
    price: Mapped[float]=mapped_column(Float)
    fees: Mapped[float]=mapped_column(Float,default=0)
    trade_date: Mapped[str]=mapped_column(String(32),index=True)
    notes: Mapped[str|None]=mapped_column(String(500),nullable=True)

class Benchmark(Base):
    __tablename__="benchmarks"
    id: Mapped[int]=mapped_column(primary_key=True)
    symbol: Mapped[str]=mapped_column(String(32),unique=True,index=True)
    name: Mapped[str]=mapped_column(String(120))
    exchange: Mapped[str]=mapped_column(String(12),default="NSE")
    source: Mapped[str]=mapped_column(String(120),default="user-configured")

class PortfolioBenchmark(Base):
    __tablename__="portfolio_benchmarks"
    id: Mapped[int]=mapped_column(primary_key=True)
    portfolio_id: Mapped[int]=mapped_column(Integer,index=True,unique=True)
    benchmark_symbol: Mapped[str]=mapped_column(String(32))


class CashEntry(Base):
    __tablename__="cash_entries"
    id: Mapped[int]=mapped_column(primary_key=True)
    portfolio_id: Mapped[int]=mapped_column(Integer,index=True)
    entry_type: Mapped[str]=mapped_column(String(20))
    amount: Mapped[float]=mapped_column(Float)
    currency: Mapped[str]=mapped_column(String(3),default="INR")
    trade_date: Mapped[str]=mapped_column(String(32),index=True)
    reference: Mapped[str|None]=mapped_column(String(120),nullable=True)
    notes: Mapped[str|None]=mapped_column(String(500),nullable=True)


class AccessUser(Base):
    __tablename__="access_users"
    id: Mapped[int]=mapped_column(primary_key=True)
    username: Mapped[str]=mapped_column(String(80),unique=True,index=True)
    display_name: Mapped[str]=mapped_column(String(120),default="")
    status: Mapped[str]=mapped_column(String(16),default="active")
    password_hash: Mapped[str]=mapped_column(String(256),default="")
    is_admin: Mapped[bool]=mapped_column(default=False)

class PortfolioAccess(Base):
    __tablename__="portfolio_access"
    id: Mapped[int]=mapped_column(primary_key=True)
    portfolio_id: Mapped[int]=mapped_column(Integer,index=True)
    user_id: Mapped[int]=mapped_column(Integer,index=True)
    role: Mapped[str]=mapped_column(String(16),default="viewer")


# AETHER AutoTrader v2.0 — user-isolated paper trading records.
from sqlalchemy import UniqueConstraint

class PaperAccount(Base):
    __tablename__ = "paper_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    initial_capital: Mapped[float] = mapped_column(Float, default=50000.0)
    cash_balance: Mapped[float] = mapped_column(Float, default=50000.0)
    daily_realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    daily_pnl_date: Mapped[str] = mapped_column(String(10), default="")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

class PaperPosition(Base):
    __tablename__ = "paper_positions"
    __table_args__ = (UniqueConstraint("user_id", "symbol", "segment", name="uq_paper_position_user_symbol_segment"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    exchange: Mapped[str] = mapped_column(String(8), default="NSE")
    segment: Mapped[str] = mapped_column(String(8), default="CASH")
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    lot_size: Mapped[int] = mapped_column(Integer, default=1)
    average_price: Mapped[float] = mapped_column(Float, default=0.0)
    last_price: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)

class PaperOrder(Base):
    __tablename__ = "paper_orders"
    __table_args__ = (UniqueConstraint("user_id", "client_order_id", name="uq_paper_order_user_client_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    client_order_id: Mapped[str] = mapped_column(String(48))
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    exchange: Mapped[str] = mapped_column(String(8), default="NSE")
    segment: Mapped[str] = mapped_column(String(8), default="CASH")
    side: Mapped[str] = mapped_column(String(4))
    quantity: Mapped[int] = mapped_column(Integer)
    lot_size: Mapped[int] = mapped_column(Integer, default=1)
    trade_style: Mapped[str] = mapped_column(String(12), default="INTRADAY")
    reference_price: Mapped[float] = mapped_column(Float)
    fill_price: Mapped[float] = mapped_column(Float)
    stop_loss_price: Mapped[float] = mapped_column(Float, default=0.0)
    notional: Mapped[float] = mapped_column(Float)
    estimated_costs: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default="FILLED")
    price_source: Mapped[str] = mapped_column(String(32), default="MANUAL_REFERENCE")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GrowwConnection(Base):
    __tablename__ = "groww_connections"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    encrypted_access_token: Mapped[str] = mapped_column(Text)
    connected_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

class LiveTradingState(Base):
    __tablename__ = "live_trading_states"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    armed: Mapped[bool] = mapped_column(Boolean, default=False)
    armed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    daily_date: Mapped[str] = mapped_column(String(10), default="")
    daily_order_count: Mapped[int] = mapped_column(Integer, default=0)
    daily_notional: Mapped[float] = mapped_column(Float, default=0.0)

class AutoStrategyConfig(Base):
    __tablename__ = "auto_strategy_configs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(80), default="AETHER strategy")
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    groww_symbol: Mapped[str] = mapped_column(String(100))
    exchange: Mapped[str] = mapped_column(String(8), default="NSE")
    segment: Mapped[str] = mapped_column(String(8), default="CASH")
    candle_interval: Mapped[str] = mapped_column(String(16), default="5minute")
    strategy: Mapped[str] = mapped_column(String(32), default="trend_following")
    lot_size: Mapped[int] = mapped_column(Integer, default=1)
    product: Mapped[str] = mapped_column(String(8), default="MIS")
    max_order_value: Mapped[float] = mapped_column(Float, default=10000.0)
    stop_loss_pct: Mapped[float] = mapped_column(Float, default=0.02)
    target_pct: Mapped[float] = mapped_column(Float, default=0.04)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    pending_order_id: Mapped[str] = mapped_column(String(64), default="")
    pending_order_side: Mapped[str] = mapped_column(String(8), default="")
    pending_reference_id: Mapped[str] = mapped_column(String(20), default="")
    open_quantity: Mapped[int] = mapped_column(Integer, default=0)
    entry_price: Mapped[float] = mapped_column(Float, default=0.0)
    smart_order_id: Mapped[str] = mapped_column(String(64), default="")
    smart_order_type: Mapped[str] = mapped_column(String(8), default="")
    last_signal_key: Mapped[str] = mapped_column(String(64), default="")
    last_run_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

class LiveBrokerOrder(Base):
    __tablename__ = "live_broker_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    client_reference_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    groww_order_id: Mapped[str] = mapped_column(String(64), default="")
    symbol: Mapped[str] = mapped_column(String(64))
    exchange: Mapped[str] = mapped_column(String(8))
    segment: Mapped[str] = mapped_column(String(8))
    side: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[int] = mapped_column(Integer)
    product: Mapped[str] = mapped_column(String(8))
    order_type: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(24), default="SUBMITTED")
    source_strategy_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

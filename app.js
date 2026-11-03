const initial = {
 holdings:[
  {symbol:"RELIANCE",name:"Reliance Industries",qty:120,avg:2810,price:2942.5,sector:"Energy"},
  {symbol:"HDFCBANK",name:"HDFC Bank",qty:250,avg:1640,price:1718.2,sector:"Banking"},
  {symbol:"INFY",name:"Infosys",qty:180,avg:1510,price:1468.4,sector:"IT"},
  {symbol:"TCS",name:"Tata Consultancy",qty:75,avg:3820,price:4012,sector:"IT"},
  {symbol:"ICICIBANK",name:"ICICI Bank",qty:160,avg:1090,price:1164.7,sector:"Banking"},
  {symbol:"ITC",name:"ITC Limited",qty:400,avg:438,price:421.3,sector:"FMCG"}
 ],
 watch:[
  {symbol:"NIFTY 50",name:"NSE Index",price:24185.4,change:0.62},
  {symbol:"SENSEX",name:"BSE Index",price:79486.3,change:0.54},
  {symbol:"RELIANCE",name:"Reliance Industries",price:2942.5,change:0.88},
  {symbol:"HDFCBANK",name:"HDFC Bank",price:1718.2,change:0.41},
  {symbol:"INFY",name:"Infosys",price:1468.4,change:-0.73},
  {symbol:"TCS",name:"Tata Consultancy",price:4012,change:1.12},
  {symbol:"ICICIBANK",name:"ICICI Bank",price:1164.7,change:0.95},
  {symbol:"ITC",name:"ITC Limited",price:421.3,change:-0.38}
 ],
 trades:[]
};
let state;
try{state=JSON.parse(localStorage.getItem("aetherState"))||initial}catch{state=initial}
const save=()=>localStorage.setItem("aetherState",JSON.stringify(state));
const money=n=>"₹"+Number(n).toLocaleString("en-IN",{maximumFractionDigits:2});
const pct=n=>(n>=0?"+":"")+n.toFixed(2)+"%";
const total=()=>state.holdings.reduce((s,h)=>s+h.qty*h.price,0);
const cost=()=>state.holdings.reduce((s,h)=>s+h.qty*h.avg,0);
const pnl=()=>total()-cost();
const el=(id)=>document.getElementById(id);
function chart(){let vals=[94,96,95,99,98,102,101,105,103,108,107,111,109,115,114,118,117,121,119,125,123,128,127,132];let w=700,h=210,p=12,min=Math.min(...vals)-5,max=Math.max(...vals)+5;let pts=vals.map((v,i)=>`${p+i*(w-2*p)/(vals.length-1)},${h-p-(v-min)*(h-2*p)/(max-min)}`).join(" ");return `<svg class="chart" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><defs><linearGradient id="fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#55e0c0" stop-opacity=".25"/><stop offset="1" stop-color="#55e0c0" stop-opacity="0"/></linearGradient></defs>${[.25,.5,.75].map(y=>`<line x1="0" y1="${h*y}" x2="${w}" y2="${h*y}" stroke="#263750" stroke-dasharray="4 5"/>`).join("")}<polygon points="${p},${h} ${pts} ${w-p},${h}" fill="url(#fill)"/><polyline points="${pts}" fill="none" stroke="#55e0c0" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>`}
function metrics(){let t=total(),p=pnl(),r=p/cost()*100;return `<div class="grid metrics">
<div class="card"><div class="metric-label">PORTFOLIO MARKET VALUE</div><div class="metric-value">${money(t)}</div><div class="subtle">Simulated holdings value</div></div>
<div class="card"><div class="metric-label">UNREALIZED P&amp;L</div><div class="metric-value ${p>=0?"positive":"negative"}">${money(p)}</div><div class="subtle">${pct(r)} vs invested cost</div></div>
<div class="card"><div class="metric-label">INVESTED CAPITAL</div><div class="metric-value">${money(cost())}</div><div class="subtle">${state.holdings.length} positions</div></div>
<div class="card"><div class="metric-label">CASH (PAPER ACCOUNT)</div><div class="metric-value">${money(500000-state.trades.reduce((s,t)=>s+(t.side==="BUY"?t.qty*t.price:-t.qty*t.price),0))}</div><div class="subtle">Starting cash ₹5,00,000</div></div></div>`}
function tableHoldings(){return `<div class="card"><div class="card-head"><h3>PORTFOLIO HOLDINGS</h3><span class="tag">DEMO BOOK</span></div><div style="overflow:auto"><table><thead><tr><th>SECURITY</th><th class="right">QTY</th><th class="right">AVG COST</th><th class="right">LAST PRICE</th><th class="right">MARKET VALUE</th><th class="right">P&amp;L</th></tr></thead><tbody>${state.holdings.map(h=>{let p=(h.price-h.avg)*h.qty;return `<tr><td><div class="symbol">${h.symbol}</div><div class="company">${h.name}</div></td><td class="right">${h.qty}</td><td class="right">${money(h.avg)}</td><td class="right">${money(h.price)}</td><td class="right">${money(h.qty*h.price)}</td><td class="right ${p>=0?"positive":"negative"}">${money(p)}</td></tr>`}).join("")}</tbody></table></div></div>`}
function allocation(){let sectors={};state.holdings.forEach(h=>sectors[h.sector]=(sectors[h.sector]||0)+h.qty*h.price);let colors=["","blue","gold","purple"];return `<div class="card"><div class="card-head"><h3>SECTOR ALLOCATION</h3><span class="tag">BY MARKET VALUE</span></div>${Object.entries(sectors).sort((a,b)=>b[1]-a[1]).map(([s,v],i)=>`<div class="allocation-row"><div class="alloc-top"><span>${s}</span><b>${(v/total()*100).toFixed(1)}%</b></div><div class="bar ${colors[i%4]}"><span style="width:${v/total()*100}%"></span></div></div>`).join("")}</div>`}
function overview(){return `${metrics()}<div class="grid two-col"><div class="card"><div class="card-head"><h3>PORTFOLIO PERFORMANCE</h3><span class="tag">ILLUSTRATIVE INDEXED SERIES</span></div>${chart()}<div class="legend"><span><i></i> Portfolio</span><span><i class="blue"></i> Benchmark (illustrative)</span></div><p class="small-note">Illustrative historical shape only. Not calculated from actual daily market prices.</p></div>${allocation()}</div><div style="height:14px"></div>${tableHoldings()}`}
function portfolio(){return `${metrics()}<div class="toolbar"><div><h3 style="margin:0">Portfolio book</h3><div class="subtle">Holdings, valuation and sector exposure</div></div><button class="btn" onclick="exportCSV()">Export CSV ↓</button></div>${tableHoldings()}<div style="height:14px"></div>${allocation()}`}
function markets(){return `<div class="grid metrics">${state.watch.slice(0,4).map(x=>`<div class="card"><div class="metric-label">${x.symbol}</div><div class="metric-value">${x.price.toLocaleString("en-IN")}</div><span class="${x.change>=0?"positive":"negative"}">${pct(x.change)}</span><div class="subtle">${x.name}</div></div>`).join("")}</div><div class="card"><div class="card-head"><h3>INDIAN MARKET WATCHLIST</h3><span class="tag">SIMULATED SNAPSHOT</span></div><div style="overflow:auto"><table><thead><tr><th>INSTRUMENT</th><th class="right">LAST PRICE</th><th class="right">CHANGE</th><th class="right">STATUS</th></tr></thead><tbody>${state.watch.map(x=>`<tr><td><div class="symbol">${x.symbol}</div><div class="company">${x.name}</div></td><td class="right">${x.price.toLocaleString("en-IN",{maximumFractionDigits:2})}</td><td class="right ${x.change>=0?"positive":"negative"}">${pct(x.change)}</td><td class="right"><span class="tag">DEMO</span></td></tr>`).join("")}</tbody></table></div><p class="small-note">No live exchange connection is configured. Replace this adapter with an authorized market-data provider before using live prices.</p></div>`}
function risk(){let vals=state.holdings.map(h=>(h.price-h.avg)/h.avg);let mean=vals.reduce((a,b)=>a+b,0)/vals.length;let variance=vals.reduce((s,v)=>s+(v-mean)**2,0)/vals.length;let vol=Math.sqrt(variance)*Math.sqrt(252)*100;let worst=Math.min(...vals)*100;let exposure=total();let var95=exposure*0.025;return `<div class="grid risk-grid"><div class="card"><div class="metric-label">ANNUALIZED CROSS-SECTIONAL DISPERSION</div><div class="stat">${vol.toFixed(2)}%</div><div class="subtle">Not time-series realized volatility</div></div><div class="card"><div class="metric-label">SIMPLE HISTORICAL LOSS PROXY</div><div class="stat negative">${pct(worst)}</div><div class="subtle">Worst holding return vs average cost</div></div><div class="card"><div class="metric-label">ILLUSTRATIVE 1-DAY VaR (95%)</div><div class="stat">${money(var95)}</div><div class="subtle">2.5% notional proxy, not model VaR</div></div></div><div class="grid two-col" style="margin-top:14px"><div class="card"><h3>SCENARIO STRESS TEST</h3><p class="small-note">Apply hypothetical parallel shocks to current holdings.</p><div class="form-grid"><label class="field">Market shock (%)<input id="shock" type="number" value="-10" step="1"></label><label class="field">Rate-sensitive adjustment (%)<input id="rateShock" type="number" value="0" step="0.5"></label><div class="field"><span>Estimated P&amp;L</span><div class="stat" id="stressResult">${money(-exposure*.1)}</div></div></div><button class="btn primary" style="margin-top:13px" onclick="runStress()">Run scenario</button></div><div class="card"><h3>RISK MODEL STATUS</h3><p class="small-note">Current build uses transparent illustrative proxies. Production VaR/CVaR requires validated daily return histories, instrument-level exposures, covariance and backtesting.</p><div class="allocation-row"><div class="alloc-top"><span>Historical VaR</span><span class="tag">SCAFFOLD</span></div><div class="bar"><span style="width:35%"></span></div></div><div class="allocation-row"><div class="alloc-top"><span>Monte Carlo</span><span class="tag">PLANNED</span></div><div class="bar blue"><span style="width:8%"></span></div></div><div class="allocation-row"><div class="alloc-top"><span>Stress scenarios</span><span class="pill">BASIC</span></div><div class="bar gold"><span style="width:55%"></span></div></div></div></div>`}
function quant(){return `<div class="grid three-col"><div class="card"><div class="metric-label">VOLATILITY MODEL</div><div class="stat">GARCH(1,1)</div><span class="tag">IMPLEMENTATION PLANNED</span></div><div class="card"><div class="metric-label">REGIME DETECTION</div><div class="stat">HMM</div><span class="tag">IMPLEMENTATION PLANNED</span></div><div class="card"><div class="metric-label">PORTFOLIO OPTIMIZER</div><div class="stat">Risk parity</div><span class="tag">IMPLEMENTATION PLANNED</span></div></div><div class="card" style="margin-top:14px"><div class="card-head"><h3>QUANT RESEARCH WORKSPACE</h3><span class="tag">RESEARCH MODE</span></div><p class="small-note">This module is reserved for reproducible research: data lineage, feature definitions, model versions, walk-forward validation, transaction-cost-aware backtests and experiment logs.</p><div class="grid two-col"><div><h3>Planned research pipeline</h3><ol class="small-note"><li>Ingest adjusted OHLCV and corporate actions</li><li>Validate missing values and survivorship bias</li><li>Construct point-in-time features</li><li>Train and validate volatility/regime models</li><li>Backtest with costs and out-of-sample periods</li></ol></div><div><h3>Model governance</h3><ul class="small-note"><li>Dataset version and timestamp</li><li>Parameter and code version</li><li>Out-of-sample performance</li><li>Drawdown and turnover reports</li><li>Model approval and audit trail</li></ul></div></div></div>`}
function trading(){let cash=500000-state.trades.reduce((s,t)=>s+(t.side==="BUY"?t.qty*t.price:-t.qty*t.price),0);return `<div class="grid metrics"><div class="card"><div class="metric-label">PAPER ACCOUNT CASH</div><div class="metric-value">${money(cash)}</div><div class="subtle">Starting balance ₹5,00,000</div></div><div class="card"><div class="metric-label">PAPER ORDERS</div><div class="metric-value">${state.trades.length}</div><div class="subtle">Local simulator</div></div><div class="card"><div class="metric-label">EXECUTION</div><div class="metric-value">SIMULATED</div><div class="subtle">No broker connected</div></div><div class="card"><div class="metric-label">AUDIT</div><div class="metric-value">LOCAL</div><div class="subtle">Stored on this device</div></div></div><div class="card"><div class="card-head"><h3>PLACE PAPER ORDER</h3><span class="tag">NO REAL MONEY</span></div><div class="trade-form"><label class="field">Symbol<input id="tradeSymbol" value="RELIANCE" list="symbols"><datalist id="symbols">${state.watch.map(x=>`<option value="${x.symbol}">`).join("")}</datalist></label><label class="field">Side<select id="tradeSide"><option>BUY</option><option>SELL</option></select></label><label class="field">Quantity<input id="tradeQty" type="number" min="1" value="1"></label><label class="field">Reference price (₹)<input id="tradePrice" type="number" min=".01" step=".05" value="100"></label></div><button class="btn primary" style="margin-top:13px" onclick="placeTrade()">Submit simulated order</button><p class="small-note">Orders are simulated at the entered reference price. This is not connected to a broker or exchange.</p></div><div class="card" style="margin-top:14px"><div class="card-head"><h3>ORDER BLOTTER</h3><button class="btn" onclick="clearTrades()">Clear blotter</button></div>${state.trades.length?`<div style="overflow:auto"><table><thead><tr><th>TIME</th><th>SYMBOL</th><th>SIDE</th><th class="right">QTY</th><th class="right">PRICE</th><th class="right">NOTIONAL</th></tr></thead><tbody>${state.trades.slice().reverse().map(t=>`<tr><td>${t.time}</td><td>${t.symbol}</td><td class="${t.side==="BUY"?"positive":"negative"}">${t.side}</td><td class="right">${t.qty}</td><td class="right">${money(t.price)}</td><td class="right">${money(t.qty*t.price)}</td></tr>`).join("")}</tbody></table></div>`:`<div class="empty">No simulated orders yet.</div>`}</div>`}

let backendPortfolioId=localStorage.getItem("aetherPortfolioId")||"";
let backendBase=(localStorage.getItem("aetherApiBase")||((window.location.protocol==="http:"||window.location.protocol==="https:")?window.location.origin:"http://127.0.0.1:8000")).replace(/\/+$/,"");
let backendKey=localStorage.getItem("aetherApiKey")||"";
let backendToken=sessionStorage.getItem("aetherAccessToken")||"";
function institutional(){return `<div class="card"><div class="card-head"><h3>SECURE SIGN-IN</h3><span class="tag">JWT + PORTFOLIO RBAC</span></div><div class="trade-form"><label class="field">Username<input id="authUsername" autocomplete="username" value="${escapeHtml(localStorage.getItem("aetherUsername")||"")}"></label><label class="field">Password<input id="authPassword" type="password" autocomplete="current-password"></label></div><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px"><button class="btn primary" onclick="loginBackend()">Sign in</button><button class="btn" onclick="bootstrapBackendAdmin()">First-time admin setup</button><button class="btn" onclick="logoutBackend()">Sign out</button></div><label class="field" style="margin-top:10px">One-time bootstrap key (only for initial admin)<input id="bootstrapKey" type="password"></label><p class="small-note">Create the first administrator only once. Configure AETHER_BOOTSTRAP_KEY and AETHER_JWT_SECRET on the server before setup.</p><div id="authStatus" class="small-note">${backendToken?"Access token stored on this device.":"Not signed in."}</div></div><div class="card" style="margin-top:14px"><div class="card-head"><h3>BACKEND CONNECTION</h3><span class="tag">AETHER API v0.9</span></div><div class="trade-form"><label class="field">API base URL<input id="apiBase" value="${backendBase}" placeholder="http://192.168.1.x:8000"></label><label class="field">API key (optional)<input id="apiKey" type="password" value="${escapeHtml(backendKey)}" placeholder="Only if server requires it"></label><label class="field">Portfolio ID<input id="backendPortfolioId" type="number" min="1" value="${backendPortfolioId}" placeholder="Select below"></label></div><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px"><button class="btn primary" onclick="connectBackend()">Connect & refresh</button><button class="btn" onclick="createBackendPortfolio()">Create portfolio</button><button class="btn" onclick="loadConsolidated()">Consolidated report</button></div><p class="small-note">Enter the reachable URL of your own running AETHER backend. This page will not host or start the server.</p><div id="backendStatus" class="small-note">Not connected.</div></div><div class="card" style="margin-top:14px"><div class="card-head"><h3>BACKEND PORTFOLIOS</h3><span class="tag">SERVER DATA</span></div><div id="backendPortfolioList" class="small-note">Connect to load portfolios.</div></div><div class="grid two-col" style="margin-top:14px"><div class="card"><div class="card-head"><h3>PERFORMANCE & NAV</h3><button class="btn" onclick="loadBackendAnalytics()">Refresh</button></div><div id="backendAnalytics" class="small-note">Select a portfolio and refresh.</div></div><div class="card"><div class="card-head"><h3>RETURN CONTRIBUTION</h3><button class="btn" onclick="loadBackendContribution()">Refresh</button></div><div id="backendContribution" class="small-note">Sector and asset contribution based on imported daily prices.</div></div></div><div class="card" style="margin-top:14px"><div class="card-head"><h3>CONSOLIDATED PORTFOLIO REPORT</h3><button class="btn" onclick="loadConsolidated()">Refresh</button></div><div id="backendConsolidated" class="small-note">Not loaded.</div></div>`}
function setBackendStatus(msg,isBad=false){let x=el("backendStatus");if(x){x.textContent=msg;x.className="small-note "+(isBad?"negative":"positive")}}
function apiUrl(path){return backendBase+path}
async function apiFetch(path,options={}){let res=await fetch(apiUrl(path),{...options,headers:{"Content-Type":"application/json",...(backendKey?{"X-Aether-API-Key":backendKey}:{}),...(backendToken?{"Authorization":"Bearer "+backendToken}:{}),...(options.headers||{})}});let data=await res.json().catch(()=>({detail:res.statusText}));if(!res.ok)throw new Error(data.detail||("HTTP "+res.status));return data}
async function loginBackend(){backendBase=(el("apiBase").value||backendBase).trim().replace(/\/+$/,"");backendKey=el("apiKey").value||backendKey;let username=el("authUsername").value.trim(),password=el("authPassword").value;if(!username||!password){el("authStatus").textContent="Enter username and password.";return}try{let x=await apiFetch("/api/v1/auth/login",{method:"POST",body:JSON.stringify({username,password})});backendToken=x.access_token;sessionStorage.setItem("aetherAccessToken",backendToken);localStorage.setItem("aetherUsername",username);el("authStatus").textContent="Signed in as "+username;await connectBackend()}catch(e){el("authStatus").textContent="Sign-in failed: "+e.message}}
async function bootstrapBackendAdmin(){backendBase=(el("apiBase").value||backendBase).trim().replace(/\/+$/,"");let payload={bootstrap_key:el("bootstrapKey").value,username:el("authUsername").value.trim(),display_name:"Platform Administrator",password:el("authPassword").value};try{let x=await apiFetch("/api/v1/auth/bootstrap",{method:"POST",body:JSON.stringify(payload)});backendToken=x.access_token;sessionStorage.setItem("aetherAccessToken",backendToken);localStorage.setItem("aetherUsername",payload.username);el("authStatus").textContent="Administrator created. Save your credentials securely.";await connectBackend()}catch(e){el("authStatus").textContent="Bootstrap failed: "+e.message}}
function logoutBackend(){backendToken="";sessionStorage.removeItem("aetherAccessToken");el("authStatus").textContent="Signed out.";setBackendStatus("Sign in to continue.",true)}
async function connectBackend(){backendBase=(el("apiBase").value||"").trim().replace(/\/+$/,"");backendPortfolioId=el("backendPortfolioId").value||"";backendKey=el("apiKey").value||"";localStorage.setItem("aetherApiBase",backendBase);localStorage.setItem("aetherApiKey",backendKey);localStorage.setItem("aetherPortfolioId",backendPortfolioId);try{let h=await apiFetch("/health");setBackendStatus("Connected · "+h.service+" · v"+h.version);await loadBackendPortfolios();if(backendPortfolioId)await loadBackendAnalytics()}catch(e){setBackendStatus("Connection failed: "+e.message,true)}}
async function loadBackendPortfolios(){try{let rows=await apiFetch("/api/v1/portfolios");let box=el("backendPortfolioList");if(!rows.length){box.textContent="No backend portfolios yet. Create one above.";return}box.innerHTML=rows.map(p=>`<div class="allocation-row"><div class="alloc-top"><span><b>${escapeHtml(p.name)}</b> · ${p.base_currency} · ID ${p.id}</span><button class="btn" onclick="selectBackendPortfolio(${p.id})">Select</button></div></div>`).join("")}catch(e){setBackendStatus(e.message,true)}}
function escapeHtml(v){return String(v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function selectBackendPortfolio(id){backendPortfolioId=String(id);localStorage.setItem("aetherPortfolioId",backendPortfolioId);el("backendPortfolioId").value=backendPortfolioId;loadBackendAnalytics();loadBackendContribution()}
async function createBackendPortfolio(){let name=prompt("New backend portfolio name");if(!name)return;try{let p=await apiFetch("/api/v1/portfolios",{method:"POST",body:JSON.stringify({name,base_currency:"INR"})});selectBackendPortfolio(p.id);await loadBackendPortfolios();setBackendStatus("Created portfolio "+p.name+" (ID "+p.id+")")}catch(e){setBackendStatus(e.message,true)}}
async function loadBackendAnalytics(){if(!backendPortfolioId){setBackendStatus("Choose a portfolio ID first.",true);return}try{let [nav,a,r]=await Promise.all([apiFetch(`/api/v1/portfolios/${backendPortfolioId}/performance/nav`),apiFetch(`/api/v1/portfolios/${backendPortfolioId}/performance/analytics`),apiFetch(`/api/v1/risk/dashboard/${backendPortfolioId}`)]);let n=nav.nav[nav.nav.length-1];el("backendAnalytics").innerHTML=`<div class="grid metrics"><div><div class="metric-label">LATEST NAV</div><div class="metric-value">${money(n.nav)}</div></div><div><div class="metric-label">DAILY TWR</div><div class="metric-value">${pct(a.daily_twr*100)}</div></div><div><div class="metric-label">XIRR</div><div class="metric-value">${a.annualized_money_weighted_xirr===null?"N/A":pct(a.annualized_money_weighted_xirr*100)}</div></div><div><div class="metric-label">MAX DRAWDOWN</div><div class="metric-value negative">${pct(a.risk_metrics.max_drawdown*100)}</div></div></div><p class="small-note">As of ${n.date} · ${a.risk_metrics.observations} return observations · Sharpe ${a.risk_metrics.sharpe_ratio===null?"N/A":a.risk_metrics.sharpe_ratio.toFixed(2)} · Sortino ${a.risk_metrics.sortino_ratio===null?"N/A":a.risk_metrics.sortino_ratio.toFixed(2)} · Calmar ${a.risk_metrics.calmar_ratio===null?"N/A":a.risk_metrics.calmar_ratio.toFixed(2)}</p><p class="small-note">${r.methodology}</p>`;setBackendStatus("Analytics loaded from backend.")}catch(e){el("backendAnalytics").textContent=e.message;setBackendStatus(e.message,true)}}
async function loadBackendContribution(){if(!backendPortfolioId)return;try{let x=await apiFetch(`/api/v1/portfolios/${backendPortfolioId}/performance/attribution/contribution`);el("backendContribution").innerHTML=`<b>Sector contribution</b><ul>${Object.entries(x.cumulative_sector_contribution).map(([k,v])=>`<li>${escapeHtml(k)}: ${pct(v*100)}</li>`).join("")||"<li>No matched data</li>"}</ul><b>Asset contribution</b><ul>${Object.entries(x.cumulative_asset_contribution).map(([k,v])=>`<li>${escapeHtml(k)}: ${pct(v*100)}</li>`).join("")||"<li>No matched data</li>"}</ul><p class="small-note">${escapeHtml(x.note)}</p>`}catch(e){el("backendContribution").textContent=e.message}}
async function loadConsolidated(){try{let x=await apiFetch("/api/v1/portfolios/consolidated");el("backendConsolidated").innerHTML=x.currency_groups.map(g=>`<div class="allocation-row"><b>${g.currency}</b> · ${g.portfolio_count} portfolios · NAV ${money(g.nav)}</div>`).join("")+x.portfolios.map(p=>`<div class="small-note">${escapeHtml(p.name)} · ${p.base_currency} · NAV ${money(p.nav)}${p.unpriced_symbols.length?" · Unpriced: "+escapeHtml(p.unpriced_symbols.join(", ")):""}</div>`).join("")+`<p class="small-note">${escapeHtml(x.note)}</p>`}catch(e){el("backendConsolidated").textContent=e.message}}


function autotrader(){return `
  <div class="notice">PAPER MODE ONLY · ₹50,000 virtual capital · CASH + F&O · NO REAL BROKER ORDERS</div>
  <div class="grid metrics">
    <div class="card"><div class="metric-label">PAPER EQUITY</div><div class="metric-value" id="atEquity">₹50,000</div><div class="subtle">Starting virtual capital</div></div>
    <div class="card"><div class="metric-label">AVAILABLE CASH</div><div class="metric-value" id="atCash">₹50,000</div><div class="subtle">After simulated fills and costs</div></div>
    <div class="card"><div class="metric-label">TOTAL P&amp;L</div><div class="metric-value" id="atPnl">₹0</div><div class="subtle">Realized + marked unrealized</div></div>
    <div class="card"><div class="metric-label">DAILY REALIZED P&amp;L</div><div class="metric-value" id="atDaily">₹0</div><div class="subtle">Daily loss guard applies to realized P&amp;L</div></div>
  </div>
  <div class="grid two-col">
    <div class="card">
      <div class="card-head"><h3>PLACE PAPER ORDER</h3><span class="tag">SIMULATED ONLY</span></div>
      <div class="trade-form">
        <label class="field">Symbol<input id="atSymbol" value="RELIANCE" maxlength="64"></label>
        <label class="field">Exchange<select id="atExchange"><option>NSE</option><option>BSE</option></select></label>
        <label class="field">Segment<select id="atSegment"><option value="CASH">Cash equity</option><option value="FNO">F&amp;O</option></select></label>
        <label class="field">Side<select id="atSide"><option>BUY</option><option>SELL</option></select></label>
        <label class="field">Quantity<input id="atQty" type="number" min="1" value="1"></label>
        <label class="field">Lot size<input id="atLot" type="number" min="1" value="1"></label>
        <label class="field">Reference price ₹<input id="atPrice" type="number" min=".01" step=".05" value="100"></label>
        <label class="field">Stop loss ₹ (BUY)<input id="atStop" type="number" min=".01" step=".05" value="95"></label>
        <label class="field">Style<select id="atStyle"><option value="INTRADAY">Intraday</option><option value="SWING">Swing</option></select></label>
      </div>
      <button class="btn primary" style="margin-top:13px" onclick="submitAutoPaperOrder()">Execute simulated order</button>
      <p class="small-note">Enter a reference price manually until a Groww read-only quote feed is configured. Simulated slippage and costs are applied. BUY orders require a stop loss. SELL can only close an existing long position.</p>
      <div id="atOrderStatus" class="small-note"></div>
    </div>
    <div class="card">
      <div class="card-head"><h3>RISK GUARDRAILS</h3><span class="tag">SERVER ENFORCED</span></div>
      <div class="allocation-row"><div class="alloc-top"><span>Max risk per trade</span><b>₹500 (1%)</b></div><div class="bar"><span style="width:20%"></span></div></div>
      <div class="allocation-row"><div class="alloc-top"><span>Daily realized loss limit</span><b>₹1,000 (2%)</b></div><div class="bar gold"><span style="width:40%"></span></div></div>
      <div class="allocation-row"><div class="alloc-top"><span>Max single position</span><b>₹12,500 (25%)</b></div><div class="bar blue"><span style="width:50%"></span></div></div>
      <div class="allocation-row"><div class="alloc-top"><span>Gross exposure limit</span><b>₹50,000 (100%)</b></div><div class="bar purple"><span style="width:100%"></span></div></div>
      <p class="small-note">F&amp;O is long-only in this paper simulator and reserves full notional rather than modelling broker margin. No shorting, leverage, expiry settlement or automatic intraday square-off is implemented.</p>
      <div class="toolbar"><b>Groww data connection</b><button class="btn" onclick="loadGrowwStatus()">Check status</button></div>
      <div id="growwStatus" class="small-note">Read-only quote adapter scaffold. API token and SDK are not configured.</div>
    </div>
  </div>
<div class="card" style="margin-top:14px">
  <div class="card-head"><h3>CONNECT GROWW</h3><span class="tag">API TOKEN · HTTPS</span></div>
  <p class="small-note">Groww does not document third-party OAuth login. Generate an API access token in Groww Trading APIs and paste it here. AETHER encrypts it on the backend. Never enter your Groww password, OTP or TOTP.</p>
  <div class="trade-form">
    <label class="field">Groww API access token<input id="growwTokenInput" type="password" autocomplete="off" placeholder="Paste Groww-generated access token"></label>
  </div>
  <div class="toolbar">
    <button class="btn primary" onclick="connectGrowwApi()">Connect Groww API</button>
    <button class="btn" onclick="disconnectGrowwApi()">Disconnect</button>
    <button class="btn" onclick="loadGrowwStatus()">Refresh status</button>
  </div>
  <div id="growwConnectionStatus" class="small-note">Not checked.</div>
  <p class="small-note">Groww access tokens expire daily at 06:00 IST. Reconnect with a fresh token when it expires.</p>
</div>
<div class="card" style="margin-top:14px">
  <div class="card-head"><h3>AUTO STRATEGY WATCHLIST</h3><span class="tag">DISABLED UNTIL ARMED</span></div>
  <div class="trade-form">
    <label class="field">Trading symbol<input id="autoSymbol" value="RELIANCE"></label>
    <label class="field">Groww symbol<input id="autoGrowwSymbol" value="NSE-RELIANCE"></label>
    <label class="field">Exchange<select id="autoExchange"><option>NSE</option><option>BSE</option></select></label>
    <label class="field">Segment<select id="autoSegment"><option value="CASH">CASH</option><option value="FNO">FNO</option></select></label>
    <label class="field">Strategy<select id="autoStrategy"><option value="trend_following">Trend following</option><option value="breakout">Momentum breakout</option><option value="swing_trend">Swing trend</option><option value="mean_reversion">Mean reversion</option></select></label>
    <label class="field">Candle interval<select id="autoInterval"><option value="5minute">5 minute</option><option value="15minute">15 minute</option><option value="30minute">30 minute</option><option value="1hour">1 hour</option><option value="1day">1 day</option></select></label>
    <label class="field">Product<select id="autoProduct"><option value="MIS">MIS (intraday)</option><option value="CNC">CNC (cash delivery)</option><option value="NRML">NRML (F&amp;O carry)</option></select></label>
    <label class="field">Lot size<input id="autoLotSize" type="number" min="1" value="1"></label>
    <label class="field">Maximum order value ₹<input id="autoMaxValue" type="number" min="1" max="12500" value="10000"></label>
    <label class="field">Stop loss %<input id="autoStopPct" type="number" min="0.1" max="10" step="0.1" value="2"></label>
    <label class="field">Target %<input id="autoTargetPct" type="number" min="0.2" max="30" step="0.1" value="4"></label>
  </div>
  <div class="toolbar"><button class="btn primary" onclick="addAutoStrategy()">Save strategy</button><button class="btn" onclick="loadAutoStrategies()">Refresh strategies</button></div>
  <div id="autoStrategyList" class="small-note">No strategies loaded.</div>
</div>
<div class="card" style="margin-top:14px">
  <div class="card-head"><h3>LIVE TRADING CONTROL</h3><span class="tag">OFF BY DEFAULT</span></div>
  <p class="small-note">Live orders require Groww confirmation of API/algo permissions, the required static IP and server-side approval flags. These controls cannot override a server kill switch.</p>
  <div class="toolbar">
    <button class="btn primary" onclick="armGrowwLive()">Arm live trading</button>
    <button class="btn" onclick="disarmGrowwLive()">Emergency disarm</button>
    <button class="btn" onclick="runAutoScan()">Run one scan</button>
  </div>
  <div id="liveTradingStatus" class="small-note">Live trading is not armed.</div>
</div>
  <div class="card" style="margin-top:14px">
    <div class="card-head"><h3>OPEN PAPER POSITIONS</h3><button class="btn" onclick="refreshAutoTrader()">Refresh</button></div>
    <div id="atPositions" class="small-note">Connect to AETHER backend to load positions.</div>
  </div>
  <div class="card" style="margin-top:14px">
    <div class="card-head"><h3>PAPER ORDER BLOTTER</h3><button class="btn" onclick="refreshAutoTrader()">Refresh</button></div>
    <div id="atOrders" class="small-note">No orders loaded.</div>
  </div>
  <div class="toolbar" style="margin-top:14px"><span class="small-note">Need to sign in first? Use Institutional → Secure sign-in. Backend URL and JWT session are reused.</span><button class="btn" onclick="resetAutoTrader()">Reset paper account</button></div>
  <div id="atConnection" class="small-note"></div>`}
async function refreshAutoTrader(){
  try{
    const [s,orders]=await Promise.all([apiFetch("/api/v1/autotrader/summary"),apiFetch("/api/v1/autotrader/orders")]);
    el("atEquity").textContent=money(s.equity);el("atCash").textContent=money(s.cash_balance);
    el("atPnl").textContent=money(s.total_pnl);el("atPnl").className="metric-value "+(s.total_pnl>=0?"positive":"negative");
    el("atDaily").textContent=money(s.daily_realized_pnl);el("atDaily").className="metric-value "+(s.daily_realized_pnl>=0?"positive":"negative");
    el("atPositions").innerHTML=s.positions.length?`<div style="overflow:auto"><table><thead><tr><th>SYMBOL</th><th>SEGMENT</th><th class="right">QTY</th><th class="right">AVG</th><th class="right">LAST</th><th class="right">UNREALIZED</th></tr></thead><tbody>${s.positions.map(p=>`<tr><td>${escapeHtml(p.symbol)}</td><td>${p.segment}</td><td class="right">${p.quantity} × ${p.lot_size}</td><td class="right">${money(p.average_price)}</td><td class="right">${money(p.last_price)}</td><td class="right ${p.unrealized_pnl>=0?"positive":"negative"}">${money(p.unrealized_pnl)}</td></tr>`).join("")}</tbody></table></div>`:"No open positions.";
    el("atOrders").innerHTML=orders.length?`<div style="overflow:auto"><table><thead><tr><th>SYMBOL</th><th>SIDE</th><th>SEGMENT</th><th class="right">QTY</th><th class="right">FILL</th><th class="right">COSTS</th><th>STATUS</th></tr></thead><tbody>${orders.map(o=>`<tr><td>${escapeHtml(o.symbol)}</td><td>${o.side}</td><td>${o.segment}</td><td class="right">${o.quantity}</td><td class="right">${money(o.fill_price)}</td><td class="right">${money(o.estimated_costs)}</td><td>${o.status}</td></tr>`).join("")}</tbody></table></div>`:"No paper orders yet.";
    el("atConnection").textContent="AETHER backend connected · PAPER_ONLY · real broker orders disabled.";
  }catch(e){if(el("atConnection"))el("atConnection").textContent="Backend unavailable: "+e.message+" · Sign in via Institutional first."}
}
async function submitAutoPaperOrder(){
  const payload={symbol:el("atSymbol").value.trim(),exchange:el("atExchange").value,segment:el("atSegment").value,side:el("atSide").value,quantity:Number(el("atQty").value),lot_size:Number(el("atLot").value),trade_style:el("atStyle").value,reference_price:Number(el("atPrice").value),stop_loss_price:el("atStop").value?Number(el("atStop").value):null};
  try{const r=await apiFetch("/api/v1/autotrader/orders",{method:"POST",body:JSON.stringify(payload)});el("atOrderStatus").textContent=`Paper fill ${r.status}: ${r.symbol} ${r.side} · ${r.quantity} · ${money(r.fill_price)} · costs ${money(r.estimated_costs)}. No Groww order submitted.`;await refreshAutoTrader()}
  catch(e){el("atOrderStatus").textContent="Order rejected: "+e.message}
}
async function resetAutoTrader(){
  if(!confirm("Reset all server-side paper orders and positions and restore ₹50,000 virtual cash?"))return;
  try{await apiFetch("/api/v1/autotrader/reset?confirm=true",{method:"POST"});await refreshAutoTrader();el("atOrderStatus").textContent="Paper account reset to ₹50,000."}
  catch(e){el("atConnection").textContent=e.message}
}


async function connectGrowwApi(){
  const token=el("growwTokenInput").value.trim();
  if(!token){el("growwConnectionStatus").textContent="Paste a Groww API access token first.";return}
  try{
    const r=await apiFetch("/api/v1/groww/connect",{method:"POST",body:JSON.stringify({access_token:token})});
    el("growwTokenInput").value="";
    el("growwConnectionStatus").textContent="Groww API connected. Token encrypted on backend. Live trading remains disarmed.";
    await loadGrowwStatus();
  }catch(e){el("growwConnectionStatus").textContent="Connection failed: "+e.message}
}
async function disconnectGrowwApi(){
  if(!confirm("Disconnect Groww and disarm AETHER live trading?"))return;
  try{await apiFetch("/api/v1/groww/disconnect",{method:"POST"});await loadGrowwStatus()}
  catch(e){el("growwConnectionStatus").textContent=e.message}
}
async function loadGrowwStatus(){
  try{
    const s=await apiFetch("/api/v1/groww/connection");
    const txt=`Groww API: ${s.connected?"CONNECTED":"NOT CONNECTED"} · Live armed: ${s.live_trading_armed?"YES":"NO"} · Server live switch: ${s.server_live_switch?"ON":"OFF"} · Broker approval flag: ${s.algo_approval_flag?"ON":"OFF"} · Auto worker: ${s.auto_worker_enabled?"RUNNING/ENABLED":"OFF"}`;
    if(el("growwConnectionStatus"))el("growwConnectionStatus").textContent=txt;
    if(el("liveTradingStatus"))el("liveTradingStatus").textContent=txt;
    if(el("growwStatus"))el("growwStatus").textContent=txt;
  }catch(e){
    if(el("growwConnectionStatus"))el("growwConnectionStatus").textContent="Status unavailable: "+e.message;
    if(el("growwStatus"))el("growwStatus").textContent=e.message;
  }
}
async function armGrowwLive(){
  const phrase=prompt('Type exactly: I UNDERSTAND LIVE TRADING');
  if(phrase===null)return;
  try{
    const r=await apiFetch("/api/v1/groww/live/enable",{method:"POST",body:JSON.stringify({confirmation:phrase})});
    el("liveTradingStatus").textContent="Live trading armed. Capital cap ₹"+r.capital_limit+". Worker and broker approval must also be enabled.";
    await loadGrowwStatus();
  }catch(e){el("liveTradingStatus").textContent="Could not arm live trading: "+e.message}
}
async function disarmGrowwLive(){
  try{await apiFetch("/api/v1/groww/live/disable",{method:"POST"});await loadGrowwStatus()}
  catch(e){el("liveTradingStatus").textContent=e.message}
}
async function addAutoStrategy(){
  const payload={
    name:el("autoSymbol").value.trim()+" "+el("autoStrategy").value,
    symbol:el("autoSymbol").value.trim(),
    groww_symbol:el("autoGrowwSymbol").value.trim(),
    exchange:el("autoExchange").value,segment:el("autoSegment").value,
    strategy:el("autoStrategy").value,candle_interval:el("autoInterval").value,
    product:el("autoProduct").value,lot_size:Number(el("autoLotSize").value),
    max_order_value:Number(el("autoMaxValue").value),
    stop_loss_pct:Number(el("autoStopPct").value)/100,
    target_pct:Number(el("autoTargetPct").value)/100
  };
  try{
    const r=await apiFetch("/api/v1/autotrader/strategies",{method:"POST",body:JSON.stringify(payload)});
    await apiFetch("/api/v1/autotrader/strategies/"+r.id+"/enable",{method:"POST"});
    el("autoStrategyList").textContent="Saved and enabled strategy #"+r.id+" for "+payload.symbol+". It will only trade when all live gates are satisfied.";
    await loadAutoStrategies();
  }catch(e){el("autoStrategyList").textContent="Could not save strategy: "+e.message}
}
async function loadAutoStrategies(){
  try{
    const rows=await apiFetch("/api/v1/autotrader/strategies");
    el("autoStrategyList").innerHTML=rows.length?rows.map(x=>`<div class="toolbar"><span><b>${escapeHtml(x.symbol)}</b> · ${escapeHtml(x.segment)} · ${escapeHtml(x.strategy)} · ${x.enabled?"enabled":"disabled"}</span><button class="btn" onclick="toggleAutoStrategy(${x.id},${!x.enabled})">${x.enabled?"Disable":"Enable"}</button></div>`).join(""):"No strategies configured.";
  }catch(e){el("autoStrategyList").textContent="Strategy list unavailable: "+e.message}
}
async function toggleAutoStrategy(id,enable){
  try{await apiFetch(`/api/v1/autotrader/strategies/${id}/${enable?"enable":"disable"}`,{method:"POST"});await loadAutoStrategies()}
  catch(e){el("autoStrategyList").textContent=e.message}
}
async function runAutoScan(){
  try{const r=await apiFetch("/api/v1/autotrader/worker/scan-once",{method:"POST"});el("liveTradingStatus").textContent=JSON.stringify(r)}
  catch(e){el("liveTradingStatus").textContent="Scan blocked: "+e.message}
}

const views={overview,portfolio,institutional,markets,risk,quant,trading,autotrader};let current="overview";
function render(v=current){current=v;el("pageTitle").textContent=({overview:"Overview",portfolio:"Portfolio",institutional:"Institutional portfolio management",markets:"Markets",risk:"Risk analytics",quant:"Quant research",trading:"Legacy simulator",autotrader:"AETHER AutoTrader"})[v];el("view").innerHTML=views[v]();document.querySelectorAll(".nav-item").forEach(b=>b.classList.toggle("active",b.dataset.view===v));if(v==="autotrader"){setTimeout(()=>{refreshAutoTrader();loadGrowwStatus();loadAutoStrategies()},0)}if(v==="institutional"){el("apiBase").value=backendBase;el("apiKey").value=backendKey;el("backendPortfolioId").value=backendPortfolioId;el("authUsername").value=localStorage.getItem("aetherUsername")||"";}}
document.querySelectorAll(".nav-item").forEach(b=>b.addEventListener("click",()=>{render(b.dataset.view);el("sidebar").classList.remove("open")}));
el("menuBtn").addEventListener("click",()=>document.querySelector(".sidebar").classList.toggle("open"));
function runStress(){let s=Number(el("shock").value)/100, r=Number(el("rateShock").value)/100;let result=state.holdings.reduce((a,h)=>a+h.qty*h.price*(s+(h.sector==="Banking"?r:0)),0);el("stressResult").textContent=money(result);el("stressResult").className="stat "+(result>=0?"positive":"negative")}
function placeTrade(){let symbol=el("tradeSymbol").value.trim().toUpperCase(),side=el("tradeSide").value,qty=Number(el("tradeQty").value),price=Number(el("tradePrice").value);if(!symbol||!Number.isInteger(qty)||qty<1||!Number.isFinite(price)||price<=0){alert("Enter a valid symbol, whole-number quantity and positive price.");return}let cash=500000-state.trades.reduce((s,t)=>s+(t.side==="BUY"?t.qty*t.price:-t.qty*t.price),0);if(side==="BUY"&&qty*price>cash){alert("Insufficient simulated cash.");return}state.trades.push({symbol,side,qty,price,time:new Date().toLocaleString("en-IN")});save();render("trading")}
function clearTrades(){if(confirm("Clear all local paper orders?")){state.trades=[];save();render("trading")}}
function exportCSV(){let rows=[["Symbol","Name","Quantity","Average Cost","Last Price","Market Value","Unrealized PnL"],...state.holdings.map(h=>[h.symbol,h.name,h.qty,h.avg,h.price,h.qty*h.price,(h.price-h.avg)*h.qty])];let csv=rows.map(r=>r.map(x=>'"'+String(x).replaceAll('"','""')+'"').join(",")).join("\n");let a=document.createElement("a");a.href=URL.createObjectURL(new Blob([csv],{type:"text/csv"}));a.download="aether-portfolio-demo.csv";a.click();URL.revokeObjectURL(a.href)}
render();
if("serviceWorker" in navigator)window.addEventListener("load",()=>navigator.serviceWorker.register("./sw.js").catch(()=>{}));

"""
Data export endpoints (CSV, JSON).
"""

import csv
import io
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse

from src.auth.dependencies import get_current_active_user, optional_auth
from src.auth.models import User

router = APIRouter(prefix="/api/export", tags=["Export"])


def generate_csv(headers: List[str], rows: List[List[str]]) -> str:
    """Generate CSV string from headers and rows"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


@router.get("/opportunities/csv")
async def export_opportunities_csv(
    hours: int = Query(default=24, ge=1, le=168, description="Hours of history to export"),
    min_profit: float = Query(default=0.0, ge=0, description="Minimum profit percentage"),
    pair: Optional[str] = Query(default=None, description="Filter by trading pair"),
    current_user: Optional[User] = Depends(optional_auth),
):
    """
    Export arbitrage opportunities to CSV.
    
    Returns a downloadable CSV file with opportunity history.
    """
    # Import here to avoid circular imports
    from dashboard import manager
    
    if not manager.engine:
        return Response(
            content="Engine not initialized",
            media_type="text/plain",
            status_code=503,
        )
    
    # Get opportunities from engine history
    opportunities = manager.engine.history
    
    # Filter by time
    cutoff = datetime.now() - timedelta(hours=hours)
    opportunities = [o for o in opportunities if o.timestamp >= cutoff]
    
    # Filter by profit
    if min_profit > 0:
        opportunities = [o for o in opportunities if o.profit_percent >= min_profit]
    
    # Filter by pair
    if pair:
        pair_upper = pair.upper().replace("-", "/")
        opportunities = [o for o in opportunities if o.pair == pair_upper]
    
    # Generate CSV
    headers = [
        "timestamp",
        "pair",
        "buy_exchange",
        "sell_exchange",
        "buy_price",
        "sell_price",
        "profit_percent",
    ]
    
    rows = []
    for opp in opportunities:
        rows.append([
            opp.timestamp.isoformat(),
            opp.pair,
            opp.buy_exchange,
            opp.sell_exchange,
            f"{opp.buy_price:.8f}",
            f"{opp.sell_price:.8f}",
            f"{opp.profit_percent:.4f}",
        ])
    
    csv_content = generate_csv(headers, rows)
    
    filename = f"opportunities_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )


@router.get("/triangular/csv")
async def export_triangular_csv(
    hours: int = Query(default=24, ge=1, le=168, description="Hours of history to export"),
    min_profit: float = Query(default=0.0, ge=0, description="Minimum profit percentage"),
    exchange: Optional[str] = Query(default=None, description="Filter by exchange"),
    current_user: Optional[User] = Depends(optional_auth),
):
    """
    Export triangular arbitrage opportunities to CSV.
    """
    from dashboard import manager
    
    if not manager.triangular_engine:
        return Response(
            content="Triangular engine not initialized",
            media_type="text/plain",
            status_code=503,
        )
    
    # Get from triangular engine
    state = manager.triangular_engine.get_state()
    opportunities = state.get("triangular_history", [])
    
    # Filter
    cutoff = datetime.now() - timedelta(hours=hours)
    
    headers = [
        "timestamp",
        "exchange",
        "base_currency",
        "path",
        "profit_percent",
        "start_amount",
        "end_amount",
    ]
    
    rows = []
    for opp in opportunities:
        ts = datetime.fromisoformat(opp["timestamp"]) if isinstance(opp["timestamp"], str) else opp["timestamp"]
        if ts < cutoff:
            continue
        if min_profit > 0 and opp["profit_percent"] < min_profit:
            continue
        if exchange and opp["exchange"].lower() != exchange.lower():
            continue
        
        rows.append([
            opp["timestamp"] if isinstance(opp["timestamp"], str) else opp["timestamp"].isoformat(),
            opp["exchange"],
            opp["base_currency"],
            "->".join(opp["pairs"]),
            f"{opp['profit_percent']:.4f}",
            f"{opp.get('start_amount', 10000):.2f}",
            f"{opp.get('end_amount', 0):.2f}",
        ])
    
    csv_content = generate_csv(headers, rows)
    filename = f"triangular_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )


@router.get("/prices/csv")
async def export_prices_csv(
    pair: Optional[str] = Query(default=None, description="Filter by trading pair"),
    exchange: Optional[str] = Query(default=None, description="Filter by exchange"),
    current_user: Optional[User] = Depends(optional_auth),
):
    """
    Export current prices to CSV.
    """
    from dashboard import manager
    
    if not manager.engine:
        return Response(
            content="Engine not initialized",
            media_type="text/plain",
            status_code=503,
        )
    
    state = manager.engine.get_state()
    prices = state.get("prices", {})
    
    headers = [
        "timestamp",
        "pair",
        "exchange",
        "bid",
        "ask",
        "mid",
        "spread_percent",
    ]
    
    rows = []
    for pair_name, exchanges in prices.items():
        if pair and pair_name != pair.upper().replace("-", "/"):
            continue
        
        for exch_name, price_data in exchanges.items():
            if exchange and exch_name.lower() != exchange.lower():
                continue
            
            rows.append([
                price_data["timestamp"],
                pair_name,
                exch_name,
                f"{price_data['bid']:.8f}",
                f"{price_data['ask']:.8f}",
                f"{price_data['mid']:.8f}",
                f"{price_data['spread_percent']:.4f}",
            ])
    
    csv_content = generate_csv(headers, rows)
    filename = f"prices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )


@router.get("/trades/csv")
async def export_trades_csv(
    portfolio_id: int = Query(..., description="Portfolio ID"),
    days: int = Query(default=30, ge=1, le=365, description="Days of history"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Export trade history to CSV (requires authentication).
    """
    from src.portfolio.service import portfolio_service
    
    portfolio = portfolio_service.get_portfolio(portfolio_id, current_user.id)
    if not portfolio:
        return Response(
            content="Portfolio not found",
            media_type="text/plain",
            status_code=404,
        )
    
    trades = portfolio_service.get_trades(portfolio_id, limit=10000)
    
    # Filter by date
    cutoff = datetime.now() - timedelta(days=days)
    trades = [t for t in trades if t.timestamp >= cutoff]
    
    headers = [
        "timestamp",
        "pair",
        "side",
        "quantity",
        "price",
        "value_usd",
        "fee",
        "exchange",
        "trade_type",
        "notes",
    ]
    
    rows = []
    for trade in trades:
        rows.append([
            trade.timestamp.isoformat(),
            trade.pair,
            trade.side.value,
            f"{trade.quantity:.8f}",
            f"{trade.price:.8f}",
            f"{trade.value_usd:.2f}",
            f"{trade.fee:.4f}",
            trade.exchange,
            trade.trade_type.value,
            trade.notes or "",
        ])
    
    csv_content = generate_csv(headers, rows)
    filename = f"trades_{portfolio_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )


@router.get("/summary/json")
async def export_summary_json(
    hours: int = Query(default=24, ge=1, le=168),
    current_user: Optional[User] = Depends(optional_auth),
):
    """
    Export system summary as JSON.
    """
    from dashboard import manager
    from engine_metrics import metrics_engine
    
    if not manager.engine:
        return {"error": "Engine not initialized"}
    
    state = manager.engine.get_state()
    
    # Count opportunities
    cutoff = datetime.now() - timedelta(hours=hours)
    recent_opportunities = [
        o for o in manager.engine.history 
        if o.timestamp >= cutoff
    ]
    
    summary = {
        "generated_at": datetime.now().isoformat(),
        "period_hours": hours,
        "exchanges_connected": len(set(
            exch for pair_data in state.get("prices", {}).values()
            for exch in pair_data.keys()
        )),
        "pairs_monitored": len(state.get("prices", {})),
        "opportunities": {
            "total": len(recent_opportunities),
            "avg_profit_percent": sum(o.profit_percent for o in recent_opportunities) / len(recent_opportunities) if recent_opportunities else 0,
            "max_profit_percent": max((o.profit_percent for o in recent_opportunities), default=0),
        },
        "current_opportunities": len(state.get("opportunities", [])),
        "metrics": metrics_engine.get_metrics_summary() if metrics_engine else {},
    }
    
    return summary

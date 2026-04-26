function utcDayBounds(targetDate = new Date()) {
  const year = targetDate.getUTCFullYear();
  const month = targetDate.getUTCMonth();
  const day = targetDate.getUTCDate();
  const start = new Date(Date.UTC(year, month, day, 0, 0, 0, 0));
  const end = new Date(Date.UTC(year, month, day + 1, 0, 0, 0, 0));
  const dateId = start.toISOString().slice(0, 10);
  return {dateId, start, end};
}

function firestoreDate(value) {
  if (!value) {
    return null;
  }
  if (value instanceof Date) {
    return value;
  }
  if (typeof value.toDate === "function") {
    return value.toDate();
  }
  if (typeof value === "string") {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }
  return null;
}

function tradePnlPct(trade) {
  const entry = Number(trade.entry || 0);
  const exit = Number(trade.exit || trade.close_price || 0);
  const side = String(trade.side || "").toUpperCase();
  if (entry > 0 && exit > 0) {
    let directional = ((exit - entry) / entry) * 100;
    if (side === "SELL") {
      directional *= -1;
    }
    return directional;
  }
  const realizedPnl = Number(trade.profit ?? trade.realized_pnl ?? 0);
  const executedQuantity = Number(trade.executed_quantity || 0);
  const executedNotional = Number(trade.executed_notional || (executedQuantity * entry) || 0);
  if (executedNotional > 0) {
    return (realizedPnl / executedNotional) * 100;
  }
  return 0;
}

async function aggregateDailyResultsForDate(db, targetDate = new Date()) {
  const {dateId, start, end} = utcDayBounds(targetDate);
  const snapshot = await db.collection("trades")
      .where("status", "==", "CLOSED")
      .where("closed_at", ">=", start)
      .where("closed_at", "<", end)
      .get();

  let tradesCount = 0;
  let wins = 0;
  let totalPnlPct = 0;

  snapshot.forEach((doc) => {
    const trade = doc.data() || {};
    if (String(trade.status || "").toUpperCase() !== "CLOSED") {
      return;
    }
    const closedAt = firestoreDate(trade.closed_at);
    if (!closedAt || closedAt < start || closedAt >= end) {
      return;
    }
    const pnlPct = tradePnlPct(trade);
    tradesCount += 1;
    totalPnlPct += pnlPct;
    wins += Number(pnlPct > 0);
  });

  return {
    date: dateId,
    total_pnl_pct: Number(totalPnlPct.toFixed(4)),
    win_rate: tradesCount > 0 ? Number((wins / tradesCount).toFixed(4)) : 0,
    trades_count: tradesCount,
    updated_at: start,
  };
}

async function writeDailyResultsSnapshot(db, targetDate = new Date()) {
  const aggregate = await aggregateDailyResultsForDate(db, targetDate);
  await db.collection("daily_results").doc(aggregate.date).set(aggregate, {merge: true});
  return aggregate;
}

module.exports = {
  aggregateDailyResultsForDate,
  tradePnlPct,
  utcDayBounds,
  writeDailyResultsSnapshot,
};

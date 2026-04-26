const test = require("node:test");
const assert = require("node:assert/strict");

const {
  aggregateDailyResultsForDate,
  tradePnlPct,
  utcDayBounds,
} = require("./daily_results");

function createDoc(data) {
  return {
    data() {
      return data;
    },
  };
}

function createTradeQuery(trades) {
  return {
    where() {
      return this;
    },
    get: async () => ({
      forEach(callback) {
        for (const trade of trades) {
          callback(createDoc(trade));
        }
      },
    }),
  };
}

function createDb(trades) {
  return {
    collection(name) {
      assert.equal(name, "trades");
      return createTradeQuery(trades);
    },
  };
}

test("utcDayBounds returns inclusive UTC start and exclusive end", () => {
  const {dateId, start, end} = utcDayBounds(new Date("2026-04-26T18:45:00Z"));

  assert.equal(dateId, "2026-04-26");
  assert.equal(start.toISOString(), "2026-04-26T00:00:00.000Z");
  assert.equal(end.toISOString(), "2026-04-27T00:00:00.000Z");
});

test("tradePnlPct calculates directional pnl for long and short trades", () => {
  assert.equal(tradePnlPct({entry: 100, exit: 110, side: "BUY"}), 10);
  assert.equal(tradePnlPct({entry: 100, exit: 90, side: "SELL"}), 10);
});

test("aggregateDailyResultsForDate aggregates only closed trades inside the UTC day", async () => {
  const targetDate = new Date("2026-04-26T12:00:00Z");
  const db = createDb([
    {status: "CLOSED", closed_at: "2026-04-26T01:00:00Z", entry: 100, exit: 110, side: "BUY"},
    {status: "CLOSED", closed_at: "2026-04-26T20:00:00Z", entry: 200, exit: 190, side: "BUY"},
    {status: "CLOSED", closed_at: "2026-04-27T00:00:00Z", entry: 100, exit: 120, side: "BUY"},
    {status: "OPEN", closed_at: "2026-04-26T05:00:00Z", entry: 100, exit: 105, side: "BUY"},
  ]);

  const aggregate = await aggregateDailyResultsForDate(db, targetDate);

  assert.deepEqual(aggregate, {
    date: "2026-04-26",
    total_pnl_pct: 5,
    win_rate: 0.5,
    trades_count: 2,
    updated_at: new Date("2026-04-26T00:00:00.000Z"),
  });
});

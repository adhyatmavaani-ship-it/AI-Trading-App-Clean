const test = require("node:test");
const assert = require("node:assert/strict");

const {
  buildTradeExecutionPayload,
  executeTradeWithRetry,
  exponentialBackoffMs,
} = require("./execution_client");


function createLogger() {
  return {
    infos: [],
    warnings: [],
    errors: [],
    info(message, context) {
      this.infos.push({message, context});
    },
    warning(message, context) {
      this.warnings.push({message, context});
    },
    error(message, context) {
      this.errors.push({message, context});
    },
  };
}

function createSignal(overrides = {}) {
  return {
    user_id: "alice",
    symbol: "BTCUSDT",
    inference: {
      decision: "BUY",
      trade_probability: 0.82,
    },
    quantity: 0.01,
    order_type: "MARKET",
    reason: "Momentum breakout",
    ...overrides,
  };
}

test("buildTradeExecutionPayload returns normalized execution payload", () => {
  const payload = buildTradeExecutionPayload(createSignal(), "signal-1");

  assert.deepEqual(payload, {
    user_id: "alice",
    symbol: "BTCUSDT",
    side: "BUY",
    quantity: 0.01,
    order_type: "MARKET",
    limit_price: null,
    confidence: 0.82,
    reason: "Momentum breakout",
    signal_id: "signal-1",
  });
});

test("buildTradeExecutionPayload prefers signal.signal_id when present", () => {
  const payload = buildTradeExecutionPayload(createSignal({signal_id: "embedded-1"}), "signal-1");

  assert.equal(payload.signal_id, "embedded-1");
});

test("executeTradeWithRetry does not retry unauthorized responses", async () => {
  const logger = createLogger();
  let fetchCalls = 0;

  const result = await executeTradeWithRetry({
    signal: createSignal(),
    signalId: "signal-1",
    backendExecutorUrl: "https://backend.example.com",
    apiKey: "secret",
    logger,
    fetchImpl: async () => {
      fetchCalls += 1;
      return {
        ok: false,
        status: 401,
        text: async () => "invalid credential",
      };
    },
    delayImpl: async () => {},
  });

  assert.equal(fetchCalls, 1);
  assert.equal(result.status, "unauthorized");
  assert.equal(logger.errors.length, 1);
  assert.equal(logger.warnings.length, 0);
});

test("executeTradeWithRetry retries transient failures and succeeds", async () => {
  const logger = createLogger();
  const delays = [];
  let attempt = 0;

  const result = await executeTradeWithRetry({
    signal: createSignal(),
    signalId: "signal-2",
    backendExecutorUrl: "https://backend.example.com",
    apiKey: "secret",
    logger,
    fetchImpl: async () => {
      attempt += 1;
      if (attempt < 3) {
        return {
          ok: false,
          status: 503,
          text: async () => "temporary outage",
        };
      }
      return {
        ok: true,
        status: 200,
        text: async () => "ok",
      };
    },
    delayImpl: async (ms) => {
      delays.push(ms);
    },
  });

  assert.equal(attempt, 3);
  assert.equal(result.status, "accepted");
  assert.deepEqual(delays, [exponentialBackoffMs(1), exponentialBackoffMs(2)]);
  assert.equal(logger.warnings.length, 2);
  assert.equal(logger.infos.length, 1);
});

test("executeTradeWithRetry returns config error when api key is missing", async () => {
  const logger = createLogger();

  const result = await executeTradeWithRetry({
    signal: createSignal(),
    signalId: "signal-3",
    backendExecutorUrl: "https://backend.example.com",
    apiKey: "",
    logger,
    fetchImpl: async () => {
      throw new Error("fetch should not run");
    },
  });

  assert.equal(result.status, "missing_api_key");
  assert.equal(logger.errors.length, 1);
});

const test = require("node:test");
const assert = require("node:assert/strict");

const {processSignalCreatedEvent} = require("./signal_handler");

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

function createEvent(signalId, signal) {
  return {
    params: {signalId},
    data: {
      data() {
        return signal;
      },
    },
  };
}

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

function createDb() {
  const logs = [];
  return {
    logs,
    collection(name) {
      assert.equal(name, "logs");
      return {
        add: async (payload) => {
          logs.push(payload);
          return {id: `log-${logs.length}`};
        },
      };
    },
  };
}

test("processSignalCreatedEvent triggers backend execution with correct auth context", async () => {
  const logger = createLogger();
  const db = createDb();
  const fetchCalls = [];
  const signal = createSignal();

  const executionResult = await processSignalCreatedEvent(
      createEvent("signal-1", signal),
      {
        backendExecutorUrl: "https://backend.example.com",
        apiKey: "system-secret",
        db,
        logger,
        fetchImpl: async (url, options) => {
          fetchCalls.push({url, options});
          return {
            ok: true,
            status: 200,
            text: async () => "ok",
          };
        },
        executeTradeWithRetry: async ({signal, signalId, backendExecutorUrl, apiKey, logger, fetchImpl}) => {
          return require("./execution_client").executeTradeWithRetry({
            signal,
            signalId,
            backendExecutorUrl,
            apiKey,
            logger,
            fetchImpl,
            delayImpl: async () => {},
          });
        },
        timestampFactory: () => "ts-1",
      },
  );

  assert.equal(executionResult.status, "accepted");
  assert.equal(fetchCalls.length, 1);
  assert.equal(fetchCalls[0].url, "https://backend.example.com/v1/trading/execute");
  assert.equal(fetchCalls[0].options.headers["X-API-Key"], "system-secret");
  assert.equal(fetchCalls[0].options.headers["X-Execution-User-Id"], "alice");
  assert.equal(fetchCalls[0].options.headers["X-Execution-Source"], "cloud-functions");
  assert.equal(JSON.parse(fetchCalls[0].options.body).signal_id, "signal-1");
  assert.equal(db.logs.length, 1);
  assert.equal(db.logs[0].signalId, "signal-1");
  assert.equal(db.logs[0].executionStatus, "accepted");
});

test("processSignalCreatedEvent falls back to embedded signal_id when event param is absent", async () => {
  const logger = createLogger();
  const db = createDb();
  const fetchCalls = [];

  await processSignalCreatedEvent(
      createEvent("", createSignal({signal_id: "embedded-signal-1"})),
      {
        backendExecutorUrl: "https://backend.example.com",
        apiKey: "system-secret",
        db,
        logger,
        fetchImpl: async (url, options) => {
          fetchCalls.push({url, options});
          return {
            ok: true,
            status: 200,
            text: async () => "ok",
          };
        },
        executeTradeWithRetry: async ({signal, signalId, backendExecutorUrl, apiKey, logger, fetchImpl}) => {
          return require("./execution_client").executeTradeWithRetry({
            signal,
            signalId,
            backendExecutorUrl,
            apiKey,
            logger,
            fetchImpl,
            delayImpl: async () => {},
          });
        },
        timestampFactory: () => "ts-fallback",
      },
  );

  assert.equal(JSON.parse(fetchCalls[0].options.body).signal_id, "embedded-signal-1");
  assert.equal(db.logs[0].signalId, "embedded-signal-1");
});

test("processSignalCreatedEvent executes trade once for a single signal event", async () => {
  const logger = createLogger();
  const db = createDb();
  let executionCalls = 0;

  const executionResult = await processSignalCreatedEvent(
      createEvent("signal-2", createSignal()),
      {
        backendExecutorUrl: "https://backend.example.com",
        apiKey: "system-secret",
        db,
        logger,
        fetchImpl: async () => ({
          ok: true,
          status: 200,
          text: async () => "ok",
        }),
        executeTradeWithRetry: async () => {
          executionCalls += 1;
          return {status: "accepted"};
        },
        timestampFactory: () => "ts-2",
      },
  );

  assert.equal(executionResult.status, "accepted");
  assert.equal(executionCalls, 1);
  assert.equal(db.logs.length, 1);
});

test("processSignalCreatedEvent does not execute HOLD signals", async () => {
  const logger = createLogger();
  const db = createDb();
  let executionCalls = 0;

  const executionResult = await processSignalCreatedEvent(
      createEvent("signal-3", createSignal({inference: {decision: "HOLD", trade_probability: 0.2}})),
      {
        backendExecutorUrl: "https://backend.example.com",
        apiKey: "system-secret",
        db,
        logger,
        fetchImpl: async () => {
          throw new Error("fetch should not run");
        },
        executeTradeWithRetry: async () => {
          executionCalls += 1;
          return {status: "accepted"};
        },
        timestampFactory: () => "ts-3",
      },
  );

  assert.equal(executionResult.status, "skipped");
  assert.equal(executionCalls, 0);
  assert.equal(db.logs.length, 1);
  assert.equal(db.logs[0].executionStatus, "skipped");
});

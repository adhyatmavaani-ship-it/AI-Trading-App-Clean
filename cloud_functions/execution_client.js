const DEFAULT_MAX_EXECUTION_RETRIES = 3;
const DEFAULT_RETRYABLE_STATUS_CODES = new Set([408, 409, 425, 429, 500, 502, 503, 504]);

function buildTradeExecutionPayload(signal, signalId) {
  const normalizedSignalId = String(signal.signal_id || signalId || "").trim();
  if (!normalizedSignalId) {
    throw new Error("signal_id is required for trade execution");
  }
  return {
    user_id: signal.user_id || "system",
    symbol: signal.symbol,
    side: signal.inference.decision,
    quantity: signal.quantity || 0.001,
    order_type: signal.order_type || "MARKET",
    limit_price: signal.limit_price || null,
    confidence: signal.inference.trade_probability,
    reason: signal.reason || "Signal-triggered execution",
    signal_id: normalizedSignalId,
  };
}

async function executeTradeWithRetry({
  signal,
  signalId,
  backendExecutorUrl,
  apiKey,
  fetchImpl,
  logger,
  delayImpl = delay,
  timeoutMs = 10000,
  maxExecutionRetries = DEFAULT_MAX_EXECUTION_RETRIES,
  retryableStatusCodes = DEFAULT_RETRYABLE_STATUS_CODES,
}) {
  if (!apiKey) {
    logger.error("Backend API key is not configured", {signalId});
    return {status: "missing_api_key"};
  }
  if (!backendExecutorUrl) {
    logger.error("Backend executor URL is not configured", {signalId});
    return {status: "missing_executor_url"};
  }

  const payload = buildTradeExecutionPayload(signal, signalId);
  const targetUrl = `${backendExecutorUrl}/v1/trading/execute`;

  for (let attempt = 1; attempt <= maxExecutionRetries; attempt += 1) {
    try {
      const response = await fetchWithTimeout(
          targetUrl,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-API-Key": apiKey,
              "X-Execution-Source": "cloud-functions",
              "X-Execution-User-Id": payload.user_id,
            },
            body: JSON.stringify(payload),
          },
          timeoutMs,
          fetchImpl,
      );

      if (response.ok) {
        logger.info("Trade execution request accepted", {
          signalId,
          symbol: signal.symbol,
          status: response.status,
          attempt,
        });
        return {status: "accepted", attempt, responseStatus: response.status};
      }

      const errorBody = await safeReadBody(response);
      if (response.status === 401) {
        logger.error("Backend rejected execution request with 401", {
          signalId,
          symbol: signal.symbol,
          status: response.status,
          body: errorBody,
        });
        return {status: "unauthorized", attempt, responseStatus: response.status};
      }

      if (!retryableStatusCodes.has(response.status) || attempt === maxExecutionRetries) {
        logger.error("Backend execution request failed", {
          signalId,
          symbol: signal.symbol,
          status: response.status,
          attempt,
          body: errorBody,
        });
        return {status: "failed", attempt, responseStatus: response.status};
      }

      logger.warning("Retrying backend execution request", {
        signalId,
        symbol: signal.symbol,
        status: response.status,
        attempt,
      });
    } catch (error) {
      if (attempt === maxExecutionRetries) {
        logger.error("Backend execution request errored", {
          signalId,
          symbol: signal.symbol,
          attempt,
          error: error instanceof Error ? error.message : String(error),
        });
        return {status: "errored", attempt, error: error instanceof Error ? error.message : String(error)};
      }
      logger.warning("Transient backend execution error, retrying", {
        signalId,
        symbol: signal.symbol,
        attempt,
        error: error instanceof Error ? error.message : String(error),
      });
    }

    await delayImpl(exponentialBackoffMs(attempt));
  }

  return {status: "exhausted"};
}

async function fetchWithTimeout(url, options, timeoutMs, fetchImpl = fetch) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetchImpl(url, {
      ...options,
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
  }
}

async function safeReadBody(response) {
  try {
    return await response.text();
  } catch (error) {
    return "";
  }
}

function exponentialBackoffMs(attempt) {
  return Math.min(4000, 250 * (2 ** (attempt - 1)));
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

module.exports = {
  DEFAULT_MAX_EXECUTION_RETRIES,
  DEFAULT_RETRYABLE_STATUS_CODES,
  buildTradeExecutionPayload,
  executeTradeWithRetry,
  fetchWithTimeout,
  safeReadBody,
  exponentialBackoffMs,
  delay,
};

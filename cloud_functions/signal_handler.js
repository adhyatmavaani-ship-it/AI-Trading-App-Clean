async function processSignalCreatedEvent(event, deps) {
  const {
    backendExecutorUrl,
    apiKey,
    db,
    logger,
    executeTradeWithRetry,
    fetchImpl,
    timestampFactory,
  } = deps;

  const signal = normalizeSignalForExecution(event);
  logger.info("Signal created", {signalId: signal.signal_id, symbol: signal?.symbol});

  let executionResult = {status: "skipped"};
  if (backendExecutorUrl && signal?.inference?.decision && signal.inference.decision !== "HOLD") {
    executionResult = await executeTradeWithRetry({
      signal,
      signalId: signal.signal_id,
      backendExecutorUrl,
      apiKey,
      logger,
      fetchImpl,
    });
  }

  await db.collection("logs").add({
    level: "INFO",
    message: "Signal queued for execution",
    signalId: signal.signal_id,
    executionStatus: executionResult.status,
    createdAt: timestampFactory(),
  });

  return executionResult;
}

function normalizeSignalForExecution(event) {
  const rawSignal = event.data.data() || {};
  const signalId = String(event.params.signalId || rawSignal.signal_id || "").trim();
  if (!signalId) {
    throw new Error("Signal event is missing signal_id");
  }
  return {
    ...rawSignal,
    signal_id: signalId,
  };
}

module.exports = {
  normalizeSignalForExecution,
  processSignalCreatedEvent,
};

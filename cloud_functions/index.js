const admin = require("firebase-admin");
const {defineSecret} = require("firebase-functions/params");
const {onDocumentCreated, onDocumentUpdated} = require("firebase-functions/v2/firestore");
const {onRequest} = require("firebase-functions/v2/https");
const {onSchedule} = require("firebase-functions/v2/scheduler");
const logger = require("firebase-functions/logger");
const {executeTradeWithRetry} = require("./execution_client");
const {writeDailyResultsSnapshot} = require("./daily_results");
const {processSignalCreatedEvent} = require("./signal_handler");

admin.initializeApp();
const db = admin.firestore();

const backendApiKey = defineSecret("BACKEND_API_KEY");
const notifyTradeStatusSecret = defineSecret("NOTIFY_TRADE_STATUS_SECRET");
const backendExecutorUrl = process.env.BACKEND_EXECUTOR_URL;

exports.onSignalCreated = onDocumentCreated(
    {
      document: "signals/{signalId}",
      secrets: [backendApiKey],
    },
    async (event) => processSignalCreatedEvent(event, {
      backendExecutorUrl,
      apiKey: backendApiKey.value(),
      db,
      logger,
      executeTradeWithRetry,
      fetchImpl: fetch,
      timestampFactory: () => admin.firestore.FieldValue.serverTimestamp(),
    }),
);

exports.onTradeUpdated = onDocumentUpdated("trades/{tradeId}", async (event) => {
  const before = event.data.before.data();
  const after = event.data.after.data();
  const movedToClosed = before?.status !== "CLOSED" && after?.status === "CLOSED";
  if (!after || !movedToClosed || after.profit === null || after.user_id === undefined || after.pnl_accounted_at) {
    return;
  }

  const tradeRef = event.data.after.ref;
  const performanceRef = db.collection("performance").doc(after.user_id);
  const processed = await db.runTransaction(async (tx) => {
    const tradeSnapshot = await tx.get(tradeRef);
    const currentTrade = tradeSnapshot.exists ? tradeSnapshot.data() : null;
    if (
      !currentTrade ||
      currentTrade.status !== "CLOSED" ||
      currentTrade.profit === null ||
      currentTrade.user_id === undefined ||
      currentTrade.pnl_accounted_at
    ) {
      return false;
    }

    const snapshot = await tx.get(performanceRef);
    const current = snapshot.exists ? snapshot.data() : {realizedPnl: 0, trades: 0};
    tx.set(performanceRef, {
      realizedPnl: (current.realizedPnl || 0) + currentTrade.profit,
      trades: (current.trades || 0) + 1,
      updatedAt: admin.firestore.FieldValue.serverTimestamp(),
    }, {merge: true});
    tx.set(tradeRef, {
      pnl_accounted_at: admin.firestore.FieldValue.serverTimestamp(),
    }, {merge: true});
    return true;
  });

  if (!processed) {
    return;
  }

  await db.collection("training_samples").doc(event.params.tradeId).set({
    sample_id: event.params.tradeId,
    trade_id: event.params.tradeId,
    user_id: after.user_id,
    symbol: after.symbol,
    features: after.features || {},
    probability_features: after.trade_probability_features || {
      trend_strength: after.features?.trend_strength || 0,
      rsi: after.features?.rsi || after.features?.["15m_rsi"] || after.features?.["5m_rsi"] || 50,
      breakout_strength: after.features?.breakout_strength || after.features?.strategy_confidence || 0,
      volume: after.features?.volume || after.features?.["15m_volume"] || after.features?.["5m_volume"] || 0,
    },
    confidence: after.ai_confidence,
    outcome: after.profit > 0 ? 1.0 : 0.0,
    realized_pnl: after.profit,
    expected_return: after.expected_return || null,
    expected_risk: after.expected_risk || null,
    updatedAt: admin.firestore.FieldValue.serverTimestamp(),
  }, {merge: true});
});

exports.notifyTradeStatus = onRequest(
    {
      secrets: [notifyTradeStatusSecret],
    },
    async (req, res) => {
      const providedSecret = req.get("X-Notify-Secret") || req.get("Authorization") || "";
      const expectedSecret = notifyTradeStatusSecret.value();
      const normalizedSecret = providedSecret.startsWith("Bearer ") ? providedSecret.slice(7).trim() : providedSecret.trim();

      if (!expectedSecret || normalizedSecret !== expectedSecret) {
        logger.warning("Unauthorized notification request", {
          ip: req.ip,
          userAgent: req.get("User-Agent") || "unknown",
        });
        res.status(401).json({error: "unauthorized"});
        return;
      }

      const {userId, title, body} = req.body;
      logger.info("Notification request", {userId, title});
      await db.collection("logs").add({
        level: "INFO",
        message: "Notification emitted",
        userId,
        title,
        body,
        createdAt: admin.firestore.FieldValue.serverTimestamp(),
      });
      res.json({status: "queued"});
    },
);

exports.aggregateDailyResults = onSchedule(
    {
      schedule: "5 0 * * *",
      timeZone: "Etc/UTC",
      retryCount: 0,
    },
    async () => {
      const yesterday = new Date();
      yesterday.setUTCDate(yesterday.getUTCDate() - 1);
      const aggregate = await writeDailyResultsSnapshot(db, yesterday);
      logger.info("Daily results snapshot updated", aggregate);
    },
);

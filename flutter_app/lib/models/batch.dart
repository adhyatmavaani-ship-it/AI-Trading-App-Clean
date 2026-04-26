class BatchModel {
  const BatchModel({
    required this.aggregateId,
    required this.exchangeOrderId,
    required this.symbol,
    required this.side,
    required this.status,
    required this.requestedQuantity,
    required this.executedQuantity,
    required this.remainingQuantity,
    required this.intentCount,
    required this.allocationCount,
    required this.retryCount,
    required this.feePaid,
    required this.executedPrice,
    required this.updatedAt,
  });

  final String aggregateId;
  final String? exchangeOrderId;
  final String symbol;
  final String side;
  final String status;
  final double requestedQuantity;
  final double executedQuantity;
  final double remainingQuantity;
  final int intentCount;
  final int allocationCount;
  final int retryCount;
  final double feePaid;
  final double executedPrice;
  final DateTime updatedAt;

  double get fillRatio =>
      requestedQuantity == 0 ? 0 : executedQuantity / requestedQuantity;

  factory BatchModel.fromJson(Map<String, dynamic> json) {
    return BatchModel(
      aggregateId: json['aggregate_id'] as String? ?? '',
      exchangeOrderId: json['exchange_order_id'] as String?,
      symbol: json['symbol'] as String? ?? '',
      side: json['side'] as String? ?? '',
      status: json['status'] as String? ?? 'UNKNOWN',
      requestedQuantity: (json['requested_quantity'] ?? 0).toDouble(),
      executedQuantity: (json['executed_quantity'] ?? 0).toDouble(),
      remainingQuantity: (json['remaining_quantity'] ?? 0).toDouble(),
      intentCount: (json['intent_count'] as num?)?.toInt() ?? 0,
      allocationCount: (json['allocation_count'] as num?)?.toInt() ?? 0,
      retryCount: (json['retry_count'] as num?)?.toInt() ?? 0,
      feePaid: (json['fee_paid'] ?? 0).toDouble(),
      executedPrice: (json['executed_price'] ?? 0).toDouble(),
      updatedAt: DateTime.tryParse(json['updated_at'] as String? ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0),
    );
  }
}

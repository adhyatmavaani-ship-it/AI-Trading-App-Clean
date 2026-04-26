import 'package:flutter/material.dart';

import '../models/batch.dart';

class BatchTile extends StatelessWidget {
  const BatchTile({
    super.key,
    required this.batch,
  });

  final BatchModel batch;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      title: Text('${batch.symbol} • ${batch.side}'),
      subtitle: Text(
        'Batch ${batch.aggregateId.substring(0, 8)} • ${batch.intentCount} intents',
      ),
      trailing: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: <Widget>[
          Text(batch.status),
          Text('${(batch.fillRatio * 100).toStringAsFixed(0)}% filled'),
        ],
      ),
    );
  }
}

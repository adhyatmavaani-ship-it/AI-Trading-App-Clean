import 'dart:ui' as ui;

import 'package:flutter/rendering.dart';
import 'package:share_plus/share_plus.dart';

class ShareCardService {
  const ShareCardService();

  Future<void> sharePerformanceCard({
    required RenderRepaintBoundary boundary,
    required String message,
    String fileName = 'ai_crypto_pulse_performance.png',
  }) async {
    final image = await boundary.toImage(pixelRatio: 3);
    final byteData = await image.toByteData(format: ui.ImageByteFormat.png);
    if (byteData == null) {
      throw StateError('Unable to render performance card.');
    }
    final bytes = byteData.buffer.asUint8List();
    await Share.shareXFiles(
      <XFile>[
        XFile.fromData(
          bytes,
          mimeType: 'image/png',
          name: fileName,
        ),
      ],
      text: message,
      fileNameOverrides: <String>[fileName],
    );
  }
}

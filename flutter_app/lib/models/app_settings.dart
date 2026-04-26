class AppSettings {
  const AppSettings({
    this.riskSlider = 0.6,
    this.autoplayEnabled = true,
    this.notificationsEnabled = true,
    this.hasStoredApiKey = false,
  });

  final double riskSlider;
  final bool autoplayEnabled;
  final bool notificationsEnabled;
  final bool hasStoredApiKey;

  AppSettings copyWith({
    double? riskSlider,
    bool? autoplayEnabled,
    bool? notificationsEnabled,
    bool? hasStoredApiKey,
  }) {
    return AppSettings(
      riskSlider: riskSlider ?? this.riskSlider,
      autoplayEnabled: autoplayEnabled ?? this.autoplayEnabled,
      notificationsEnabled: notificationsEnabled ?? this.notificationsEnabled,
      hasStoredApiKey: hasStoredApiKey ?? this.hasStoredApiKey,
    );
  }
}

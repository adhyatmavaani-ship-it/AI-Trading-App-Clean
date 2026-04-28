class AppSettings {
  const AppSettings({
    this.riskSlider = 0.6,
    this.riskLevel = 'medium',
    this.engineEnabled = true,
    this.learningFrozen = false,
    this.autoplayEnabled = true,
    this.notificationsEnabled = true,
    this.hasStoredApiKey = false,
  });

  final double riskSlider;
  final String riskLevel;
  final bool engineEnabled;
  final bool learningFrozen;
  final bool autoplayEnabled;
  final bool notificationsEnabled;
  final bool hasStoredApiKey;

  AppSettings copyWith({
    double? riskSlider,
    String? riskLevel,
    bool? engineEnabled,
    bool? learningFrozen,
    bool? autoplayEnabled,
    bool? notificationsEnabled,
    bool? hasStoredApiKey,
  }) {
    return AppSettings(
      riskSlider: riskSlider ?? this.riskSlider,
      riskLevel: riskLevel ?? this.riskLevel,
      engineEnabled: engineEnabled ?? this.engineEnabled,
      learningFrozen: learningFrozen ?? this.learningFrozen,
      autoplayEnabled: autoplayEnabled ?? this.autoplayEnabled,
      notificationsEnabled: notificationsEnabled ?? this.notificationsEnabled,
      hasStoredApiKey: hasStoredApiKey ?? this.hasStoredApiKey,
    );
  }
}

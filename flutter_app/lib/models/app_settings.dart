class AppSettings {
  const AppSettings({
    this.riskLevel = 'medium',
    this.engineEnabled = true,
    this.learningFrozen = false,
    this.hasStoredApiKey = false,
  });

  final String riskLevel;
  final bool engineEnabled;
  final bool learningFrozen;
  final bool hasStoredApiKey;

  AppSettings copyWith({
    String? riskLevel,
    bool? engineEnabled,
    bool? learningFrozen,
    bool? hasStoredApiKey,
  }) {
    return AppSettings(
      riskLevel: riskLevel ?? this.riskLevel,
      engineEnabled: engineEnabled ?? this.engineEnabled,
      learningFrozen: learningFrozen ?? this.learningFrozen,
      hasStoredApiKey: hasStoredApiKey ?? this.hasStoredApiKey,
    );
  }
}

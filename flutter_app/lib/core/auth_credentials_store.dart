import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

enum AuthScheme { apiKey, bearer }

class AuthSession {
  const AuthSession({
    required this.accessToken,
    this.refreshToken,
    this.scheme = AuthScheme.apiKey,
    this.expiresAt,
  });

  final String accessToken;
  final String? refreshToken;
  final AuthScheme scheme;
  final DateTime? expiresAt;

  bool get hasRefreshToken =>
      refreshToken != null && refreshToken!.trim().isNotEmpty;

  bool get isExpired {
    final expiresAtValue = expiresAt;
    if (expiresAtValue == null) {
      return false;
    }
    return !expiresAtValue.isAfter(DateTime.now().toUtc());
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'accessToken': accessToken,
      'refreshToken': refreshToken,
      'scheme': scheme.name,
      'expiresAt': expiresAt?.toUtc().toIso8601String(),
    };
  }

  factory AuthSession.fromJson(Map<String, dynamic> json) {
    return AuthSession(
      accessToken: json['accessToken'] as String? ?? '',
      refreshToken: json['refreshToken'] as String?,
      scheme: _schemeFromString(json['scheme'] as String?),
      expiresAt: _parseDateTime(json['expiresAt'] as String?),
    );
  }

  static AuthScheme _schemeFromString(String? value) {
    return value == AuthScheme.bearer.name
        ? AuthScheme.bearer
        : AuthScheme.apiKey;
  }

  static DateTime? _parseDateTime(String? value) {
    if (value == null || value.isEmpty) {
      return null;
    }
    return DateTime.tryParse(value)?.toUtc();
  }
}

class AuthCredentialsStore {
  AuthCredentialsStore({FlutterSecureStorage? storage})
      : _storage = storage ??
            const FlutterSecureStorage(
              aOptions: AndroidOptions(encryptedSharedPreferences: true),
              iOptions: IOSOptions(
                accessibility: KeychainAccessibility.first_unlock,
              ),
            );

  static const String _sessionKey = 'auth_session';
  final FlutterSecureStorage _storage;

  Future<AuthSession?> loadSession() async {
    final raw = await _storage.read(key: _sessionKey);
    if (raw == null || raw.isEmpty) {
      return null;
    }
    try {
      final decoded = jsonDecode(raw) as Map<String, dynamic>;
      final session = AuthSession.fromJson(decoded);
      if (session.accessToken.trim().isEmpty) {
        return null;
      }
      return session;
    } on FormatException {
      await clear();
      return null;
    }
  }

  Future<void> saveSession(AuthSession session) async {
    await _storage.write(
      key: _sessionKey,
      value: jsonEncode(session.toJson()),
    );
  }

  Future<void> saveApiKey(
    String apiKey, {
    AuthScheme scheme = AuthScheme.apiKey,
    DateTime? expiresAt,
  }) async {
    final normalized = apiKey.trim();
    if (normalized.isEmpty) {
      await clear();
      return;
    }
    await saveSession(
      AuthSession(
        accessToken: normalized,
        scheme: scheme,
        expiresAt: expiresAt?.toUtc(),
      ),
    );
  }

  Future<void> clear() async {
    await _storage.delete(key: _sessionKey);
  }
}

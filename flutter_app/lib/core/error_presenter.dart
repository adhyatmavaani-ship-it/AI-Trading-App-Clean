import 'error_mapper.dart';

String userMessageForError(
  Object? error, {
  String fallback = 'Something went wrong. Please try again.',
}) {
  return ErrorMapper.map(error, fallback: fallback);
}

import 'dart:io';
import 'dart:typed_data';

Future<void> saveDownloadPlatform(List<int> bytes, String filename) async {
  final downloads = Directory(
    '${Platform.environment['USERPROFILE'] ?? Platform.environment['HOME'] ?? '.'}${Platform.pathSeparator}Downloads',
  );
  if (!downloads.existsSync()) downloads.createSync(recursive: true);
  await File(
    '${downloads.path}${Platform.pathSeparator}$filename',
  ).writeAsBytes(Uint8List.fromList(bytes));
}

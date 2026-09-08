import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../services/auth_service.dart';
import 'home_shell.dart';
import 'LandingPage.dart';

/// Brand palette kept in one place so every screen stays visually consistent.
class Brand {
  static const primary = Color(0xff245c58);
  static const primaryDark = Color(0xff153a37);
  static const accent = Color(0xffe8a33d);
  static const background = Color(0xfff7f8f5);
  static const surface = Colors.white;
  static const danger = Color(0xffb3261e);
}

class AcademicSecondBrainApp extends StatefulWidget {
  const AcademicSecondBrainApp({super.key});

  @override
  State<AcademicSecondBrainApp> createState() => _AcademicSecondBrainAppState();
}

class _AcademicSecondBrainAppState extends State<AcademicSecondBrainApp> {
  late final ApiService api;
  late final AuthController auth;
  bool _restoring = true;

  @override
  void initState() {
    super.initState();
    const configuredBaseUrl = String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://127.0.0.1:8000',
    );
    api = ApiService(baseUrl: configuredBaseUrl);
    auth = AuthController(api);
    // Harmless no-op if there is no persisted access token yet; kept so a
    // future persistence layer (secure storage) can restore a session
    // without any other screen needing to change.
    auth.restore().whenComplete(() {
      if (!mounted) return;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) setState(() => _restoring = false);
      });
    });
  }

  @override
  void dispose() {
    auth.dispose();
    super.dispose();
  }

  ThemeData _buildTheme() {
    final scheme = ColorScheme.fromSeed(
      seedColor: Brand.primary,
      brightness: Brightness.light,
    ).copyWith(primary: Brand.primary, secondary: Brand.accent);

    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: Brand.background,
      textTheme: const TextTheme().apply(
        bodyColor: const Color(0xff1c211f),
        displayColor: const Color(0xff11201e),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Brand.background,
        foregroundColor: Color(0xff11201e),
        elevation: 0,
        scrolledUnderElevation: 1,
        centerTitle: false,
      ),
      inputDecorationTheme: InputDecorationTheme(
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xffd8ded9)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Brand.primary, width: 1.6),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Brand.danger),
        ),
        filled: true,
        fillColor: Colors.white,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 14,
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: Brand.primary,
          foregroundColor: Colors.white,
          minimumSize: const Size(0, 50),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(0, 50),
          foregroundColor: Brand.primary,
          side: const BorderSide(color: Brand.primary, width: 1.4),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(foregroundColor: Brand.primary),
      ),
      cardTheme: CardThemeData(
        margin: EdgeInsets.zero,
        elevation: 0,
        color: Brand.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: Color(0xffe6e9e5)),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
      dividerTheme: const DividerThemeData(color: Color(0xffe6e9e5)),
    );
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: auth,
    builder: (context, _) => MaterialApp(
      title: 'Academic Second Brain',
      debugShowCheckedModeBanner: false,
      theme: _buildTheme(),
      home: _restoring
          ? const _SplashScreen()
          : (auth.isAuthenticated
                ? HomeShell(auth: auth)
                : LandingPage(auth: auth)),
    ),
  );
}

class _SplashScreen extends StatelessWidget {
  const _SplashScreen();

  @override
  Widget build(BuildContext context) => const Scaffold(
    backgroundColor: Brand.background,
    body: Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.menu_book_rounded, size: 40, color: Brand.primary),
          SizedBox(height: 16),
          SizedBox(
            width: 22,
            height: 22,
            child: CircularProgressIndicator(strokeWidth: 2.4),
          ),
        ],
      ),
    ),
  );
}

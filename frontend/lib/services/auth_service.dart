import 'package:flutter/foundation.dart';

import '../models/user.dart';
import 'api_service.dart';

class AuthController extends ChangeNotifier {
  AuthController(this.api);

  final ApiService api;
  User? user;
  bool busy = false;
  String? error;

  bool get isAuthenticated => user != null && api.accessToken != null;
  bool get isAdmin => user?.role == 'admin';

  Future<bool> login(String email, String password) async {
    return _run(() async {
      final result = await api.login(email.trim(), password);
      user = result.user;
    });
  }

  Future<bool> signup(Map<String, dynamic> fields) async {
    return _run(() async {
      final result = await api.signup(fields);
      user = result.user;
    });
  }

  Future<bool> restore() async {
    if (api.accessToken == null) return false;
    return _run(() async => user = await api.me());
  }

  Future<void> logout() async {
    await api.logout();
    user = null;
    notifyListeners();
  }

  Future<bool> _run(Future<void> Function() action) async {
    busy = true;
    error = null;
    notifyListeners();
    try {
      await action();
      return true;
    } on ApiException catch (exception) {
      error = exception.message;
      return false;
    } catch (exception) {
      error =
          'Could not connect to the API. Check that the backend is running.';
      return false;
    } finally {
      busy = false;
      notifyListeners();
    }
  }
}

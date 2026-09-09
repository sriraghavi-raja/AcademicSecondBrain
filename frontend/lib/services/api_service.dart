import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/user.dart';

class ApiException implements Exception {
  const ApiException(this.message, this.statusCode);

  final String message;
  final int statusCode;

  @override
  String toString() => message;
}

class ApiService {
  ApiService({String? baseUrl})
    : baseUrl = baseUrl ?? 'http://10.234.243.63:8000';

  final String baseUrl;
  String? accessToken;
  String? refreshToken;
  Future<bool>? _refreshing;

  Uri _uri(String path) => Uri.parse('$baseUrl$path');

  Future<dynamic> _request(
    String method,
    String path, {
    Map<String, dynamic>? body,
    bool authenticated = true,
    bool retry = true,
  }) async {
    final headers = <String, String>{'Content-Type': 'application/json'};
    if (authenticated && accessToken != null) {
      headers['Authorization'] = 'Bearer $accessToken';
    }
    final encoded = body == null ? null : jsonEncode(body);
    late http.Response response;
    switch (method) {
      case 'GET':
        response = await http.get(_uri(path), headers: headers);
      case 'POST':
        response = await http.post(_uri(path), headers: headers, body: encoded);
      case 'PUT':
        response = await http.put(_uri(path), headers: headers, body: encoded);
      case 'PATCH':
        response = await http.patch(
          _uri(path),
          headers: headers,
          body: encoded,
        );
      case 'DELETE':
        response = await http.delete(
          _uri(path),
          headers: headers,
          body: encoded,
        );
      default:
        throw ApiException('Unsupported HTTP method', 0);
    }
    if (response.statusCode == 401 &&
        authenticated &&
        retry &&
        refreshToken != null) {
      final refreshed = await _refreshOnce();
      if (refreshed) {
        return _request(
          method,
          path,
          body: body,
          authenticated: true,
          retry: false,
        );
      }
    }
    return _parse(response);
  }

  dynamic _parse(http.Response response) {
    if (response.statusCode < 200 || response.statusCode >= 300) {
      var message = 'Request failed (${response.statusCode})';
      try {
        final decoded = jsonDecode(response.body);
        final detail = decoded is Map ? decoded['detail'] : null;
        if (detail is String) message = detail;
      } catch (_) {}
      throw ApiException(message, response.statusCode);
    }
    if (response.body.isEmpty) return null;
    return jsonDecode(response.body);
  }

  Future<bool> _refreshOnce() async {
    _refreshing ??= _performRefresh();
    final refreshed = await _refreshing!;
    _refreshing = null;
    return refreshed;
  }

  Future<bool> _performRefresh() async {
    try {
      final response = await http.post(
        _uri('/api/auth/refresh'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'refresh_token': refreshToken}),
      );
      if (response.statusCode < 200 || response.statusCode >= 300) return false;
      final result = AuthResult.fromJson(jsonDecode(response.body));
      accessToken = result.accessToken;
      refreshToken = result.refreshToken;
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<AuthResult> login(String name, String password) async {
    final json = await _request(
      'POST',
      '/api/auth/login',
      body: {'name': name, 'password': password},
      authenticated: false,
    );
    final result = AuthResult.fromJson(Map<String, dynamic>.from(json));
    accessToken = result.accessToken;
    refreshToken = result.refreshToken;
    return result;
  }

  Future<AuthResult> signup(
    Map<String, dynamic> fields, {
    String? adminKey,
  }) async {
    final headers = <String, String>{'Content-Type': 'application/json'};
    if (adminKey != null && adminKey.trim().isNotEmpty) {
      headers['X-Admin-Signup-Key'] = adminKey.trim();
    }
    final response = await http.post(
      _uri('/api/auth/signup'),
      headers: headers,
      body: jsonEncode(fields),
    );
    final json = _parse(response);
    final result = AuthResult.fromJson(Map<String, dynamic>.from(json));
    accessToken = result.accessToken;
    refreshToken = result.refreshToken;
    return result;
  }

  Future<User> me() async => User.fromJson(
    Map<String, dynamic>.from(await _request('GET', '/api/auth/me')),
  );

  Future<void> logout() async {
    try {
      await _request(
        'POST',
        '/api/auth/logout',
        body: {'refresh_token': refreshToken},
        authenticated: false,
      );
    } finally {
      accessToken = null;
      refreshToken = null;
    }
  }

  Future<dynamic> get(String path) => _request('GET', path);
  Future<dynamic> post(String path, Map<String, dynamic> body) =>
      _request('POST', path, body: body);
  Future<dynamic> put(String path, Map<String, dynamic> body) =>
      _request('PUT', path, body: body);
  Future<dynamic> patch(String path, Map<String, dynamic> body) =>
      _request('PATCH', path, body: body);
  Future<dynamic> delete(String path) => _request('DELETE', path);

  Future<List<dynamic>> listChatSessions() async =>
      List<dynamic>.from(await get('/api/chat/sessions') as List);

  Future<List<dynamic>> chatHistory(String sessionId) async =>
      List<dynamic>.from(
        await get('/api/chat/history/${Uri.encodeComponent(sessionId)}')
            as List,
      );

  Future<void> deleteChatSession(String sessionId) async {
    await delete('/api/chat/session/${Uri.encodeComponent(sessionId)}');
  }

  Future<List<dynamic>> listDocuments() async =>
      List<dynamic>.from(await get('/api/docs') as List);

  Future<Map<String, dynamic>> getProfile() async =>
      Map<String, dynamic>.from(await get('/api/profile') as Map);

  Future<Map<String, dynamic>> saveProfile(
    Map<String, dynamic> profile,
  ) async =>
      Map<String, dynamic>.from(await put('/api/profile', profile) as Map);

  Future<Map<String, dynamic>> careerDashboard() async =>
      Map<String, dynamic>.from(await get('/api/career/dashboard') as Map);

  Future<List<dynamic>> adminUsers() async => List<dynamic>.from(
    (await get('/api/admin/users') as Map)['users'] as List,
  );

  Future<Map<String, dynamic>> updateAdminUserRole(
    String userId,
    String role,
  ) async => Map<String, dynamic>.from(
    await patch('/api/admin/users/$userId/role', {'role': role}) as Map,
  );

  Future<void> deleteAdminUser(String userId) async {
    await delete('/api/admin/users/$userId');
  }

  Future<Map<String, dynamic>> getSkills() async =>
      Map<String, dynamic>.from(await get('/api/skills') as Map);

  Future<Map<String, dynamic>> addSkillEvidence({
    required String rawTerm,
    required String sourceType,
    required String sourceRef,
    required double confidence,
  }) async => Map<String, dynamic>.from(
    await post('/api/skills/evidence', {
          'raw_term': rawTerm,
          'source_type': sourceType,
          'source_ref': sourceRef,
          'confidence': confidence,
        })
        as Map,
  );

  Future<Map<String, dynamic>> syncGithub(String username) async =>
      Map<String, dynamic>.from(
        await post('/api/skills/sync/github', {'github_username': username})
            as Map,
      );

  Future<Map<String, dynamic>> addProject({
    required String title,
    required String techStack,
    required String description,
  }) async => Map<String, dynamic>.from(
    await post('/api/career/projects', {
          'title': title,
          'tech_stack': techStack,
          'description_text': description,
        })
        as Map,
  );

  Future<Map<String, dynamic>> gapAnalysis(String jobDescription) async =>
      Map<String, dynamic>.from(
        await post('/api/career/gap-analysis', {
              'job_description_text': jobDescription,
            })
            as Map,
      );

  Future<Map<String, dynamic>> uploadCertificate(
    String filename,
    List<int> bytes,
  ) async {
    final request = http.MultipartRequest(
      'POST',
      _uri('/api/career/certifications'),
    );
    if (accessToken != null) {
      request.headers['Authorization'] = 'Bearer $accessToken';
    }
    request.files.add(
      http.MultipartFile.fromBytes('file', bytes, filename: filename),
    );
    final response = await http.Response.fromStream(await request.send());
    return Map<String, dynamic>.from(_parse(response) as Map);
  }

  Future<http.Response> generateResume({String? targetRole}) async {
    final response = await _authenticatedResponseWithBody(
      'POST',
      '/api/career/resume',
      {'target_role': targetRole},
    );
    return response;
  }

  Future<Map<String, dynamic>> generateQuiz({
    required String documentId,
    int questionCount = 5,
  }) async => Map<String, dynamic>.from(
    await post('/api/study/quiz', {
          'document_id': documentId,
          'num_questions': questionCount,
        })
        as Map,
  );

  Future<Map<String, dynamic>> submitQuiz(
    List<Map<String, dynamic>> attempts,
  ) async => Map<String, dynamic>.from(
    await post('/api/study/quiz/submit', {'attempts': attempts}) as Map,
  );

  Future<Map<String, dynamic>> weakTopics({double threshold = 0.7}) async =>
      Map<String, dynamic>.from(
        await get('/api/study/weak-topics?threshold=$threshold') as Map,
      );

  Future<Map<String, dynamic>> createStudyPlan({
    required String syllabusId,
    List<Map<String, dynamic>>? weakTopics,
  }) async => Map<String, dynamic>.from(
    await post('/api/study/plan', {
          'syllabus_id': syllabusId,
          'weak_topics': weakTopics,
        })
        as Map,
  );

  Future<Map<String, dynamic>> startInterview({
    required String targetRole,
    String mode = 'technical',
  }) async => Map<String, dynamic>.from(
    await post('/api/career/interview/start', {
          'target_role': targetRole,
          'mode': mode,
        })
        as Map,
  );

  Future<Map<String, dynamic>> continueInterview({
    required String sessionId,
    required String answer,
  }) async => Map<String, dynamic>.from(
    await post('/api/career/interview/continue', {
          'session_id': sessionId,
          'answer': answer,
        })
        as Map,
  );

  Future<Map<String, dynamic>> endInterview(String sessionId) async =>
      Map<String, dynamic>.from(
        await post('/api/career/interview/end', {'session_id': sessionId})
            as Map,
      );

  Future<String> exportStudyPlan(String planId) async {
    final response = await _authenticatedResponse(
      'GET',
      '/api/study/plan/${Uri.encodeComponent(planId)}/export',
    );
    return response.body;
  }

  Future<http.Response> _authenticatedResponse(
    String method,
    String path,
  ) async {
    final headers = <String, String>{};
    if (accessToken != null) headers['Authorization'] = 'Bearer $accessToken';
    final response = method == 'GET'
        ? await http.get(_uri(path), headers: headers)
        : throw ApiException('Unsupported download method', 0);
    if (response.statusCode == 401 && refreshToken != null) {
      final refreshed = await _refreshOnce();
      if (refreshed) return _authenticatedResponse(method, path);
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(
        'Request failed (${response.statusCode})',
        response.statusCode,
      );
    }
    return response;
  }

  Future<http.Response> _authenticatedResponseWithBody(
    String method,
    String path,
    Map<String, dynamic> body,
  ) async {
    final headers = <String, String>{'Content-Type': 'application/json'};
    if (accessToken != null) headers['Authorization'] = 'Bearer $accessToken';
    final response = await http.post(
      _uri(path),
      headers: headers,
      body: jsonEncode(body),
    );
    if (response.statusCode == 401 && refreshToken != null) {
      final refreshed = await _refreshOnce();
      if (refreshed) return _authenticatedResponseWithBody(method, path, body);
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(
        'Request failed (${response.statusCode})',
        response.statusCode,
      );
    }
    return response;
  }

  Future<void> streamChat({
    required String question,
    String? sessionId,
    String? documentId,
    required void Function(String sessionId) onSession,
    required void Function(String token) onToken,
    required void Function(List<dynamic> sources) onSources,
  }) async {
    final request = http.Request('POST', _uri('/chat'));
    request.headers['Content-Type'] = 'application/json';
    if (accessToken != null) {
      request.headers['Authorization'] = 'Bearer $accessToken';
    }
    request.body = jsonEncode({
      'question': question,
      'session_id': sessionId,
      'document_id': documentId,
    });
    final response = await http.Client().send(request);
    if (response.statusCode == 401 && refreshToken != null) {
      final refreshed = await _refreshOnce();
      if (refreshed) {
        return streamChat(
          question: question,
          sessionId: sessionId,
          documentId: documentId,
          onSession: onSession,
          onToken: onToken,
          onSources: onSources,
        );
      }
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(
        'Chat request failed (${response.statusCode})',
        response.statusCode,
      );
    }
    var buffer = '';
    await for (final chunk in response.stream.transform(utf8.decoder)) {
      buffer += chunk;
      final events = buffer.split('\n\n');
      buffer = events.removeLast();
      for (final event in events) {
        final data = event
            .split('\n')
            .where((line) => line.startsWith('data:'))
            .map((line) => line.substring(5).trim())
            .join();
        if (data.isEmpty || data == '[DONE]') continue;
        final payload = jsonDecode(data);
        switch (payload['type']) {
          case 'session':
            onSession(payload['session_id'] as String);
          case 'token':
            onToken(payload['content'] as String);
          case 'sources':
            onSources(List<dynamic>.from(payload['sources'] as List));
        }
      }
    }
  }

  Future<dynamic> uploadDocument(String filename, List<int> bytes) async {
    final request = http.MultipartRequest('POST', _uri('/api/docs/upload'));
    if (accessToken != null) {
      request.headers['Authorization'] = 'Bearer $accessToken';
    }
    request.files.add(
      http.MultipartFile.fromBytes('file', bytes, filename: filename),
    );
    final response = await http.Response.fromStream(await request.send());
    return _parse(response);
  }
}

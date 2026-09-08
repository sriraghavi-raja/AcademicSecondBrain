class User {
  const User({
    required this.id,
    required this.name,
    required this.email,
    required this.role,
    this.collegeName = '',
    this.collegeYear = '',
  });

  final String id;
  final String name;
  final String email;
  final String role;
  final String collegeName;
  final String collegeYear;

  factory User.fromJson(Map<String, dynamic> json) => User(
    id: '${json['user_id'] ?? json['id'] ?? ''}',
    name: '${json['name'] ?? json['full_name'] ?? ''}',
    email: '${json['email'] ?? ''}',
    role: '${json['role'] ?? 'student'}',
    collegeName: '${json['college_name'] ?? ''}',
    collegeYear: '${json['college_year'] ?? ''}',
  );
}

class AuthResult {
  const AuthResult({
    required this.accessToken,
    required this.refreshToken,
    required this.user,
  });

  final String accessToken;
  final String refreshToken;
  final User user;

  factory AuthResult.fromJson(Map<String, dynamic> json) => AuthResult(
    accessToken: '${json['access_token'] ?? ''}',
    refreshToken: '${json['refresh_token'] ?? ''}',
    user: User.fromJson(Map<String, dynamic>.from(json['user'] as Map? ?? {})),
  );
}

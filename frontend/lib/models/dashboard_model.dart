class DashboardModel {
  const DashboardModel({
    required this.studentId,
    this.profile,
    required this.summary,
    required this.skills,
    required this.weakTopics,
    required this.achievements,
    required this.projects,
    required this.lastRuns,
  });

  final String studentId;
  final DashboardProfile? profile;
  final DashboardSummary summary;
  final List<DashboardSkill> skills;
  final List<WeakTopic> weakTopics;
  final List<DashboardAchievement> achievements;
  final List<DashboardProject> projects;
  final Map<String, CareerRun> lastRuns;

  factory DashboardModel.fromJson(Map<String, dynamic> json) {
    final rawRuns = json['last_runs'];
    final runs = <String, CareerRun>{};
    if (rawRuns is Map) {
      for (final entry in rawRuns.entries) {
        if (entry.value is Map) {
          runs['${entry.key}'] = CareerRun.fromJson(
            Map<String, dynamic>.from(entry.value as Map),
          );
        }
      }
    }
    return DashboardModel(
      studentId: _string(json['student_id']),
      profile: json['profile'] is Map
          ? DashboardProfile.fromJson(
              Map<String, dynamic>.from(json['profile'] as Map),
            )
          : null,
      summary: DashboardSummary.fromJson(_map(json['summary'])),
      skills: _list(json['skills'])
          .whereType<Map>()
          .map((item) => DashboardSkill.fromJson(Map<String, dynamic>.from(item)))
          .toList(),
      weakTopics: _list(json['weak_topics'])
          .whereType<Map>()
          .map((item) => WeakTopic.fromJson(Map<String, dynamic>.from(item)))
          .where((topic) => topic.accuracy < 0.7)
          .toList(),
      achievements: _list(json['achievements'])
          .whereType<Map>()
          .map((item) => DashboardAchievement.fromJson(Map<String, dynamic>.from(item)))
          .toList(),
      projects: _list(json['projects'])
          .whereType<Map>()
          .map((item) => DashboardProject.fromJson(Map<String, dynamic>.from(item)))
          .toList(),
      lastRuns: runs,
    );
  }
}

class DashboardProfile {
  const DashboardProfile({this.studentId = '', this.name = '', this.email = ''});
  final String studentId;
  final String name;
  final String email;

  factory DashboardProfile.fromJson(Map<String, dynamic> json) => DashboardProfile(
    studentId: _string(json['student_id']),
    name: _string(json['name'] ?? json['full_name']),
    email: _string(json['email']),
  );
}

class DashboardSummary {
  const DashboardSummary({
    this.skillCount = 0,
    this.studyTopicCount = 0,
    this.projectCount = 0,
    this.achievementCount = 0,
    this.weakTopicCount = 0,
  });
  final int skillCount;
  final int studyTopicCount;
  final int projectCount;
  final int achievementCount;
  final int weakTopicCount;

  factory DashboardSummary.fromJson(Map<String, dynamic> json) => DashboardSummary(
    skillCount: _int(json['skill_count']),
    studyTopicCount: _int(json['study_topic_count']),
    projectCount: _int(json['project_count']),
    achievementCount: _int(json['achievement_count']),
    weakTopicCount: _int(json['weak_topic_count']),
  );
}

class DashboardSkill {
  const DashboardSkill({
    this.name = 'Untitled skill',
    this.type = '',
    this.confidence = 0,
    this.evidenceCount = 0,
    this.lastEvidenceAt,
    required this.trend,
  });
  final String name;
  final String type;
  final double confidence;
  final int evidenceCount;
  final String? lastEvidenceAt;
  final List<ConfidencePoint> trend;

  bool get isStudyTopic => type == 'study_topic';

  factory DashboardSkill.fromJson(Map<String, dynamic> json) {
    final rawTrend = _list(json['confidence_trend']);
    return DashboardSkill(
      name: _string(json['skill_name'], fallback: 'Untitled skill'),
      type: _string(json['skill_type']),
      confidence: _ratio(json['confidence']),
      evidenceCount: _int(json['evidence_count']),
      lastEvidenceAt: _nullableString(json['last_evidence_at']),
      trend: rawTrend
          .whereType<Map>()
          .map((item) => ConfidencePoint.fromJson(Map<String, dynamic>.from(item)))
          .toList(),
    );
  }
}

class ConfidencePoint {
  const ConfidencePoint({this.confidence = 0, this.recordedAt});
  final double confidence;
  final String? recordedAt;

  factory ConfidencePoint.fromJson(Map<String, dynamic> json) => ConfidencePoint(
    confidence: _ratio(json['confidence']),
    recordedAt: _nullableString(json['recorded_at']),
  );
}

class WeakTopic {
  const WeakTopic({this.name = 'Untitled topic', this.attempts = 0, this.accuracy = 0, this.lastAnsweredAt});
  final String name;
  final int attempts;
  final double accuracy;
  final String? lastAnsweredAt;

  factory WeakTopic.fromJson(Map<String, dynamic> json) => WeakTopic(
    name: _string(json['concept_tag'], fallback: 'Untitled topic'),
    attempts: _int(json['attempts'] ?? json['attempt_count']),
    accuracy: _ratio(json['accuracy']),
    lastAnsweredAt: _nullableString(json['last_answered_at']),
  );
}

class DashboardAchievement {
  const DashboardAchievement({this.name = 'Achievement', this.description = '', this.awardedAt});
  final String name;
  final String description;
  final String? awardedAt;

  factory DashboardAchievement.fromJson(Map<String, dynamic> json) => DashboardAchievement(
    name: _string(json['name'], fallback: 'Achievement'),
    description: _string(json['description']),
    awardedAt: _nullableString(json['awarded_at']),
  );
}

class DashboardProject {
  const DashboardProject({this.title = 'Untitled project', this.techStack = '', this.sourceType = '', this.sourceRef});
  final String title;
  final String techStack;
  final String sourceType;
  final String? sourceRef;

  factory DashboardProject.fromJson(Map<String, dynamic> json) => DashboardProject(
    title: _string(json['title'], fallback: 'Untitled project'),
    techStack: _string(json['tech_stack']),
    sourceType: _string(json['source_type']),
    sourceRef: _nullableString(json['source_ref']),
  );
}

class CareerRun {
  const CareerRun({this.createdAt, this.summary = const {}});
  final String? createdAt;
  final Map<String, dynamic> summary;

  factory CareerRun.fromJson(Map<String, dynamic> json) => CareerRun(
    createdAt: _nullableString(json['created_at']),
    summary: _map(json['summary']),
  );
}

Map<String, dynamic> _map(dynamic value) => value is Map ? Map<String, dynamic>.from(value) : <String, dynamic>{};
List<dynamic> _list(dynamic value) => value is List ? value : const [];
String _string(dynamic value, {String fallback = ''}) => value?.toString().trim().isNotEmpty == true ? value.toString() : fallback;
String? _nullableString(dynamic value) => value == null || value.toString().trim().isEmpty ? null : value.toString();
int _int(dynamic value) => value is num ? value.toInt() : int.tryParse('$value') ?? 0;
double _ratio(dynamic value) => ((value is num ? value.toDouble() : double.tryParse('$value') ?? 0).clamp(0, 1)).toDouble();

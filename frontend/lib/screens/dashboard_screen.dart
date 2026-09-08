import 'package:flutter/material.dart';

import '../models/dashboard_model.dart';
import '../services/api_service.dart';
import '../services/dashboard_service.dart';
import 'app.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({required this.api, required this.studentId, required this.fallbackName, super.key});

  final ApiService api;
  final String studentId;
  final String fallbackName;

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  late final DashboardService service = DashboardService(widget.api);
  DashboardModel? dashboard;
  String? error;
  bool loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final result = await service.getDashboard(widget.studentId);
      if (mounted) setState(() => dashboard = result);
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } catch (_) {
      if (mounted) setState(() => error = 'Please check your connection and try again.');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (loading && dashboard == null) return const _DashboardLoading();
    if (error != null && dashboard == null) {
      return _DashboardError(message: error!, onRetry: _load);
    }
    final data = dashboard!;
    final profileName = data.profile?.name.trim().isNotEmpty == true
        ? data.profile!.name
        : widget.fallbackName;
    final taxonomy = data.skills.where((skill) => !skill.isStudyTopic).toList();
    final studyTopics = data.skills.where((skill) => skill.isStudyTopic).toList();

    return RefreshIndicator(
      onRefresh: _load,
      color: Brand.primary,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(0, 4, 0, 30),
        children: [
          _DashboardHeader(name: profileName),
          const SizedBox(height: 22),
          _CareerSnapshotCard(summary: data.summary),
          const SizedBox(height: 22),
          _SectionTitle(title: 'Your signals', caption: 'A quick read on the work behind your profile'),
          const SizedBox(height: 12),
          _SummaryGrid(summary: data.summary),
          const SizedBox(height: 26),
          _SectionTitle(title: 'Your skills', caption: 'Confidence backed by evidence and learning activity'),
          const SizedBox(height: 12),
          _SkillsSection(
            title: 'Technical skills',
            skills: taxonomy,
            emptyText: 'No skills tracked yet.',
            onSkillTap: _showSkillDetails,
          ),
          const SizedBox(height: 12),
          _SkillsSection(
            title: 'Study topics',
            skills: studyTopics,
            emptyText: 'No study topics tracked yet.',
            onSkillTap: _showSkillDetails,
          ),
          const SizedBox(height: 26),
          _WeakTopicsSection(topics: data.weakTopics),
          const SizedBox(height: 26),
          _AchievementsSection(achievements: data.achievements),
          const SizedBox(height: 26),
          _ProjectsSection(projects: data.projects),
          const SizedBox(height: 26),
          _CareerRunsSection(runs: data.lastRuns),
          if (error != null) ...[
            const SizedBox(height: 12),
            Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ],
        ],
      ),
    );
  }

  void _showSkillDetails(DashboardSkill skill) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => _SkillDetails(skill: skill),
    );
  }
}

class _DashboardHeader extends StatelessWidget {
  const _DashboardHeader({required this.name});
  final String name;

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${_greeting()}, ${name.isEmpty ? 'there' : name.split(' ').first} 👋',
              style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                fontWeight: FontWeight.w800,
                color: Brand.primaryDark,
              ),
            ),
            const SizedBox(height: 6),
            const Text('Here is your career readiness snapshot.', style: TextStyle(color: Colors.black54)),
          ],
        ),
      ),
      const CircleAvatar(
        radius: 18,
        backgroundColor: Color(0xffe5f0ec),
        child: Icon(Icons.person_outline_rounded, color: Brand.primary),
      ),
    ],
  );

  String _greeting() {
    final hour = DateTime.now().hour;
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  }
}

class _CareerSnapshotCard extends StatelessWidget {
  const _CareerSnapshotCard({required this.summary});
  final DashboardSummary summary;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(22),
    decoration: BoxDecoration(
      gradient: const LinearGradient(
        colors: [Brand.primaryDark, Brand.primary],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ),
      borderRadius: BorderRadius.circular(22),
      boxShadow: [BoxShadow(color: Brand.primary.withValues(alpha: .18), blurRadius: 24, offset: const Offset(0, 10))],
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(color: Colors.white.withValues(alpha: .12), shape: BoxShape.circle),
              child: const Icon(Icons.auto_awesome_rounded, color: Brand.accent),
            ),
            const SizedBox(width: 12),
            const Text('Your career snapshot', style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w800)),
          ],
        ),
        const SizedBox(height: 10),
        const Text('Your profile is taking shape through the signals you are building.', style: TextStyle(color: Colors.white70, height: 1.4)),
        const SizedBox(height: 20),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: [
            _SnapshotMetric('${summary.skillCount}', 'skills'),
            _SnapshotMetric('${summary.projectCount}', 'projects'),
            _SnapshotMetric('${summary.achievementCount}', 'achievements'),
            _SnapshotMetric('${summary.weakTopicCount}', 'topics to improve'),
          ],
        ),
      ],
    ),
  );
}

class _SnapshotMetric extends StatelessWidget {
  const _SnapshotMetric(this.value, this.label);
  final String value;
  final String label;

  @override
  Widget build(BuildContext context) => Container(
    width: 132,
    padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 11),
    decoration: BoxDecoration(color: Colors.white.withValues(alpha: .11), borderRadius: BorderRadius.circular(13)),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(value, style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w800)),
      const SizedBox(height: 2),
      Text(label, style: const TextStyle(color: Colors.white70, fontSize: 12)),
    ]),
  );
}

class _SummaryGrid extends StatelessWidget {
  const _SummaryGrid({required this.summary});
  final DashboardSummary summary;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final columns = constraints.maxWidth >= 700 ? 5 : 2;
      final width = (constraints.maxWidth - (columns - 1) * 10) / columns;
      final stats = [
        ('Skills', summary.skillCount, Icons.psychology_outlined, Brand.primary),
        ('Study topics', summary.studyTopicCount, Icons.menu_book_outlined, const Color(0xff467c73)),
        ('Projects', summary.projectCount, Icons.code_rounded, const Color(0xffbd7130)),
        ('Achievements', summary.achievementCount, Icons.workspace_premium_outlined, Brand.accent),
        ('Weak topics', summary.weakTopicCount, Icons.track_changes_outlined, const Color(0xffbd5d4d)),
      ];
      return Wrap(spacing: 10, runSpacing: 10, children: [
        for (final stat in stats) SizedBox(width: width, child: _SummaryStatCard(label: stat.$1, value: stat.$2, icon: stat.$3, color: stat.$4)),
      ]);
    },
  );
}

class _SummaryStatCard extends StatelessWidget {
  const _SummaryStatCard({required this.label, required this.value, required this.icon, required this.color});
  final String label;
  final int value;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(icon, color: color, size: 21),
        const SizedBox(height: 12),
        Text('$value', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
        const SizedBox(height: 2),
        Text(label, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.black54, fontSize: 12)),
      ]),
    ),
  );
}

class _SkillsSection extends StatelessWidget {
  const _SkillsSection({required this.title, required this.skills, required this.emptyText, required this.onSkillTap});
  final String title;
  final List<DashboardSkill> skills;
  final String emptyText;
  final ValueChanged<DashboardSkill> onSkillTap;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(18),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 17)),
        const SizedBox(height: 12),
        if (skills.isEmpty) _EmptyState(icon: Icons.insights_outlined, text: emptyText),
        for (final skill in skills.take(8)) _SkillTile(skill: skill, onTap: () => onSkillTap(skill)),
      ]),
    ),
  );
}

class _SkillTile extends StatelessWidget {
  const _SkillTile({required this.skill, required this.onTap});
  final DashboardSkill skill;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final improving = skill.trend.length > 1 && skill.trend.last.confidence > skill.trend.first.confidence;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(skill.name, style: const TextStyle(fontWeight: FontWeight.w700))),
            Text('${(skill.confidence * 100).round()}%', style: const TextStyle(color: Brand.primary, fontWeight: FontWeight.w800)),
            const SizedBox(width: 8),
            Icon(improving ? Icons.trending_up_rounded : Icons.trending_flat_rounded, size: 18, color: improving ? Brand.primary : Colors.black38),
          ]),
          const SizedBox(height: 7),
          ClipRRect(borderRadius: BorderRadius.circular(8), child: TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: skill.confidence),
            duration: const Duration(milliseconds: 650),
            builder: (context, value, child) => LinearProgressIndicator(value: value, minHeight: 8, backgroundColor: const Color(0xffe6ece8), color: skill.isStudyTopic ? const Color(0xffbd7130) : Brand.primary),
          )),
          const SizedBox(height: 5),
          Text('${skill.evidenceCount} piece${skill.evidenceCount == 1 ? '' : 's'} of evidence${skill.lastEvidenceAt == null ? '' : ' · ${_shortDate(skill.lastEvidenceAt)}'}', style: const TextStyle(color: Colors.black54, fontSize: 12)),
        ]),
      ),
    );
  }
}

class _WeakTopicsSection extends StatelessWidget {
  const _WeakTopicsSection({required this.topics});
  final List<WeakTopic> topics;

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    const _SectionTitle(title: 'Topics to improve', caption: 'A calm place to focus your next study session'),
    const SizedBox(height: 12),
    if (topics.isEmpty) const _EmptyState(icon: Icons.check_circle_outline, text: 'Great work! No weak topics detected.'),
    for (final topic in topics.take(6)) _WeakTopicCard(topic: topic),
  ]);
}

class _WeakTopicCard extends StatelessWidget {
  const _WeakTopicCard({required this.topic});
  final WeakTopic topic;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [Expanded(child: Text(topic.name, style: const TextStyle(fontWeight: FontWeight.w800))), Text('${(topic.accuracy * 100).round()}%', style: const TextStyle(color: Color(0xffa64f3f), fontWeight: FontWeight.w800))]),
        const SizedBox(height: 9),
        ClipRRect(borderRadius: BorderRadius.circular(8), child: LinearProgressIndicator(value: topic.accuracy, minHeight: 8, backgroundColor: const Color(0xfff2e4de), color: const Color(0xffbd7130))),
        const SizedBox(height: 8),
        Text('${topic.attempts} attempts${topic.lastAnsweredAt == null ? '' : ' · last answered ${_shortDate(topic.lastAnsweredAt)}'}', style: const TextStyle(color: Colors.black54, fontSize: 12)),
      ]),
    ),
  );
}

class _AchievementsSection extends StatelessWidget {
  const _AchievementsSection({required this.achievements});
  final List<DashboardAchievement> achievements;

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    const _SectionTitle(title: 'Achievements', caption: 'Milestones earned along the way'),
    const SizedBox(height: 12),
    if (achievements.isEmpty) const _EmptyState(icon: Icons.workspace_premium_outlined, text: 'Your achievements will appear here as you progress.'),
    if (achievements.isNotEmpty) SizedBox(height: 145, child: ListView.separated(scrollDirection: Axis.horizontal, itemCount: achievements.length, separatorBuilder: (context, index) => const SizedBox(width: 12), itemBuilder: (context, index) => _AchievementCard(achievement: achievements[index]))),
  ]);
}

class _AchievementCard extends StatelessWidget {
  const _AchievementCard({required this.achievement});
  final DashboardAchievement achievement;

  @override
  Widget build(BuildContext context) => SizedBox(width: 230, child: Card(child: Padding(padding: const EdgeInsets.all(15), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    const Icon(Icons.workspace_premium_rounded, color: Brand.accent, size: 25),
    const SizedBox(height: 8),
    Text(achievement.name, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w800)),
    const SizedBox(height: 4),
    Expanded(child: Text(achievement.description.isEmpty ? 'Milestone recorded in your learning journey.' : achievement.description, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.black54, fontSize: 12))),
    Text(_shortDate(achievement.awardedAt), style: const TextStyle(color: Brand.primary, fontSize: 12, fontWeight: FontWeight.w700)),
  ]))));
}

class _ProjectsSection extends StatelessWidget {
  const _ProjectsSection({required this.projects});
  final List<DashboardProject> projects;

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    const _SectionTitle(title: 'My projects', caption: 'The work that makes your profile tangible'),
    const SizedBox(height: 12),
    if (projects.isEmpty) const _EmptyState(icon: Icons.code_rounded, text: 'Add your first project to start building your career profile.'),
    for (final project in projects.take(6)) Card(child: ListTile(contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 5), leading: const CircleAvatar(backgroundColor: Color(0xffe5f0ec), child: Icon(Icons.code_rounded, color: Brand.primary)), title: Text(project.title, style: const TextStyle(fontWeight: FontWeight.w800)), subtitle: Text([project.techStack, project.sourceType].where((value) => value.isNotEmpty).join(' · ')), trailing: project.sourceRef?.isNotEmpty == true ? IconButton(tooltip: 'View source reference', icon: const Icon(Icons.open_in_new_rounded, size: 19), onPressed: () => _showSourceReference(context, project)) : null)),
  ]);
}

void _showSourceReference(BuildContext context, DashboardProject project) {
  showDialog<void>(
    context: context,
    builder: (_) => AlertDialog(
      title: Text(project.title),
      content: SelectableText(project.sourceRef!),
      actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close'))],
    ),
  );
}

class _CareerRunsSection extends StatelessWidget {
  const _CareerRunsSection({required this.runs});
  final Map<String, CareerRun> runs;

  @override
  Widget build(BuildContext context) {
    final entries = runs.entries.toList();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const _SectionTitle(title: 'Recent career insights', caption: 'Your latest analysis signals'),
      const SizedBox(height: 12),
      if (entries.isEmpty) const _EmptyState(icon: Icons.insights_outlined, text: 'No career insights generated yet.'),
      for (final entry in entries) Card(child: ListTile(contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 5), leading: const Icon(Icons.auto_awesome_outlined, color: Brand.primary), title: Text(_titleCase(entry.key), style: const TextStyle(fontWeight: FontWeight.w800)), subtitle: Text(_shortDate(entry.value.createdAt)), trailing: const Icon(Icons.chevron_right_rounded))),
    ]);
  }
}

class _SkillDetails extends StatelessWidget {
  const _SkillDetails({required this.skill});
  final DashboardSkill skill;

  @override
  Widget build(BuildContext context) => SafeArea(child: Padding(padding: const EdgeInsets.fromLTRB(22, 4, 22, 26), child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text(skill.name, style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
    const SizedBox(height: 6),
    Text('${(skill.confidence * 100).round()}% confidence · ${skill.evidenceCount} pieces of evidence', style: const TextStyle(color: Colors.black54)),
    const SizedBox(height: 20),
    if (skill.trend.isEmpty) const _EmptyState(icon: Icons.show_chart_rounded, text: 'No confidence history available yet.'),
    if (skill.trend.isNotEmpty) _TrendChart(points: skill.trend),
    if (skill.lastEvidenceAt != null) Padding(padding: const EdgeInsets.only(top: 12), child: Text('Last evidence: ${_shortDate(skill.lastEvidenceAt)}', style: const TextStyle(color: Colors.black54))),
  ])));
}

class _TrendChart extends StatelessWidget {
  const _TrendChart({required this.points});
  final List<ConfidencePoint> points;

  @override
  Widget build(BuildContext context) => SizedBox(
    height: 190,
    child: GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTapUp: (details) {
        final width = context.size?.width ?? 0;
        final index = width <= 0 || points.length == 1
            ? 0
            : ((details.localPosition.dx / width) * points.length).floor().clamp(0, points.length - 1);
        final point = points[index];
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          duration: const Duration(milliseconds: 1400),
          content: Text('${_shortDate(point.recordedAt)} - ${(point.confidence * 100).round()}% confidence'),
        ));
      },
      child: CustomPaint(painter: _TrendPainter(points), child: const SizedBox.expand()),
    ),
  );
}

class _TrendPainter extends CustomPainter {
  _TrendPainter(this.points);
  final List<ConfidencePoint> points;

  @override
  void paint(Canvas canvas, Size size) {
    final chart = Rect.fromLTWH(34, 12, size.width - 48, size.height - 34);
    final gridPaint = Paint()..color = const Color(0xffe5ebe7)..strokeWidth = 1;
    for (var i = 0; i <= 4; i++) {
      final y = chart.top + chart.height * i / 4;
      canvas.drawLine(Offset(chart.left, y), Offset(chart.right, y), gridPaint);
      final label = TextPainter(text: TextSpan(text: '${100 - i * 25}%', style: const TextStyle(fontSize: 10, color: Colors.black45)), textDirection: TextDirection.ltr)..layout();
      label.paint(canvas, Offset(0, y - 6));
    }
    final linePaint = Paint()..color = Brand.primary..style = PaintingStyle.stroke..strokeWidth = 3..strokeCap = StrokeCap.round;
    final fillPaint = Paint()..shader = LinearGradient(colors: [Brand.primary.withValues(alpha: .2), Brand.primary.withValues(alpha: 0)]).createShader(chart);
    final path = Path();
    for (var i = 0; i < points.length; i++) {
      final point = Offset(chart.left + (points.length == 1 ? chart.width / 2 : chart.width * i / (points.length - 1)), chart.bottom - chart.height * points[i].confidence);
      if (i == 0) path.moveTo(point.dx, point.dy); else path.lineTo(point.dx, point.dy);
    }
    final area = Path.from(path)..lineTo(chart.right, chart.bottom)..lineTo(chart.left, chart.bottom)..close();
    canvas.drawPath(area, fillPaint);
    canvas.drawPath(path, linePaint);
    for (var i = 0; i < points.length; i++) {
      final point = Offset(chart.left + (points.length == 1 ? chart.width / 2 : chart.width * i / (points.length - 1)), chart.bottom - chart.height * points[i].confidence);
      canvas.drawCircle(point, 5, Paint()..color = Colors.white);
      canvas.drawCircle(point, 3, Paint()..color = Brand.primary);
    }
  }

  @override
  bool shouldRepaint(covariant _TrendPainter oldDelegate) => oldDelegate.points != points;
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.title, required this.caption});
  final String title;
  final String caption;

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(title, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800, color: Brand.primaryDark)), const SizedBox(height: 3), Text(caption, style: const TextStyle(color: Colors.black54, fontSize: 13))]);
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.icon, required this.text});
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) => Container(width: double.infinity, padding: const EdgeInsets.all(20), decoration: BoxDecoration(color: const Color(0xfff1f5f2), borderRadius: BorderRadius.circular(14)), child: Row(children: [Icon(icon, color: Brand.primary), const SizedBox(width: 12), Expanded(child: Text(text, style: const TextStyle(color: Colors.black54)))]));
}

class _DashboardLoading extends StatelessWidget {
  const _DashboardLoading();

  @override
  Widget build(BuildContext context) => ListView(padding: const EdgeInsets.only(top: 10), children: [
    const _Skeleton(width: 240, height: 30),
    const SizedBox(height: 10),
    const _Skeleton(width: 280, height: 16),
    const SizedBox(height: 24),
    const _Skeleton(height: 180),
    const SizedBox(height: 18),
    Wrap(spacing: 10, runSpacing: 10, children: List.generate(5, (_) => const SizedBox(width: 125, child: _Skeleton(height: 105)))),
    const SizedBox(height: 24),
    const _Skeleton(height: 220),
  ]);
}

class _Skeleton extends StatefulWidget {
  const _Skeleton({this.width = double.infinity, required this.height});
  final double width;
  final double height;

  @override
  State<_Skeleton> createState() => _SkeletonState();
}

class _SkeletonState extends State<_Skeleton> with SingleTickerProviderStateMixin {
  late final AnimationController controller = AnimationController(vsync: this, duration: const Duration(milliseconds: 1200))..repeat(reverse: true);

  @override
  void dispose() { controller.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(animation: controller, builder: (context, child) => Container(width: widget.width, height: widget.height, decoration: BoxDecoration(color: Color.lerp(const Color(0xffe7ece8), const Color(0xfff5f7f5), controller.value), borderRadius: BorderRadius.circular(16))));
}

class _DashboardError extends StatelessWidget {
  const _DashboardError({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Center(child: Padding(padding: const EdgeInsets.all(24), child: Column(mainAxisSize: MainAxisSize.min, children: [const Icon(Icons.cloud_off_rounded, size: 44, color: Brand.primary), const SizedBox(height: 14), Text('Unable to load your dashboard', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)), const SizedBox(height: 6), Text(message, textAlign: TextAlign.center, style: const TextStyle(color: Colors.black54)), const SizedBox(height: 18), FilledButton.icon(onPressed: onRetry, icon: const Icon(Icons.refresh_rounded), label: const Text('Retry'))])));
}

String _shortDate(String? raw) {
  if (raw == null || raw.isEmpty) return 'Date unavailable';
  final parsed = DateTime.tryParse(raw);
  if (parsed == null) return raw;
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return '${months[parsed.month - 1]} ${parsed.day}, ${parsed.year}';
}

String _titleCase(String value) => value.replaceAll('_', ' ').split(' ').map((word) => word.isEmpty ? word : '${word[0].toUpperCase()}${word.substring(1)}').join(' ');

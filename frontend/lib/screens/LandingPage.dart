// The file predates the current lower_case_with_underscores convention.
// ignore_for_file: file_names

import 'package:flutter/material.dart';

import '../services/auth_service.dart';
import 'app.dart';
import 'auth_pages.dart';

class LandingPage extends StatelessWidget {
  const LandingPage({required this.auth, super.key});
  final AuthController auth;

  static const _features = [
    (
      Icons.chat_bubble_outline_rounded,
      'Chat with your material',
      'Ask questions and get grounded answers pulled straight from the '
          'documents you upload.',
    ),
    (
      Icons.work_outline_rounded,
      'Career Zone',
      'Track projects and certifications, spot skill gaps against a job '
          'description, and rehearse with a mock interviewer.',
    ),
    (
      Icons.insights_outlined,
      'Skill Zone',
      'Build a living skill graph from evidence — projects, GitHub, and '
          'quiz performance all feed into it.',
    ),
    (
      Icons.school_outlined,
      'Study Zone',
      'Turn a syllabus into a study plan and weak topics into quizzes, '
          'automatically.',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final isWide = MediaQuery.sizeOf(context).width >= 900;
    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.menu_book_rounded, color: Brand.primary),
            const SizedBox(width: 10),
            Flexible(
              child: Text(
                'Academic Second Brain',
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => LoginPage(auth: auth)),
            ),
            child: const Text('Log in'),
          ),
          const SizedBox(width: 8),
          FilledButton(
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => SignupPage(auth: auth)),
            ),
            child: const Padding(
              padding: EdgeInsets.symmetric(horizontal: 4),
              child: Text('Get started'),
            ),
          ),
          const SizedBox(width: 16),
        ],
      ),
      body: SingleChildScrollView(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1100),
            child: Padding(
              padding: EdgeInsets.symmetric(
                horizontal: isWide ? 32 : 20,
                vertical: 32,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _Hero(auth: auth, isWide: isWide),
                  const SizedBox(height: 64),
                  Text(
                    'Everything one learning workspace needs',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Four zones, one profile, zero context-switching.',
                    textAlign: TextAlign.center,
                    style: Theme.of(
                      context,
                    ).textTheme.bodyLarge?.copyWith(color: Colors.black54),
                  ),
                  const SizedBox(height: 32),
                  LayoutBuilder(
                    builder: (context, constraints) {
                      final columns = isWide ? 4 : 2;
                      final gap = 16.0;
                      final cardWidth =
                          (constraints.maxWidth - gap * (columns - 1)) /
                          columns;
                      return Wrap(
                        spacing: gap,
                        runSpacing: gap,
                        children: [
                          for (final feature in _features)
                            SizedBox(
                              width: cardWidth,
                              child: _FeatureCard(
                                icon: feature.$1,
                                title: feature.$2,
                                text: feature.$3,
                              ),
                            ),
                        ],
                      );
                    },
                  ),
                  const SizedBox(height: 56),
                  _ClosingCta(auth: auth),
                  const SizedBox(height: 32),
                  Text(
                    '© ${DateTime.now().year} Academic Second Brain',
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.black38, fontSize: 12),
                  ),
                  const SizedBox(height: 12),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _Hero extends StatelessWidget {
  const _Hero({required this.auth, required this.isWide});
  final AuthController auth;
  final bool isWide;

  Widget _copy(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    mainAxisSize: MainAxisSize.min,
    children: [
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: Brand.primary.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(20),
        ),
        child: const Text(
          'Built for students, one workspace',
          style: TextStyle(
            color: Brand.primary,
            fontWeight: FontWeight.w600,
            fontSize: 12,
          ),
        ),
      ),
      const SizedBox(height: 20),
      Text(
        'Your entire learning\njourney, in one place.',
        style: Theme.of(context).textTheme.displaySmall?.copyWith(
          fontWeight: FontWeight.w800,
          height: 1.15,
        ),
      ),
      const SizedBox(height: 16),
      Text(
        'Chat with your notes, close skill gaps, rehearse interviews, and '
        'turn a syllabus into a study plan — a calm second brain that '
        'keeps every zone of your academic life connected.',
        style: Theme.of(
          context,
        ).textTheme.titleMedium?.copyWith(color: Colors.black54, height: 1.4),
      ),
      const SizedBox(height: 28),
      Wrap(
        spacing: 12,
        runSpacing: 12,
        children: [
          FilledButton.icon(
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => SignupPage(auth: auth)),
            ),
            icon: const Icon(Icons.person_add_alt_1),
            label: const Text('Create your account'),
          ),
          OutlinedButton.icon(
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => LoginPage(auth: auth)),
            ),
            icon: const Icon(Icons.login),
            label: const Text('I already have one'),
          ),
        ],
      ),
    ],
  );

  Widget _illustration() => AspectRatio(
    aspectRatio: 1,
    child: Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(28),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Brand.primary, Brand.primaryDark],
        ),
      ),
      padding: const EdgeInsets.all(28),
      child: Stack(
        children: [
          Positioned(
            right: -20,
            top: -20,
            child: Icon(
              Icons.auto_awesome,
              size: 120,
              color: Colors.white.withValues(alpha: 0.12),
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              const Spacer(),
              const Icon(
                Icons.menu_book_rounded,
                color: Colors.white,
                size: 44,
              ),
              const SizedBox(height: 16),
              const Text(
                'Second Brain',
                style: TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w800,
                  fontSize: 22,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                'Profile → Zones → Progress',
                style: TextStyle(color: Colors.white.withValues(alpha: 0.8)),
              ),
            ],
          ),
        ],
      ),
    ),
  );

  @override
  Widget build(BuildContext context) {
    if (!isWide) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [_copy(context), const SizedBox(height: 32), _illustration()],
      );
    }
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Expanded(flex: 6, child: _copy(context)),
          const SizedBox(width: 48),
          Expanded(flex: 4, child: _illustration()),
        ],
      ),
    );
  }
}

class _FeatureCard extends StatelessWidget {
  const _FeatureCard({
    required this.icon,
    required this.title,
    required this.text,
  });
  final IconData icon;
  final String title;
  final String text;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: Brand.primary.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: Brand.primary),
          ),
          const SizedBox(height: 16),
          Text(
            title,
            style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
          ),
          const SizedBox(height: 6),
          Text(
            text,
            style: const TextStyle(
              color: Colors.black54,
              fontSize: 13,
              height: 1.4,
            ),
          ),
        ],
      ),
    ),
  );
}

class _ClosingCta extends StatelessWidget {
  const _ClosingCta({required this.auth});
  final AuthController auth;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(32),
    decoration: BoxDecoration(
      color: Brand.primary,
      borderRadius: BorderRadius.circular(24),
    ),
    child: Column(
      children: [
        const Text(
          'Ready to build your second brain?',
          textAlign: TextAlign.center,
          style: TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.w800,
            fontSize: 22,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'Free to join — takes less than a minute to set up your profile.',
          textAlign: TextAlign.center,
          style: TextStyle(color: Colors.white.withValues(alpha: 0.85)),
        ),
        const SizedBox(height: 20),
        FilledButton(
          style: FilledButton.styleFrom(
            backgroundColor: Colors.white,
            foregroundColor: Brand.primaryDark,
          ),
          onPressed: () => Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => SignupPage(auth: auth)),
          ),
          child: const Padding(
            padding: EdgeInsets.symmetric(horizontal: 24),
            child: Text('Create your free account'),
          ),
        ),
      ],
    ),
  );
}

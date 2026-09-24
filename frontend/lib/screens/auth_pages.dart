import 'package:flutter/material.dart';

import '../services/auth_service.dart';
import 'app.dart';

// ---------------------------------------------------------------------------
// Shared shell used by both Login and Signup so the two screens feel like one
// coherent flow.
// ---------------------------------------------------------------------------

class AuthScaffold extends StatelessWidget {
  const AuthScaffold({
    required this.title,
    required this.subtitle,
    required this.child,
    required this.footer,
    super.key,
  });

  final String title;
  final String subtitle;
  final Widget child;
  final Widget footer;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      leading: BackButton(onPressed: () => Navigator.maybePop(context)),
    ),
    body: SafeArea(
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 460),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Icon(
                  Icons.menu_book_rounded,
                  size: 36,
                  color: Brand.primary,
                ),
                const SizedBox(height: 20),
                Text(
                  title,
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 6),
                Text(subtitle, style: const TextStyle(color: Colors.black54)),
                const SizedBox(height: 28),
                child,
                const SizedBox(height: 20),
                footer,
                const SizedBox(height: 24),
              ],
            ),
          ),
        ),
      ),
    ),
  );
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.only(bottom: 16),
    padding: const EdgeInsets.all(12),
    decoration: BoxDecoration(
      color: Brand.danger.withValues(alpha: 0.08),
      borderRadius: BorderRadius.circular(10),
      border: Border.all(color: Brand.danger.withValues(alpha: 0.3)),
    ),
    child: Row(
      children: [
        const Icon(Icons.error_outline, color: Brand.danger, size: 20),
        const SizedBox(width: 10),
        Expanded(
          child: Text(message, style: const TextStyle(color: Brand.danger)),
        ),
      ],
    ),
  );
}

// ---------------------------------------------------------------------------
// Login
// ---------------------------------------------------------------------------

class LoginPage extends StatefulWidget {
  const LoginPage({required this.auth, super.key});
  final AuthController auth;

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _formKey = GlobalKey<FormState>();
  final email = TextEditingController();
  final password = TextEditingController();
  bool _obscure = true;

  static final _emailRegex = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

  @override
  void dispose() {
    email.dispose();
    password.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    FocusScope.of(context).unfocus();
    if (!(_formKey.currentState?.validate() ?? false)) return;
    final ok = await widget.auth.login(email.text.trim(), password.text);
    if (!mounted) return;
    if (ok) {
      // AcademicSecondBrainApp listens to `auth` and will swap to HomeShell
      // automatically, so we just close every route pushed on top of it.
      Navigator.of(context).popUntil((route) => route.isFirst);
    }
  }

  @override
  Widget build(BuildContext context) => AuthScaffold(
    title: 'Welcome back',
    subtitle: 'Pick up where your learning left off.',
    // ignore: sort_child_properties_last
    child: Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          AnimatedBuilder(
            animation: widget.auth,
            builder: (context, _) => widget.auth.error == null
                ? const SizedBox.shrink()
                : _ErrorBanner(message: widget.auth.error!),
          ),
          TextFormField(
            controller: email,
            textInputAction: TextInputAction.next,
            keyboardType: TextInputType.emailAddress,
            autofillHints: const [AutofillHints.email],
            decoration: const InputDecoration(
              labelText: 'Email',
              prefixIcon: Icon(Icons.alternate_email),
            ),
            validator: (value) => (value == null || !_emailRegex.hasMatch(value.trim()))
                ? 'Enter a valid email'
                : null,
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: password,
            obscureText: _obscure,
            textInputAction: TextInputAction.done,
            autofillHints: const [AutofillHints.password],
            onFieldSubmitted: (_) => submit(),
            decoration: InputDecoration(
              labelText: 'Password',
              prefixIcon: const Icon(Icons.lock_outline),
              suffixIcon: IconButton(
                icon: Icon(
                  _obscure
                      ? Icons.visibility_outlined
                      : Icons.visibility_off_outlined,
                ),
                onPressed: () => setState(() => _obscure = !_obscure),
              ),
            ),
            validator: (value) =>
                (value == null || value.isEmpty) ? 'Enter your password' : null,
          ),
          const SizedBox(height: 22),
          AnimatedBuilder(
            animation: widget.auth,
            builder: (context, _) => FilledButton.icon(
              onPressed: widget.auth.busy ? null : submit,
              icon: widget.auth.busy
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.arrow_forward),
              label: Text(widget.auth.busy ? 'Signing in…' : 'Log in'),
            ),
          ),
        ],
      ),
    ),
    footer: Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Text("Don't have an account?"),
        TextButton(
          onPressed: () => Navigator.pushReplacement(
            context,
            MaterialPageRoute(builder: (_) => SignupPage(auth: widget.auth)),
          ),
          child: const Text('Create one'),
        ),
      ],
    ),
  );
}

// ---------------------------------------------------------------------------
// Signup
// ---------------------------------------------------------------------------

class SignupPage extends StatefulWidget {
  const SignupPage({required this.auth, super.key});
  final AuthController auth;

  @override
  State<SignupPage> createState() => _SignupPageState();
}

class _SignupPageState extends State<SignupPage> {
  final _formKey = GlobalKey<FormState>();
  final name = TextEditingController();
  final email = TextEditingController();
  final password = TextEditingController();
  final confirmPassword = TextEditingController();
  final collegeName = TextEditingController();
  final collegeYear = TextEditingController();
  bool _obscurePassword = true;
  bool _obscureConfirm = true;

  static final _emailRegex = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

  @override
  void dispose() {
    name.dispose();
    email.dispose();
    password.dispose();
    confirmPassword.dispose();
    collegeName.dispose();
    collegeYear.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    FocusScope.of(context).unfocus();
    if (!(_formKey.currentState?.validate() ?? false)) return;
    final fields = {
      'name': name.text.trim(),
      'email': email.text.trim(),
      'password': password.text,
      'confirm_password': confirmPassword.text,
      'college_name': collegeName.text.trim(),
      'college_year': collegeYear.text.trim(),
    };
    final ok = await widget.auth.signup(fields);
    if (!mounted) return;
    if (ok) {
      Navigator.of(context).popUntil((route) => route.isFirst);
    }
  }

  @override
  Widget build(BuildContext context) => AuthScaffold(
    title: 'Build your learning home',
    subtitle: 'Your profile becomes the context for every zone.',
    // ignore: sort_child_properties_last
    child: Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          AnimatedBuilder(
            animation: widget.auth,
            builder: (context, _) => widget.auth.error == null
                ? const SizedBox.shrink()
                : _ErrorBanner(message: widget.auth.error!),
          ),
          const _SectionLabel('Account'),
          TextFormField(
            controller: name,
            decoration: const InputDecoration(
              labelText: 'Name',
              prefixIcon: Icon(Icons.badge_outlined),
            ),
            validator: (value) {
              final v = value?.trim() ?? '';
              if (v.isEmpty) return 'Enter your name';
              if (v.length > 100) return 'Keep it under 100 characters';
              return null;
            },
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: email,
            keyboardType: TextInputType.emailAddress,
            decoration: const InputDecoration(
              labelText: 'Email',
              prefixIcon: Icon(Icons.alternate_email),
            ),
            validator: (value) {
              final v = value?.trim() ?? '';
              if (v.isEmpty) return 'Enter your email';
              if (!_emailRegex.hasMatch(v)) return 'Enter a valid email';
              return null;
            },
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: password,
            obscureText: _obscurePassword,
            decoration: InputDecoration(
              labelText: 'Password',
              prefixIcon: const Icon(Icons.lock_outline),
              helperText: '8–72 characters',
              suffixIcon: IconButton(
                icon: Icon(
                  _obscurePassword
                      ? Icons.visibility_outlined
                      : Icons.visibility_off_outlined,
                ),
                onPressed: () =>
                    setState(() => _obscurePassword = !_obscurePassword),
              ),
            ),
            validator: (value) {
              final v = value ?? '';
              if (v.isEmpty) return 'Enter a password';
              if (v.length < 8) return 'Use at least 8 characters';
              if (v.length > 72) return 'Keep it under 72 characters';
              return null;
            },
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: confirmPassword,
            obscureText: _obscureConfirm,
            decoration: InputDecoration(
              labelText: 'Confirm password',
              prefixIcon: const Icon(Icons.lock_outline),
              suffixIcon: IconButton(
                icon: Icon(
                  _obscureConfirm
                      ? Icons.visibility_outlined
                      : Icons.visibility_off_outlined,
                ),
                onPressed: () =>
                    setState(() => _obscureConfirm = !_obscureConfirm),
              ),
            ),
            validator: (value) =>
                value != password.text ? 'Passwords do not match' : null,
          ),
          const SizedBox(height: 24),
          const _SectionLabel('Academic details'),
          TextFormField(
            controller: collegeName,
            decoration: const InputDecoration(
              labelText: 'College name',
              prefixIcon: Icon(Icons.account_balance_outlined),
            ),
            validator: (value) {
              final v = value?.trim() ?? '';
              if (v.isEmpty) return 'Enter your college name';
              if (v.length > 200) return 'Keep it under 200 characters';
              return null;
            },
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: collegeYear,
            decoration: const InputDecoration(
              labelText: 'College year (e.g. 2nd, 4th)',
              prefixIcon: Icon(Icons.calendar_today_outlined),
            ),
            validator: (value) {
              final v = value?.trim() ?? '';
              if (v.isEmpty) return 'Enter your college year';
              if (v.length > 20) return 'Keep it under 20 characters';
              return null;
            },
          ),
          const SizedBox(height: 26),
          AnimatedBuilder(
            animation: widget.auth,
            builder: (context, _) => FilledButton.icon(
              onPressed: widget.auth.busy ? null : submit,
              icon: widget.auth.busy
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.auto_awesome),
              label: Text(widget.auth.busy ? 'Creating…' : 'Create account'),
            ),
          ),
        ],
      ),
    ),
    footer: Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Text('Already have an account?'),
        TextButton(
          onPressed: () => Navigator.pushReplacement(
            context,
            MaterialPageRoute(builder: (_) => LoginPage(auth: widget.auth)),
          ),
          child: const Text('Log in'),
        ),
      ],
    ),
  );
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Text(
      text.toUpperCase(),
      style: const TextStyle(
        fontSize: 11.5,
        fontWeight: FontWeight.w700,
        letterSpacing: 1.1,
        color: Brand.primary,
      ),
    ),
  );
}

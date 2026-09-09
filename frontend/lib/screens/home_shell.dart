import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter_markdown/flutter_markdown.dart';

import '../models/user.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';
import '../services/download_helper.dart';
import 'app.dart';
import 'dashboard_screen.dart';

class _NavEntry {
  const _NavEntry(this.label, this.icon, {this.adminOnly = false});
  final String label;
  final IconData icon;
  final bool adminOnly;
}

const _studentNav = [
  _NavEntry('Overview', Icons.grid_view_rounded),
  _NavEntry('Chat', Icons.chat_bubble_outline_rounded),
  _NavEntry('Profile', Icons.person_outline),
  _NavEntry('Career Zone', Icons.work_outline_rounded),
  _NavEntry('Skill Zone', Icons.insights_outlined),
  _NavEntry('Study Zone', Icons.school_outlined),
  _NavEntry('Documents', Icons.folder_open_outlined),
];

const _adminNav = [
  _NavEntry('Overview', Icons.grid_view_rounded),
  _NavEntry('Profile', Icons.person_outline),
  _NavEntry(
    'Admin console',
    Icons.admin_panel_settings_outlined,
    adminOnly: true,
  ),
];

class HomeShell extends StatefulWidget {
  const HomeShell({required this.auth, super.key});
  final AuthController auth;

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int selected = 0;

  List<_NavEntry> get _nav => widget.auth.isAdmin ? _adminNav : _studentNav;

  void _goTo(int index) => setState(() => selected = index);

  Future<void> _confirmLogout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Log out?'),
        content: const Text("You'll need to sign in again to continue."),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Log out'),
          ),
        ],
      ),
    );
    if (confirmed == true) await widget.auth.logout();
  }

  @override
  Widget build(BuildContext context) {
    final nav = _nav;
    final safeIndex = selected < nav.length ? selected : 0;
    final isWide = MediaQuery.sizeOf(context).width >= 900;

    return Scaffold(
      appBar: AppBar(
        title: Text(
          nav[safeIndex].label,
          style: const TextStyle(fontWeight: FontWeight.w700),
        ),
        actions: [_UserMenu(auth: widget.auth, onLogout: _confirmLogout)],
      ),
      drawer: isWide
          ? null
          : Drawer(
              child: _NavList(
                entries: nav,
                selected: safeIndex,
                onSelect: (index) {
                  _goTo(index);
                  Navigator.pop(context);
                },
                auth: widget.auth,
              ),
            ),
      body: Row(
        children: [
          if (isWide)
            SizedBox(
              width: 260,
              child: Material(
                color: Brand.surface,
                child: _NavList(
                  entries: nav,
                  selected: safeIndex,
                  onSelect: _goTo,
                  auth: widget.auth,
                ),
              ),
            ),
          if (isWide) const VerticalDivider(width: 1),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: _Page(
                label: nav[safeIndex].label,
                auth: widget.auth,
                onNavigate: _goTo,
                nav: nav,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _NavList extends StatelessWidget {
  const _NavList({
    required this.entries,
    required this.selected,
    required this.onSelect,
    required this.auth,
  });
  final List<_NavEntry> entries;
  final int selected;
  final ValueChanged<int> onSelect;
  final AuthController auth;

  @override
  Widget build(BuildContext context) => SafeArea(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 24, 20, 12),
          child: Row(
            children: [
              const Icon(Icons.menu_book_rounded, color: Brand.primary),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'SECOND BRAIN',
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    letterSpacing: 1.2,
                    fontWeight: FontWeight.w800,
                    color: Brand.primary,
                  ),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 4),
        for (var i = 0; i < entries.length; i++)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
            child: _NavTile(
              entry: entries[i],
              isSelected: selected == i,
              onTap: () => onSelect(i),
            ),
          ),
        const Spacer(),
        Padding(
          padding: const EdgeInsets.all(16),
          child: _RoleBadge(role: auth.user?.role ?? 'student'),
        ),
      ],
    ),
  );
}

class _NavTile extends StatelessWidget {
  const _NavTile({
    required this.entry,
    required this.isSelected,
    required this.onTap,
  });
  final _NavEntry entry;
  final bool isSelected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Material(
    color: isSelected
        ? Brand.primary.withValues(alpha: 0.09)
        : Colors.transparent,
    borderRadius: BorderRadius.circular(12),
    child: InkWell(
      borderRadius: BorderRadius.circular(12),
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          children: [
            Icon(
              entry.icon,
              size: 20,
              color: isSelected ? Brand.primary : Colors.black54,
            ),
            const SizedBox(width: 14),
            Text(
              entry.label,
              style: TextStyle(
                color: isSelected ? Brand.primary : const Color(0xff1c211f),
                fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                fontSize: 14,
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

class _RoleBadge extends StatelessWidget {
  const _RoleBadge({required this.role});
  final String role;
  bool get _isAdmin => role == 'admin';

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
    decoration: BoxDecoration(
      color: (_isAdmin ? Brand.accent : Brand.primary).withValues(alpha: 0.1),
      borderRadius: BorderRadius.circular(10),
    ),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(
          _isAdmin ? Icons.shield_outlined : Icons.school_outlined,
          size: 16,
          color: _isAdmin ? Brand.accent : Brand.primary,
        ),
        const SizedBox(width: 8),
        Text(
          _isAdmin ? 'Admin account' : 'Student account',
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: _isAdmin ? const Color(0xff8a5c14) : Brand.primaryDark,
          ),
        ),
      ],
    ),
  );
}

class _UserMenu extends StatelessWidget {
  const _UserMenu({required this.auth, required this.onLogout});
  final AuthController auth;
  final VoidCallback onLogout;

  @override
  Widget build(BuildContext context) {
    final user = auth.user;
    final initial = (user?.name.isNotEmpty ?? false)
        ? user!.name.substring(0, 1).toUpperCase()
        : '?';
    return Padding(
      padding: const EdgeInsets.only(right: 12),
      child: PopupMenuButton<String>(
        tooltip: 'Account',
        offset: const Offset(0, 48),
        onSelected: (value) {
          if (value == 'logout') onLogout();
        },
        itemBuilder: (context) => [
          PopupMenuItem<String>(
            enabled: false,
            child: Text(
              user?.email ?? '',
              style: const TextStyle(color: Colors.black54, fontSize: 12),
            ),
          ),
          const PopupMenuDivider(),
          const PopupMenuItem<String>(
            value: 'logout',
            child: Row(
              children: [
                Icon(Icons.logout, size: 18, color: Brand.danger),
                SizedBox(width: 10),
                Text('Log out', style: TextStyle(color: Brand.danger)),
              ],
            ),
          ),
        ],
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircleAvatar(
              radius: 16,
              backgroundColor: Brand.primary,
              child: Text(
                initial,
                style: const TextStyle(color: Colors.white, fontSize: 13),
              ),
            ),
            const SizedBox(width: 8),
            if (MediaQuery.sizeOf(context).width >= 600)
              Text(
                user?.name ?? '',
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
            const Icon(Icons.expand_more, size: 18),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Page router within the shell
// ---------------------------------------------------------------------------

class _Page extends StatelessWidget {
  const _Page({
    required this.label,
    required this.auth,
    required this.onNavigate,
    required this.nav,
  });
  final String label;
  final AuthController auth;
  final ValueChanged<int> onNavigate;
  final List<_NavEntry> nav;

  @override
  Widget build(BuildContext context) {
    switch (label) {
      case 'Overview':
        return _OverviewPage(auth: auth, nav: nav, onNavigate: onNavigate);
      case 'Chat':
        return ChatPage(api: auth.api);
      case 'Documents':
        return DocumentsPage(api: auth.api);
      case 'Profile':
        return ProfilePage(api: auth.api, user: auth.user!);
      case 'Study Zone':
        return StudyPage(api: auth.api);
      case 'Career Zone':
        return CareerPage(api: auth.api);
      case 'Skill Zone':
        return SkillsPage(api: auth.api);
      case 'Admin console':
        return AdminOverviewPage(api: auth.api, currentUserId: auth.user!.id);
      default:
        return _ComingSoon(label: label);
    }
  }
}

class AdminOverviewPage extends StatefulWidget {
  const AdminOverviewPage({
    required this.api,
    required this.currentUserId,
    super.key,
  });
  final ApiService api;
  final String currentUserId;

  @override
  State<AdminOverviewPage> createState() => _AdminOverviewPageState();
}

class _AdminOverviewPageState extends State<AdminOverviewPage> {
  final search = TextEditingController();
  List<Map<String, dynamic>> users = [];
  bool loading = true;
  String? error;

  @override
  void initState() {
    super.initState();
    search.addListener(() => setState(() {}));
    _loadUsers();
  }

  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  Future<void> _loadUsers() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final result = await widget.api.adminUsers();
      if (!mounted) return;
      setState(() {
        users = result
            .map((user) => Map<String, dynamic>.from(user as Map))
            .toList();
        loading = false;
      });
    } on ApiException catch (exception) {
      if (mounted)
        setState(() {
          error = exception.message;
          loading = false;
        });
    }
  }

  List<Map<String, dynamic>> get filteredUsers {
    final query = search.text.trim().toLowerCase();
    if (query.isEmpty) return users;
    return users.where((user) {
      final text = '${user['name']} ${user['email']} ${user['role']}'
          .toLowerCase();
      return text.contains(query);
    }).toList();
  }

  Future<void> _changeRole(Map<String, dynamic> user, String role) async {
    final userId = '${user['user_id'] ?? user['id'] ?? ''}';
    if (userId == widget.currentUserId) return;
    try {
      await widget.api.updateAdminUserRole(userId, role);
      await _loadUsers();
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    }
  }

  Future<void> _deleteUser(Map<String, dynamic> user) async {
    final userId = '${user['user_id'] ?? user['id'] ?? ''}';
    if (userId == widget.currentUserId) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Delete user?'),
        content: Text(
          'Delete ${user['name'] ?? 'this user'} and their account?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Brand.danger),
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await widget.api.deleteAdminUser(userId);
      await _loadUsers();
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final adminCount = users.where((user) => user['role'] == 'admin').length;
    final studentCount = users.where((user) => user['role'] != 'admin').length;
    return ListView(
      children: [
        Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Admin overview',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Manage users and workspace access.',
                    style: TextStyle(color: Colors.black54),
                  ),
                ],
              ),
            ),
            IconButton(
              tooltip: 'Refresh users',
              onPressed: loading ? null : _loadUsers,
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
        const SizedBox(height: 22),
        if (error != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Text(
              error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            _AdminMetric(
              label: 'Total users',
              value: '${users.length}',
              icon: Icons.people_outline,
            ),
            _AdminMetric(
              label: 'Students',
              value: '$studentCount',
              icon: Icons.school_outlined,
            ),
            _AdminMetric(
              label: 'Admins',
              value: '$adminCount',
              icon: Icons.admin_panel_settings_outlined,
            ),
          ],
        ),
        const SizedBox(height: 20),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'User directory',
                  style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: search,
                  decoration: const InputDecoration(
                    prefixIcon: Icon(Icons.search),
                    labelText: 'Search users',
                  ),
                ),
                const SizedBox(height: 12),
                if (loading) const LinearProgressIndicator(),
                if (!loading && filteredUsers.isEmpty)
                  const Padding(
                    padding: EdgeInsets.all(12),
                    child: Text(
                      'No users found.',
                      style: TextStyle(color: Colors.black54),
                    ),
                  ),
                for (final user in filteredUsers)
                  _AdminUserTile(
                    user: user,
                    isCurrentUser:
                        '${user['user_id'] ?? user['id'] ?? ''}' ==
                        widget.currentUserId,
                    onRoleChanged: _changeRole,
                    onDelete: _deleteUser,
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _AdminMetric extends StatelessWidget {
  const _AdminMetric({
    required this.label,
    required this.value,
    required this.icon,
  });
  final String label;
  final String value;
  final IconData icon;

  @override
  Widget build(BuildContext context) => SizedBox(
    width: 190,
    child: Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Icon(icon, color: Brand.primary),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  value,
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.w800,
                    color: Brand.primary,
                  ),
                ),
                Text(
                  label,
                  style: const TextStyle(color: Colors.black54, fontSize: 12),
                ),
              ],
            ),
          ],
        ),
      ),
    ),
  );
}

class _AdminUserTile extends StatelessWidget {
  const _AdminUserTile({
    required this.user,
    required this.isCurrentUser,
    required this.onRoleChanged,
    required this.onDelete,
  });
  final Map<String, dynamic> user;
  final bool isCurrentUser;
  final Future<void> Function(Map<String, dynamic>, String) onRoleChanged;
  final Future<void> Function(Map<String, dynamic>) onDelete;

  @override
  Widget build(BuildContext context) {
    final role = '${user['role'] ?? 'student'}';
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: CircleAvatar(
        backgroundColor: Brand.primary.withValues(alpha: 0.12),
        child: Text(
          '${user['name'] ?? '?'}'.substring(0, 1).toUpperCase(),
          style: const TextStyle(color: Brand.primary),
        ),
      ),
      title: Text(
        '${user['name'] ?? 'Unnamed user'}',
        style: const TextStyle(fontWeight: FontWeight.w700),
      ),
      subtitle: Text('${user['email'] ?? ''}${isCurrentUser ? ' · You' : ''}'),
      trailing: Wrap(
        spacing: 4,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          DropdownButton<String>(
            value: role == 'admin' ? 'admin' : 'student',
            onChanged: isCurrentUser
                ? null
                : (value) {
                    if (value != null) onRoleChanged(user, value);
                  },
            items: const [
              DropdownMenuItem(value: 'student', child: Text('Student')),
              DropdownMenuItem(value: 'admin', child: Text('Admin')),
            ],
          ),
          IconButton(
            tooltip: isCurrentUser
                ? 'You cannot delete yourself'
                : 'Delete user',
            onPressed: isCurrentUser ? null : () => onDelete(user),
            icon: const Icon(Icons.delete_outline, color: Brand.danger),
          ),
        ],
      ),
    );
  }
}

class _ComingSoon extends StatelessWidget {
  const _ComingSoon({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) => Center(
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(
          Icons.construction_outlined,
          size: 36,
          color: Colors.black26,
        ),
        const SizedBox(height: 12),
        Text(
          '$label is being wired up next',
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 4),
        const Text(
          'This zone will connect to the API in the next pass.',
          style: TextStyle(color: Colors.black45, fontSize: 13),
        ),
      ],
    ),
  );
}

// ---------------------------------------------------------------------------
// Overview
// ---------------------------------------------------------------------------

class _OverviewPage extends StatelessWidget {
  const _OverviewPage({
    required this.auth,
    required this.nav,
    required this.onNavigate,
  });
  final AuthController auth;
  final List<_NavEntry> nav;
  final ValueChanged<int> onNavigate;

  String get _greeting {
    final hour = DateTime.now().hour;
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  }

  @override
  Widget build(BuildContext context) {
    if (!auth.isAdmin) {
      return DashboardScreen(
        api: auth.api,
        studentId: auth.user?.id ?? '',
        fallbackName: auth.user?.name ?? '',
      );
    }

    final isAdmin = auth.isAdmin;
    final name = auth.user?.name ?? 'there';
    return ListView(
      children: [
        Text(
          '$_greeting, $name.',
          style: Theme.of(
            context,
          ).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 8),
        Text(
          isAdmin
              ? 'Here is a quick look at the workspace you manage.'
              : 'Your learning workspace is ready. Choose a zone to keep moving.',
          style: const TextStyle(color: Colors.black54),
        ),
        const SizedBox(height: 28),
        if (isAdmin)
          _AdminOverview(nav: nav, onNavigate: onNavigate)
        else
          _StudentOverview(nav: nav, onNavigate: onNavigate),
      ],
    );
  }
}

class _StudentOverview extends StatelessWidget {
  const _StudentOverview({required this.nav, required this.onNavigate});
  final List<_NavEntry> nav;
  final ValueChanged<int> onNavigate;

  static const _cards = [
    (
      'Chat',
      Icons.chat_bubble_outline_rounded,
      'Ask a question about anything you\'ve uploaded.',
    ),
    (
      'Career Zone',
      Icons.work_outline_rounded,
      'Turn skills into focused next steps.',
    ),
    ('Skill Zone', Icons.insights_outlined, 'Capture evidence as you learn.'),
    ('Study Zone', Icons.school_outlined, 'Practice, diagnose, and plan.'),
    (
      'Documents',
      Icons.folder_open_outlined,
      'Upload notes and past material.',
    ),
    ('Profile', Icons.person_outline, 'Keep your academic context current.'),
  ];

  @override
  Widget build(BuildContext context) => Wrap(
    spacing: 14,
    runSpacing: 14,
    children: [
      for (final card in _cards)
        _OverviewCard(
          icon: card.$2,
          title: card.$1,
          text: card.$3,
          onTap: () {
            final index = nav.indexWhere((entry) => entry.label == card.$1);
            if (index != -1) onNavigate(index);
          },
        ),
    ],
  );
}

class _AdminOverview extends StatelessWidget {
  const _AdminOverview({required this.nav, required this.onNavigate});
  final List<_NavEntry> nav;
  final ValueChanged<int> onNavigate;

  @override
  Widget build(BuildContext context) => Wrap(
    spacing: 14,
    runSpacing: 14,
    children: [
      _OverviewCard(
        icon: Icons.admin_panel_settings_outlined,
        title: 'Admin console',
        text: 'View the user directory, change roles, and remove accounts.',
        onTap: () {
          final index = nav.indexWhere((entry) => entry.adminOnly);
          if (index != -1) onNavigate(index);
        },
      ),
      _OverviewCard(
        icon: Icons.person_outline,
        title: 'Profile',
        text: 'Manage your own account details.',
        onTap: () {
          final index = nav.indexWhere((entry) => entry.label == 'Profile');
          if (index != -1) onNavigate(index);
        },
      ),
    ],
  );
}

class _OverviewCard extends StatelessWidget {
  const _OverviewCard({
    required this.icon,
    required this.title,
    required this.text,
    required this.onTap,
  });
  final IconData icon;
  final String title;
  final String text;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => SizedBox(
    width: 240,
    child: Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, color: Brand.primary),
              const SizedBox(height: 16),
              Text(
                title,
                style: Theme.of(
                  context,
                ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 6),
              Text(text, style: const TextStyle(color: Colors.black54)),
              const SizedBox(height: 10),
              const Row(
                children: [
                  Text(
                    'Open',
                    style: TextStyle(
                      color: Brand.primary,
                      fontWeight: FontWeight.w600,
                      fontSize: 13,
                    ),
                  ),
                  SizedBox(width: 4),
                  Icon(Icons.arrow_forward, size: 14, color: Brand.primary),
                ],
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

class ChatPage extends StatefulWidget {
  const ChatPage({required this.api, super.key});
  final ApiService api;

  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final question = TextEditingController();
  final sessionSearch = TextEditingController();
  final sessions = <Map<String, dynamic>>[];
  final messages = <Map<String, dynamic>>[];
  String? sessionId;
  bool loadingSessions = true;
  bool sending = false;
  String? error;

  @override
  void initState() {
    super.initState();
    _loadSessions();
  }

  @override
  void dispose() {
    question.dispose();
    sessionSearch.dispose();
    super.dispose();
  }

  Future<void> _loadSessions() async {
    try {
      final result = await widget.api.listChatSessions();
      if (mounted) {
        setState(() {
          sessions
            ..clear()
            ..addAll(result.cast<Map<String, dynamic>>());
          loadingSessions = false;
        });
      }
    } on ApiException catch (exception) {
      if (mounted)
        setState(() {
          error = exception.message;
          loadingSessions = false;
        });
    }
  }

  Future<void> _selectSession(String id) async {
    try {
      final result = await widget.api.chatHistory(id);
      if (!mounted) return;
      setState(() {
        sessionId = id;
        messages
          ..clear()
          ..addAll(result.cast<Map<String, dynamic>>());
      });
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    }
  }

  void _newSession() => setState(() {
    sessionId = null;
    messages.clear();
    error = null;
  });

  Future<void> _deleteSession(String id) async {
    try {
      await widget.api.deleteChatSession(id);
      if (sessionId == id) _newSession();
      await _loadSessions();
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    }
  }

  Future<void> _send() async {
    final text = question.text.trim();
    if (text.isEmpty || sending) return;
    question.clear();
    setState(() {
      sending = true;
      error = null;
      messages.add({'role': 'user', 'content': text});
      messages.add({'role': 'assistant', 'content': ''});
    });
    try {
      await widget.api.streamChat(
        question: text,
        sessionId: sessionId,
        onSession: (id) => setState(() => sessionId = id),
        onToken: (token) => setState(() => messages.last['content'] += token),
        onSources: (_) {},
      );
      await _loadSessions();
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } catch (_) {
      if (mounted) setState(() => error = 'Could not connect to RAG Bot.');
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  List<Map<String, dynamic>> get filteredSessions {
    final term = sessionSearch.text.trim().toLowerCase();
    if (term.isEmpty) return sessions;
    return sessions
        .where(
          (session) =>
              (session['title'] ?? '').toString().toLowerCase().contains(term),
        )
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    final isCompact = MediaQuery.sizeOf(context).width < 760;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: SizedBox(
        height: MediaQuery.sizeOf(context).height - 120,
        child: isCompact
            ? _mobileChat(context)
            : Row(
                children: [
                  SizedBox(width: 260, child: _sessionRail(context)),
                  const VerticalDivider(width: 1),
                  Expanded(child: _conversation(context)),
                ],
              ),
      ),
    );
  }

  Widget _mobileChat(BuildContext context) => Column(
    children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(14, 12, 14, 8),
        child: Row(
          children: [
            OutlinedButton.icon(
              onPressed: () => showModalBottomSheet<void>(
                context: context,
                isScrollControlled: true,
                builder: (_) => SafeArea(
                  child: SizedBox(
                    height: MediaQuery.sizeOf(context).height * 0.72,
                    child: _sessionRail(context),
                  ),
                ),
              ),
              icon: const Icon(Icons.chat_bubble_outline, size: 18),
              label: Text('Chats (${sessions.length})'),
            ),
            const Spacer(),
            IconButton(
              tooltip: 'New chat',
              onPressed: _newSession,
              icon: const Icon(Icons.add_circle_outline),
            ),
          ],
        ),
      ),
      const Divider(height: 1),
      Expanded(child: _conversation(context)),
    ],
  );

  Widget _sessionRail(BuildContext context) => Container(
    color: const Color(0xfff1f5f2),
    padding: const EdgeInsets.all(14),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            const Icon(Icons.auto_awesome, color: Brand.primary),
            const SizedBox(width: 8),
            Text(
              'RAG Bot',
              style: Theme.of(
                context,
              ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
            ),
          ],
        ),
        const SizedBox(height: 14),
        FilledButton.icon(
          onPressed: _newSession,
          icon: const Icon(Icons.add),
          label: const Text('New chat'),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: sessionSearch,
          onChanged: (_) => setState(() {}),
          decoration: const InputDecoration(
            prefixIcon: Icon(Icons.search),
            hintText: 'Search chats',
            isDense: true,
          ),
        ),
        const SizedBox(height: 12),
        if (loadingSessions) const LinearProgressIndicator(),
        Expanded(
          child: ListView(
            children: [
              for (final session in filteredSessions)
                ListTile(
                  dense: true,
                  selected: session['id'] == sessionId,
                  leading: const Icon(Icons.chat_bubble_outline, size: 18),
                  title: Text(
                    session['title']?.toString() ?? 'Untitled chat',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  onTap: () => _selectSession(session['id'].toString()),
                  trailing: IconButton(
                    icon: const Icon(Icons.delete_outline, size: 18),
                    onPressed: () => _deleteSession(session['id'].toString()),
                  ),
                ),
              if (!loadingSessions && filteredSessions.isEmpty)
                const Padding(
                  padding: EdgeInsets.all(12),
                  child: Text(
                    'No chats yet.',
                    style: TextStyle(color: Colors.black54),
                  ),
                ),
            ],
          ),
        ),
        OutlinedButton.icon(
          onPressed: _pickDocument,
          icon: const Icon(Icons.attach_file),
          label: const Text('Upload document'),
        ),
      ],
    ),
  );

  Widget _conversation(BuildContext context) => Column(
    children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 14, 16, 12),
        child: Row(
          children: [
            const CircleAvatar(
              backgroundColor: Color(0xffe6f1ed),
              child: Icon(Icons.auto_awesome, color: Brand.primary),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'RAG Bot',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const Text(
                    'Your documents, made conversational.',
                    style: TextStyle(color: Colors.black54),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
      const Divider(height: 1),
      Expanded(child: messages.isEmpty ? _emptyChat(context) : _messageList()),
      if (error != null)
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Text(
            error!,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        ),
      Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(
              child: TextField(
                controller: question,
                minLines: 1,
                maxLines: 5,
                onSubmitted: (_) => _send(),
                decoration: const InputDecoration(
                  hintText: 'Ask RAG Bot about your documents...',
                ),
              ),
            ),
            const SizedBox(width: 10),
            IconButton.filled(
              tooltip: 'Send',
              onPressed: sending ? null : _send,
              icon: sending
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.arrow_upward),
            ),
          ],
        ),
      ),
    ],
  );

  Widget _emptyChat(BuildContext context) => Center(
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.forum_outlined, size: 48, color: Color(0xffb4c8c1)),
        const SizedBox(height: 14),
        Text(
          'Start a focused study chat',
          style: Theme.of(
            context,
          ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 6),
        const Text(
          'Upload a document, then ask a question.',
          style: TextStyle(color: Colors.black54),
        ),
      ],
    ),
  );

  Widget _messageList() => ListView.builder(
    padding: const EdgeInsets.all(24),
    itemCount: messages.length,
    itemBuilder: (context, index) {
      final message = messages[index];
      final user = message['role'] == 'user';
      return Align(
        alignment: user ? Alignment.centerRight : Alignment.centerLeft,
        child: Container(
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.all(14),
          constraints: const BoxConstraints(maxWidth: 680),
          decoration: BoxDecoration(
            color: user ? Brand.primary : const Color(0xffedf3f0),
            borderRadius: BorderRadius.circular(16),
          ),
          child: user
              ? Text(
                  message['content']?.toString() ?? '',
                  style: const TextStyle(color: Colors.white, height: 1.45),
                )
              : MarkdownBody(
                  data: message['content']?.toString() ?? '',
                  selectable: true,
                  styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context))
                      .copyWith(
                        p: const TextStyle(
                          color: Color(0xff1c211f),
                          height: 1.5,
                        ),
                        h1: const TextStyle(
                          fontSize: 24,
                          fontWeight: FontWeight.w800,
                          color: Color(0xff153a37),
                        ),
                        h2: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w800,
                          color: Color(0xff153a37),
                        ),
                        h3: const TextStyle(
                          fontSize: 17,
                          fontWeight: FontWeight.w700,
                          color: Color(0xff245c58),
                        ),
                        code: const TextStyle(
                          fontFamily: 'monospace',
                          color: Color(0xff153a37),
                        ),
                        codeblockDecoration: BoxDecoration(
                          color: Color(0xffdfeae5),
                          borderRadius: BorderRadius.all(Radius.circular(10)),
                        ),
                        blockquoteDecoration: const BoxDecoration(
                          border: Border(
                            left: BorderSide(color: Brand.accent, width: 4),
                          ),
                        ),
                        tableHead: const TextStyle(
                          fontWeight: FontWeight.w800,
                          color: Color(0xff153a37),
                        ),
                      ),
                ),
        ),
      );
    },
  );

  Future<void> _pickDocument() async {
    final result = await FilePicker.platform.pickFiles(withData: true);
    final file = result?.files.single;
    if (file?.bytes == null) return;
    try {
      await widget.api.uploadDocument(file!.name, file.bytes!);
      if (mounted)
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Document uploaded and indexed.')),
        );
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    }
  }
}

class DocumentsPage extends StatefulWidget {
  const DocumentsPage({required this.api, super.key});
  final ApiService api;
  @override
  State<DocumentsPage> createState() => _DocumentsPageState();
}

class _DocumentsPageState extends State<DocumentsPage> {
  List<dynamic> documents = [];
  String? error;
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final result = await widget.api.listDocuments();
      if (mounted) setState(() => documents = result);
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    }
  }

  @override
  Widget build(BuildContext context) => ListView(
    children: [
      Text(
        'Document library',
        style: Theme.of(
          context,
        ).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800),
      ),
      const SizedBox(height: 8),
      const Text('These files power RAG Bot and your study tools.'),
      const SizedBox(height: 24),
      if (error != null)
        Text(
          error!,
          style: TextStyle(color: Theme.of(context).colorScheme.error),
        ),
      for (final document in documents)
        Card(
          child: ListTile(
            leading: const Icon(
              Icons.description_outlined,
              color: Brand.primary,
            ),
            title: Text(document['filename']?.toString() ?? 'Untitled'),
            subtitle: Text('${document['chunk_count'] ?? 0} indexed chunks'),
          ),
        ),
      if (documents.isEmpty && error == null)
        const Card(
          child: Padding(
            padding: EdgeInsets.all(24),
            child: Text(
              'No documents indexed yet. Open RAG Bot to upload one.',
            ),
          ),
        ),
    ],
  );
}

class ProfilePage extends StatefulWidget {
  const ProfilePage({required this.api, required this.user, super.key});
  final ApiService api;
  final User user;

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  final form = <String, TextEditingController>{};
  bool editing = false;
  bool loading = true;
  bool saving = false;
  String? error;

  static const fields = [
    'full_name',
    'email',
    'phone',
    'location',
    'college_name',
    'degree',
    'branch',
    'college_start',
    'college_end',
    'cgpa',
    'school_name',
    'school_detail',
    'school_dates',
    'school_score',
  ];

  @override
  void initState() {
    super.initState();
    for (final field in fields) form[field] = TextEditingController();
    _load();
  }

  @override
  void dispose() {
    for (final controller in form.values) controller.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final profile = await widget.api.getProfile();
      _fill(profile);
    } on ApiException catch (exception) {
      if (exception.statusCode != 404 && mounted)
        setState(() => error = exception.message);
      if (exception.statusCode == 404) {
        _fill({
          'full_name': widget.user.name,
          'email': widget.user.email,
          'college_name': widget.user.collegeName,
          'college_year': widget.user.collegeYear,
        });
      }
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  void _fill(Map<String, dynamic> profile) {
    for (final field in fields)
      form[field]!.text = profile[field]?.toString() ?? '';
  }

  Future<void> _save() async {
    setState(() {
      saving = true;
      error = null;
    });
    try {
      final profile = {
        for (final field in fields) field: form[field]!.text.trim(),
      };
      final saved = await widget.api.saveProfile(profile);
      _fill(saved);
      if (mounted) {
        setState(() {
          editing = false;
        });
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Profile saved.')));
      }
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  Widget _field(String key, {int maxLines = 1}) => TextField(
    controller: form[key],
    enabled: editing,
    maxLines: maxLines,
    decoration: InputDecoration(labelText: _label(key)),
  );

  String _label(String key) => key
      .split('_')
      .map((word) => word[0].toUpperCase() + word.substring(1))
      .join(' ');

  @override
  Widget build(BuildContext context) => ListView(
    children: [
      Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Profile',
                  style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  editing
                      ? 'Keep your academic context current.'
                      : 'Your learning identity and academic context.',
                  style: const TextStyle(color: Colors.black54),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          editing
              ? FilledButton.icon(
                  onPressed: saving ? null : _save,
                  icon: const Icon(Icons.save_outlined),
                  label: Text(saving ? 'Saving...' : 'Save'),
                )
              : OutlinedButton.icon(
                  onPressed: () => setState(() => editing = true),
                  icon: const Icon(Icons.edit_outlined),
                  label: const Text('Edit profile'),
                ),
        ],
      ),
      const SizedBox(height: 24),
      if (error != null)
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Text(
            error!,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        ),
      if (loading) const LinearProgressIndicator(),
      if (!loading)
        LayoutBuilder(
          builder: (context, constraints) {
            final narrow = constraints.maxWidth < 760;
            final personal =
                _profileCard('Personal information', Icons.person_outline, [
                  _field('full_name'),
                  _field('email'),
                  _field('phone'),
                  _field('location'),
                  _field('college_name'),
                ]);
            final academic =
                _profileCard('Academic journey', Icons.school_outlined, [
                  _field('degree'),
                  _field('branch'),
                  _field('college_start'),
                  _field('college_end'),
                  _field('cgpa'),
                ]);
            final background =
                _profileCard('Earlier education', Icons.menu_book_outlined, [
                  _field('school_name'),
                  _field('school_detail', maxLines: 2),
                  _field('school_dates'),
                  _field('school_score'),
                ]);
            return Column(
              children: [
                narrow
                    ? personal
                    : Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(child: personal),
                          const SizedBox(width: 18),
                          Expanded(child: academic),
                        ],
                      ),
                const SizedBox(height: 18),
                narrow ? academic : background,
                if (narrow) ...[const SizedBox(height: 18), background],
              ],
            );
          },
        ),
    ],
  );

  Widget _profileCard(String title, IconData icon, List<Widget> children) =>
      Card(
        child: Padding(
          padding: const EdgeInsets.all(22),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(icon, color: Brand.primary),
                  const SizedBox(width: 10),
                  Text(
                    title,
                    style: const TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 16,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 18),
              for (final child in children)
                Padding(
                  padding: const EdgeInsets.only(bottom: 14),
                  child: child,
                ),
            ],
          ),
        ),
      );
}

class StudyPage extends StatefulWidget {
  const StudyPage({required this.api, super.key});
  final ApiService api;

  @override
  State<StudyPage> createState() => _StudyPageState();
}

class _StudyPageState extends State<StudyPage> {
  List<dynamic> documents = [];
  List<dynamic> questions = [];
  List<dynamic> weakTopics = [];
  Map<String, dynamic>? plan;
  String? selectedDocument;
  String? error;
  bool loading = true;
  bool working = false;
  bool exportingPlan = false;
  bool submitted = false; // NEW — true once the current quiz has been graded
  final count = TextEditingController(text: '5');
  final threshold = TextEditingController(text: '0.7');
  final vivaRole = TextEditingController(text: 'Python Developer');
  final vivaAnswer = TextEditingController();
  final answers = <int, int>{};
  String? vivaSessionId;
  String? vivaQuestion;

  @override
  void initState() {
    super.initState();
    _loadStudyData();
  }

  @override
  void dispose() {
    count.dispose();
    threshold.dispose();
    vivaRole.dispose();
    vivaAnswer.dispose();
    super.dispose();
  }

  Future<void> _loadStudyData() async {
    try {
      final results = await Future.wait([
        widget.api.listDocuments(),
        widget.api.weakTopics(),
      ]);
      if (!mounted) return;
      setState(() {
        documents = results[0] as List<dynamic>;
        weakTopics =
            (results[1] as Map<String, dynamic>)['weak_topics']
                as List<dynamic>? ??
            [];
        loading = false;
      });
      if (documents.isNotEmpty) {
        selectedDocument ??= documents.first['document_id']?.toString();
      }
    } on ApiException catch (exception) {
      if (mounted) {
        setState(() {
          error = exception.message;
          loading = false;
        });
      }
    }
  }

  Future<void> _generateQuiz() async {
    if (selectedDocument == null) return;
    setState(() {
      working = true;
      error = null;
    });
    try {
      final result = await widget.api.generateQuiz(
        documentId: selectedDocument!,
        questionCount: int.tryParse(count.text) ?? 5,
      );
      setState(() {
        questions = result['questions'] as List<dynamic>? ?? [];
        answers.clear();
        submitted = false; // NEW — reset review state for the new quiz
      });
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) setState(() => working = false);
    }
  }

  Future<void> _submitQuiz() async {
    if (questions.isEmpty) return;
    setState(() => working = true);
    try {
      final attempts = <Map<String, dynamic>>[];
      for (var index = 0; index < questions.length; index++) {
        final question = questions[index] as Map<String, dynamic>;
        final correctOption = (question['correct_option'] as num).toInt();
        attempts.add({
          'document_id': selectedDocument,
          'concept_tag': question['concept_tag'],
          'correct': answers[index] == correctOption,
        });
      }
      await widget.api.submitQuiz(attempts);
      if (mounted) setState(() => submitted = true); // NEW — reveal colors
      await _loadStudyData();
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Quiz results saved.')));
      }
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) setState(() => working = false);
    }
  }

  Future<void> _loadWeakTopics() async {
    try {
      final result = await widget.api.weakTopics(
        threshold: double.tryParse(threshold.text) ?? 0.7,
      );
      if (mounted) {
        setState(
          () => weakTopics = result['weak_topics'] as List<dynamic>? ?? [],
        );
      }
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    }
  }

  Future<void> _createPlan() async {
    if (selectedDocument == null) return;
    setState(() => working = true);
    try {
      plan = await widget.api.createStudyPlan(
        syllabusId: selectedDocument!,
        weakTopics: weakTopics.cast<Map<String, dynamic>>(),
      );
      if (mounted) setState(() {});
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) setState(() => working = false);
    }
  }

  Future<void> _exportPlan() async {
    final planId = plan?['plan_id']?.toString();
    if (planId == null || planId.isEmpty || exportingPlan) return;
    setState(() {
      exportingPlan = true;
      error = null;
    });
    try {
      final ics = await widget.api.exportStudyPlan(planId);
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('Calendar export ready'),
          content: SizedBox(
            width: 560,
            child: SingleChildScrollView(child: SelectableText(ics)),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Close'),
            ),
          ],
        ),
      );
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) setState(() => exportingPlan = false);
    }
  }

  @override
  Widget build(BuildContext context) => ListView(
    children: [
      Text(
        'Study Zone',
        style: Theme.of(
          context,
        ).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800),
      ),
      const SizedBox(height: 6),
      const Text(
        'Practice what you know, find what needs work, and turn it into a plan.',
        style: TextStyle(color: Colors.black54),
      ),
      const SizedBox(height: 24),
      if (error != null)
        Text(
          error!,
          style: TextStyle(color: Theme.of(context).colorScheme.error),
        ),
      if (loading) const LinearProgressIndicator(),
      if (!loading) ...[
        _studySetup(),
        const SizedBox(height: 18),
        _quizCard(),
        const SizedBox(height: 18),
        _weakTopicsCard(),
        const SizedBox(height: 18),
        _planCard(),
        const SizedBox(height: 18),
        _vivaCard(),
      ],
    ],
  );

  Widget _studySetup() => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact = constraints.maxWidth < 560;
          final documentWidth = compact
              ? constraints.maxWidth
              : constraints.maxWidth < 360
              ? constraints.maxWidth
              : 360.0;
          return Wrap(
            spacing: 14,
            runSpacing: 14,
            children: [
              SizedBox(
                width: documentWidth,
                child: DropdownButtonFormField<String>(
                  initialValue: selectedDocument,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Choose a study document',
                  ),
                  items: [
                    for (final document in documents)
                      DropdownMenuItem(
                        value: document['document_id']?.toString(),
                        child: Text(
                          document['filename']?.toString() ?? 'Untitled',
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                  onChanged: (value) =>
                      setState(() => selectedDocument = value),
                ),
              ),
              SizedBox(
                width: compact ? constraints.maxWidth : null,
                child: Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    SizedBox(
                      width: 110,
                      child: TextField(
                        controller: count,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'Questions',
                        ),
                      ),
                    ),
                    FilledButton.icon(
                      onPressed: working || selectedDocument == null
                          ? null
                          : _generateQuiz,
                      icon: const Icon(Icons.auto_awesome),
                      label: const Text('Generate quiz'),
                    ),
                  ],
                ),
              ),
            ],
          );
        },
      ),
    ),
  );

  // ---------------------------------------------------------------------
  // Quiz card — now shows a score summary and swaps the action button
  // between "Submit quiz" (pre-submit) and "Try another quiz" (post-submit)
  // ---------------------------------------------------------------------
  Widget _quizCard() {
    final correctCount = questions.asMap().entries.where((entry) {
      final q = entry.value as Map<String, dynamic>;
      final correctOption = (q['correct_option'] as num?)?.toInt();
      return answers[entry.key] == correctOption;
    }).length;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Practice quiz',
                  style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
                ),
                if (questions.isNotEmpty && !submitted)
                  Text(
                    '${answers.length}/${questions.length} answered',
                    style: const TextStyle(color: Colors.black54),
                  ),
                if (submitted)
                  Text(
                    '$correctCount/${questions.length} correct',
                    style: TextStyle(
                      fontWeight: FontWeight.w800,
                      color: correctCount == questions.length
                          ? const Color(0xff2e7d46)
                          : Brand.accent,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 14),
            if (questions.isEmpty)
              const Text('Generate a quiz from an indexed document to begin.'),
            for (var index = 0; index < questions.length; index++)
              _questionCard(index, questions[index] as Map<String, dynamic>),
            if (questions.isNotEmpty)
              Align(
                alignment: Alignment.centerRight,
                child: submitted
                    ? OutlinedButton.icon(
                        onPressed: working ? null : _generateQuiz,
                        icon: const Icon(Icons.refresh),
                        label: const Text('Try another quiz'),
                      )
                    : FilledButton.icon(
                        onPressed:
                            (working || answers.length != questions.length)
                            ? null
                            : _submitQuiz,
                        icon: const Icon(Icons.check),
                        label: const Text('Submit quiz'),
                      ),
              ),
          ],
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------
  // One question: plain radio-style options before submit,
  // green (correct) / red (wrong-selected) highlighting after submit,
  // plus the explanation revealed underneath.
  // ---------------------------------------------------------------------
  Widget _questionCard(int index, Map<String, dynamic> question) {
    final options = question['options'] as List;
    final correctIndex = (question['correct_option'] as num?)?.toInt();
    final selectedIndex = answers[index];
    final gotItRight = submitted && selectedIndex == correctIndex;

    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          border: Border.all(
            color: !submitted
                ? const Color(0xffe0e6e2)
                : (gotItRight
                      ? const Color(0xff2e7d46)
                      : const Color(0xffc62828)),
          ),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Text(
                    '${index + 1}. ${question['question']}',
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
                if (submitted)
                  Icon(
                    gotItRight ? Icons.check_circle : Icons.cancel,
                    color: gotItRight
                        ? const Color(0xff2e7d46)
                        : const Color(0xffc62828),
                  ),
              ],
            ),
            const SizedBox(height: 10),
            for (
              var optionIndex = 0;
              optionIndex < options.length;
              optionIndex++
            )
              _optionTile(
                text: options[optionIndex].toString(),
                isSelected: selectedIndex == optionIndex,
                isCorrect: optionIndex == correctIndex,
                submitted: submitted,
                onTap: submitted
                    ? null
                    : () => setState(() => answers[index] = optionIndex),
              ),
            if (submitted && question['explanation'] != null) ...[
              const SizedBox(height: 6),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0xfff1f5f2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  question['explanation'].toString(),
                  style: const TextStyle(color: Colors.black87, fontSize: 13),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------
  // A single answer option. Behaves like a plain radio row before submit;
  // turns green if it's the correct answer, red if it's the student's
  // wrong pick, and neutral otherwise, once `submitted` is true.
  // ---------------------------------------------------------------------
  Widget _optionTile({
    required String text,
    required bool isSelected,
    required bool isCorrect,
    required bool submitted,
    required VoidCallback? onTap,
  }) {
    Color background = Colors.white;
    Color border = const Color(0xffe0e6e2);
    IconData icon = Icons.radio_button_off;
    Color iconColor = Colors.black38;
    double borderWidth = 1;

    if (submitted) {
      if (isCorrect) {
        background = const Color(0xffe6f6ea);
        border = const Color(0xff2e7d46);
        icon = Icons.check_circle;
        iconColor = const Color(0xff2e7d46);
        borderWidth = 1.6;
      } else if (isSelected) {
        background = const Color(0xfffdeaea);
        border = const Color(0xffc62828);
        icon = Icons.cancel;
        iconColor = const Color(0xffc62828);
        borderWidth = 1.6;
      } else {
        icon = Icons.circle_outlined;
      }
    } else if (isSelected) {
      background = Brand.primary.withValues(alpha: 0.08);
      border = Brand.primary;
      icon = Icons.radio_button_checked;
      iconColor = Brand.primary;
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Material(
        color: background,
        borderRadius: BorderRadius.circular(10),
        child: InkWell(
          borderRadius: BorderRadius.circular(10),
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            decoration: BoxDecoration(
              border: Border.all(color: border, width: borderWidth),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(
              children: [
                Icon(icon, size: 18, color: iconColor),
                const SizedBox(width: 10),
                Expanded(child: Text(text)),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _weakTopicsCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            LayoutBuilder(
              builder: (context, constraints) => Wrap(
                alignment: WrapAlignment.spaceBetween,
                crossAxisAlignment: WrapCrossAlignment.center,
                runSpacing: 10,
                children: [
                  const Text(
                    'Weak topics',
                    style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
                  ),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      SizedBox(
                        width: constraints.maxWidth < 180
                            ? constraints.maxWidth - 48
                            : 100,
                        child: TextField(
                          controller: threshold,
                          decoration: const InputDecoration(
                            labelText: 'Threshold',
                          ),
                          keyboardType: const TextInputType.numberWithOptions(
                            decimal: true,
                          ),
                        ),
                      ),
                      IconButton(
                        tooltip: 'Refresh weak topics',
                        onPressed: _loadWeakTopics,
                        icon: const Icon(Icons.refresh),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            if (weakTopics.isEmpty)
              const Text(
                'No weak topics yet. Submit a quiz to build your learning signals.',
              ),
            for (final topic in weakTopics)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.flag_outlined, color: Brand.accent),
                title: Text(topic['concept_tag']?.toString() ?? 'Topic'),
                subtitle: Text(
                  '${((topic['accuracy'] ?? 0) * 100).round()}% accuracy · ${topic['attempt_count'] ?? topic['attempts'] ?? 0} attempts',
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _planCard() => Card(
    child: Padding(
      padding: EdgeInsets.zero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 18),
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                colors: [Color(0xff173e3a), Brand.primary],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: .12),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(
                    Icons.calendar_month_rounded,
                    color: Brand.accent,
                  ),
                ),
                const SizedBox(width: 12),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Your study plan',
                        style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w800,
                          fontSize: 20,
                        ),
                      ),
                      SizedBox(height: 4),
                      Text(
                        'A focused sequence built from your syllabus and weak topics.',
                        style: TextStyle(color: Colors.white70, height: 1.35),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          if (plan == null)
            Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Choose a syllabus above, then build a plan that turns its topics into dated study sessions.',
                  ),
                  const SizedBox(height: 16),
                  FilledButton.icon(
                    onPressed: working || selectedDocument == null
                        ? null
                        : _createPlan,
                    icon: const Icon(Icons.auto_awesome_rounded),
                    label: const Text('Build my study plan'),
                  ),
                ],
              ),
            ),
          if (plan != null) ...[
            _StudyPlanView(
              plan: plan!,
              working: working,
              exporting: exportingPlan,
              onRebuild: _createPlan,
              onExport: _exportPlan,
            ),
          ],
        ],
      ),
    ),
  );

  Widget _vivaCard() => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Mock viva',
            style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
          ),
          const SizedBox(height: 6),
          const Text(
            'Practice a role-focused interview before the real one.',
            style: TextStyle(color: Colors.black54),
          ),
          const SizedBox(height: 14),
          TextField(
            controller: vivaRole,
            decoration: const InputDecoration(labelText: 'Target role'),
          ),
          const SizedBox(height: 12),
          if (vivaQuestion != null) ...[
            Text(
              vivaQuestion!,
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: vivaAnswer,
              minLines: 2,
              maxLines: 5,
              decoration: const InputDecoration(labelText: 'Your answer'),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                FilledButton.icon(
                  onPressed: working ? null : _continueViva,
                  icon: const Icon(Icons.arrow_forward),
                  label: const Text('Submit answer'),
                ),
                const SizedBox(width: 10),
                TextButton(
                  onPressed: working ? null : _endViva,
                  child: const Text('End viva'),
                ),
              ],
            ),
          ] else
            FilledButton.icon(
              onPressed: working ? null : _startViva,
              icon: const Icon(Icons.mic_none),
              label: const Text('Start mock viva'),
            ),
        ],
      ),
    ),
  );

  Future<void> _startViva() async {
    setState(() => working = true);
    try {
      final result = await widget.api.startInterview(
        targetRole: vivaRole.text.trim(),
      );
      if (mounted) {
        setState(() {
          vivaSessionId = result['session_id']?.toString();
          vivaQuestion = result['question']?.toString();
        });
      }
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) setState(() => working = false);
    }
  }

  Future<void> _continueViva() async {
    if (vivaSessionId == null || vivaAnswer.text.trim().isEmpty) return;
    setState(() => working = true);
    try {
      final result = await widget.api.continueInterview(
        sessionId: vivaSessionId!,
        answer: vivaAnswer.text.trim(),
      );
      vivaAnswer.clear();
      if (mounted) {
        setState(
          () => vivaQuestion =
              result['question']?.toString() ??
              result['next_question']?.toString(),
        );
      }
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) setState(() => working = false);
    }
  }

  Future<void> _endViva() async {
    if (vivaSessionId == null) return;
    try {
      await widget.api.endInterview(vivaSessionId!);
      if (mounted) {
        setState(() {
          vivaSessionId = null;
          vivaQuestion = null;
          vivaAnswer.clear();
        });
      }
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    }
  }
}

class _StudyPlanView extends StatelessWidget {
  const _StudyPlanView({
    required this.plan,
    required this.working,
    required this.exporting,
    required this.onRebuild,
    required this.onExport,
  });

  final Map<String, dynamic> plan;
  final bool working;
  final bool exporting;
  final VoidCallback onRebuild;
  final VoidCallback onExport;

  List<_PlanSession> get sessions => ((plan['sessions'] as List?) ?? [])
      .whereType<Map>()
      .map(
        (session) => _PlanSession.fromJson(Map<String, dynamic>.from(session)),
      )
      .toList();

  @override
  Widget build(BuildContext context) {
    final items = sessions;
    final reviewCount = items.where((item) => item.isReview).length;
    final topics = items.map((item) => item.topic).toSet().length;
    final grouped = <String, List<_PlanSession>>{};
    for (final item in items) {
      grouped.putIfAbsent(item.date, () => []).add(item);
    }

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  '${items.length} sessions across $topics topics',
                  style: const TextStyle(
                    fontWeight: FontWeight.w800,
                    fontSize: 17,
                  ),
                ),
              ),
              IconButton(
                tooltip: 'Rebuild study plan',
                onPressed: working ? null : onRebuild,
                icon: const Icon(Icons.refresh_rounded),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _PlanSummary(
            sessions: items.length,
            reviewSessions: reviewCount,
            topics: topics,
          ),
          const SizedBox(height: 22),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Your schedule',
                    style: TextStyle(fontWeight: FontWeight.w800, fontSize: 17),
                  ),
                  SizedBox(height: 3),
                  Text(
                    'Start with the next session and keep the rhythm.',
                    style: TextStyle(color: Colors.black54, fontSize: 12),
                  ),
                ],
              ),
              OutlinedButton.icon(
                onPressed: exporting ? null : onExport,
                icon: exporting
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.download_outlined, size: 18),
                label: Text(exporting ? 'Preparing...' : 'Calendar'),
              ),
            ],
          ),
          const SizedBox(height: 14),
          if (items.isEmpty)
            const _PlanEmptyState()
          else
            for (final entry in grouped.entries) ...[
              _PlanDayHeader(
                date: entry.key,
                isFirst: entry.key == grouped.keys.first,
              ),
              for (final session in entry.value)
                _PlanSessionCard(session: session),
            ],
        ],
      ),
    );
  }
}

class _PlanSession {
  const _PlanSession({
    required this.date,
    required this.topic,
    this.sourceWeek,
    required this.sessionType,
  });

  final String date;
  final String topic;
  final String? sourceWeek;
  final String sessionType;

  bool get isReview => sessionType == 'weak-topic-review';

  factory _PlanSession.fromJson(Map<String, dynamic> json) => _PlanSession(
    date: json['date']?.toString() ?? '',
    topic: json['topic']?.toString().trim().isNotEmpty == true
        ? json['topic'].toString()
        : 'Study session',
    sourceWeek:
        json['source_date_or_week']?.toString().trim().isNotEmpty == true
        ? json['source_date_or_week'].toString()
        : null,
    sessionType: json['session_type']?.toString() ?? 'study-session',
  );
}

class _PlanSummary extends StatelessWidget {
  const _PlanSummary({
    required this.sessions,
    required this.reviewSessions,
    required this.topics,
  });

  final int sessions;
  final int reviewSessions;
  final int topics;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Expanded(
        child: _PlanMetric(
          icon: Icons.event_note_rounded,
          value: '$sessions',
          label: 'Sessions',
          color: Brand.primary,
        ),
      ),
      const SizedBox(width: 8),
      Expanded(
        child: _PlanMetric(
          icon: Icons.track_changes_rounded,
          value: '$reviewSessions',
          label: 'Reviews',
          color: Brand.accent,
        ),
      ),
      const SizedBox(width: 8),
      Expanded(
        child: _PlanMetric(
          icon: Icons.menu_book_rounded,
          value: '$topics',
          label: 'Topics',
          color: const Color(0xff467c73),
        ),
      ),
    ],
  );
}

class _PlanMetric extends StatelessWidget {
  const _PlanMetric({
    required this.icon,
    required this.value,
    required this.label,
    required this.color,
  });

  final IconData icon;
  final String value;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
    decoration: BoxDecoration(
      color: color.withValues(alpha: .08),
      borderRadius: BorderRadius.circular(13),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 19, color: color),
        const SizedBox(height: 8),
        Text(
          value,
          style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
        ),
        Text(
          label,
          style: const TextStyle(color: Colors.black54, fontSize: 11),
        ),
      ],
    ),
  );
}

class _PlanDayHeader extends StatelessWidget {
  const _PlanDayHeader({required this.date, required this.isFirst});

  final String date;
  final bool isFirst;

  @override
  Widget build(BuildContext context) {
    final parsed = DateTime.tryParse(date);
    final day = parsed == null
        ? date
        : '${_weekday(parsed.weekday)}, ${_month(parsed.month)} ${parsed.day}';
    return Padding(
      padding: EdgeInsets.only(top: isFirst ? 0 : 18, bottom: 8),
      child: Row(
        children: [
          Container(
            width: 9,
            height: 9,
            decoration: const BoxDecoration(
              color: Brand.primary,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 9),
          Text(
            day,
            style: const TextStyle(
              fontWeight: FontWeight.w800,
              color: Brand.primaryDark,
            ),
          ),
          if (parsed != null && _sameDay(parsed, DateTime.now())) ...[
            const SizedBox(width: 8),
            const Text(
              'TODAY',
              style: TextStyle(
                color: Brand.accent,
                fontWeight: FontWeight.w800,
                fontSize: 10,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _PlanSessionCard extends StatelessWidget {
  const _PlanSessionCard({required this.session});

  final _PlanSession session;

  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.only(bottom: 9),
    decoration: BoxDecoration(
      color: session.isReview ? const Color(0xfffffaf1) : Colors.white,
      border: Border.all(
        color: session.isReview
            ? const Color(0xfff2dcae)
            : const Color(0xffe4ebe6),
      ),
      borderRadius: BorderRadius.circular(14),
    ),
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: session.isReview
                  ? const Color(0xffffedc9)
                  : const Color(0xffe5f0ec),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(
              session.isReview ? Icons.replay_rounded : Icons.menu_book_rounded,
              color: session.isReview ? const Color(0xffa86c16) : Brand.primary,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  session.topic,
                  style: const TextStyle(
                    fontWeight: FontWeight.w800,
                    fontSize: 15,
                  ),
                ),
                const SizedBox(height: 5),
                Text(
                  session.isReview
                      ? 'Review this weak topic and reinforce the fundamentals.'
                      : 'Study this syllabus topic and build your understanding.',
                  style: const TextStyle(
                    color: Colors.black54,
                    fontSize: 12,
                    height: 1.3,
                  ),
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    _PlanTag(
                      label: session.isReview
                          ? 'Weak-topic review'
                          : 'Syllabus study',
                      color: session.isReview
                          ? const Color(0xffa86c16)
                          : Brand.primary,
                    ),
                    if (session.sourceWeek != null)
                      _PlanTag(
                        label: session.sourceWeek!,
                        color: Colors.black54,
                      ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}

class _PlanTag extends StatelessWidget {
  const _PlanTag({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
    decoration: BoxDecoration(
      color: color.withValues(alpha: .09),
      borderRadius: BorderRadius.circular(6),
    ),
    child: Text(
      label,
      style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w700),
    ),
  );
}

class _PlanEmptyState extends StatelessWidget {
  const _PlanEmptyState();

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(18),
    decoration: BoxDecoration(
      color: const Color(0xfff1f5f2),
      borderRadius: BorderRadius.circular(14),
    ),
    child: const Text(
      'No sessions were returned for this plan yet.',
      style: TextStyle(color: Colors.black54),
    ),
  );
}

String _weekday(int value) =>
    const ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][value - 1];
String _month(int value) => const [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
][value - 1];
bool _sameDay(DateTime first, DateTime second) =>
    first.year == second.year &&
    first.month == second.month &&
    first.day == second.day;

class CareerPage extends StatefulWidget {
  const CareerPage({required this.api, super.key});
  final ApiService api;

  @override
  State<CareerPage> createState() => _CareerPageState();
}

class _CareerPageState extends State<CareerPage> {
  Map<String, dynamic>? dashboard;
  Map<String, dynamic>? gaps;
  String? error;
  bool loading = true;
  bool working = false;
  final projectTitle = TextEditingController();
  final projectStack = TextEditingController();
  final projectDescription = TextEditingController();
  final jobDescription = TextEditingController();
  final targetRole = TextEditingController(text: 'Python Developer');

  @override
  void initState() {
    super.initState();
    _loadDashboard();
  }

  @override
  void dispose() {
    projectTitle.dispose();
    projectStack.dispose();
    projectDescription.dispose();
    jobDescription.dispose();
    targetRole.dispose();
    super.dispose();
  }

  Future<void> _loadDashboard() async {
    try {
      final result = await widget.api.careerDashboard();
      if (mounted) setState(() => dashboard = result);
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> _addProject() async {
    if (projectTitle.text.trim().isEmpty || projectStack.text.trim().isEmpty)
      return;
    setState(() => working = true);
    try {
      await widget.api.addProject(
        title: projectTitle.text.trim(),
        techStack: projectStack.text.trim(),
        description: projectDescription.text.trim(),
      );
      projectTitle.clear();
      projectStack.clear();
      projectDescription.clear();
      await _loadDashboard();
      if (mounted) _notice('Project evidence added.');
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) setState(() => working = false);
    }
  }

  Future<void> _uploadCertificate() async {
    final result = await FilePicker.platform.pickFiles(withData: true);
    final file = result?.files.single;
    if (file?.bytes == null) return;
    setState(() => working = true);
    try {
      await widget.api.uploadCertificate(file!.name, file.bytes!);
      await _loadDashboard();
      if (mounted) _notice('Certificate added to your career profile.');
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) setState(() => working = false);
    }
  }

  Future<void> _runGapAnalysis() async {
    if (jobDescription.text.trim().isEmpty) return;
    setState(() => working = true);
    try {
      final result = await widget.api.gapAnalysis(jobDescription.text.trim());
      if (mounted) setState(() => gaps = result);
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) setState(() => working = false);
    }
  }

  Future<void> _generateResume() async {
    setState(() => working = true);
    try {
      final response = await widget.api.generateResume(
        targetRole: targetRole.text.trim(),
      );
      await saveDownload(
        response.bodyBytes,
        'academic-second-brain-resume.docx',
      );
      if (mounted) _notice('Resume downloaded successfully.');
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) setState(() => working = false);
    }
  }

  void _notice(String message) => ScaffoldMessenger.of(
    context,
  ).showSnackBar(SnackBar(content: Text(message)));

  @override
  Widget build(BuildContext context) {
    final summary = dashboard?['summary'] as Map<String, dynamic>? ?? {};
    final skills = dashboard?['skills'] as List<dynamic>? ?? [];
    final projects = dashboard?['projects'] as List<dynamic>? ?? [];
    final achievements = dashboard?['achievements'] as List<dynamic>? ?? [];
    return ListView(
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Career Zone',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Build proof of your ability, spot the next gap, and walk into interviews prepared.',
                    style: TextStyle(color: Colors.black54),
                  ),
                ],
              ),
            ),
            IconButton(
              tooltip: 'Refresh dashboard',
              onPressed: _loadDashboard,
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
        const SizedBox(height: 24),
        if (error != null)
          Text(
            error!,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        if (loading) const LinearProgressIndicator(),
        if (!loading) ...[
          _careerHero(summary),
          const SizedBox(height: 18),
          _evidenceSection(projects, achievements),
          const SizedBox(height: 18),
          _gapSection(),
          const SizedBox(height: 18),
          _launchSection(skills),
        ],
      ],
    );
  }

  Widget _careerHero(Map<String, dynamic> summary) => Card(
    color: Brand.primary,
    child: Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Your readiness, in motion',
            style: TextStyle(
              color: Colors.white,
              fontSize: 22,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Every project, certificate, quiz, and interview makes your next opportunity clearer.',
            style: TextStyle(color: Colors.white70),
          ),
          const SizedBox(height: 22),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              _metric('${summary['skill_count'] ?? 0}', 'Skills'),
              _metric('${summary['project_count'] ?? 0}', 'Projects'),
              _metric('${summary['achievement_count'] ?? 0}', 'Certificates'),
              _metric(
                '${summary['weak_topic_count'] ?? 0}',
                'Topics to improve',
              ),
            ],
          ),
        ],
      ),
    ),
  );

  Widget _metric(String value, String label) => Container(
    width: 135,
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: Colors.white.withValues(alpha: .12),
      borderRadius: BorderRadius.circular(12),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          value,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 24,
            fontWeight: FontWeight.w800,
          ),
        ),
        Text(
          label,
          style: const TextStyle(color: Colors.white70, fontSize: 12),
        ),
      ],
    ),
  );

  Widget _evidenceSection(
    List<dynamic> projects,
    List<dynamic> achievements,
  ) => LayoutBuilder(
    builder: (context, constraints) {
      final left = Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Add project evidence',
                style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
              ),
              const SizedBox(height: 14),
              TextField(
                controller: projectTitle,
                decoration: const InputDecoration(labelText: 'Project title'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: projectStack,
                decoration: const InputDecoration(labelText: 'Tech stack'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: projectDescription,
                maxLines: 3,
                decoration: const InputDecoration(
                  labelText: 'What did you build?',
                ),
              ),
              const SizedBox(height: 14),
              FilledButton.icon(
                onPressed: working ? null : _addProject,
                icon: const Icon(Icons.add),
                label: const Text('Add project'),
              ),
            ],
          ),
        ),
      );
      final right = Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'Proof library',
                    style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
                  ),
                  IconButton(
                    tooltip: 'Upload certificate',
                    onPressed: working ? null : _uploadCertificate,
                    icon: const Icon(Icons.upload_file),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              if (projects.isEmpty && achievements.isEmpty)
                const Text('Projects and certificates will appear here.'),
              for (final project in projects.take(3))
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.code, color: Brand.primary),
                  title: Text(project['title']?.toString() ?? 'Project'),
                  subtitle: Text(project['tech_stack']?.toString() ?? ''),
                ),
              for (final achievement in achievements.take(3))
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(
                    Icons.workspace_premium_outlined,
                    color: Brand.accent,
                  ),
                  title: Text(achievement['name']?.toString() ?? 'Certificate'),
                  subtitle: Text(achievement['awarded_at']?.toString() ?? ''),
                ),
            ],
          ),
        ),
      );
      return constraints.maxWidth < 800
          ? Column(children: [left, const SizedBox(height: 18), right])
          : Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: left),
                const SizedBox(width: 18),
                Expanded(child: right),
              ],
            );
    },
  );

  Widget _gapSection() => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Job fit analyzer',
            style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
          ),
          const SizedBox(height: 6),
          const Text(
            'Paste a job description and turn it into a focused preparation list.',
            style: TextStyle(color: Colors.black54),
          ),
          const SizedBox(height: 14),
          TextField(
            controller: jobDescription,
            minLines: 4,
            maxLines: 7,
            decoration: const InputDecoration(labelText: 'Job description'),
          ),
          const SizedBox(height: 14),
          FilledButton.icon(
            onPressed: working ? null : _runGapAnalysis,
            icon: const Icon(Icons.radar),
            label: const Text('Analyze skill gaps'),
          ),
          if (gaps != null) ...[
            const SizedBox(height: 18),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final skill
                    in (gaps!['required_skills'] as List<dynamic>? ?? []))
                  Chip(label: Text(skill.toString())),
              ],
            ),
            const SizedBox(height: 8),
            for (final gap in (gaps!['gaps'] as List<dynamic>? ?? []))
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.track_changes, color: Brand.accent),
                title: Text(gap['skill_name']?.toString() ?? 'Skill gap'),
                subtitle: const Text(
                  'Add evidence or practice this skill in Study Zone.',
                ),
              ),
          ],
        ],
      ),
    ),
  );

  Widget _launchSection(List<dynamic> skills) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Ready for the next step?',
            style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              SizedBox(
                width: 250,
                child: TextField(
                  controller: targetRole,
                  decoration: const InputDecoration(
                    labelText: 'Resume target role',
                  ),
                ),
              ),
              FilledButton.icon(
                onPressed: working ? null : _generateResume,
                icon: const Icon(Icons.description_outlined),
                label: const Text('Generate resume'),
              ),
              OutlinedButton.icon(
                onPressed: () =>
                    _notice('Open Study Zone to start your mock viva.'),
                icon: const Icon(Icons.mic_none),
                label: const Text('Practice mock viva'),
              ),
            ],
          ),
          if (skills.isNotEmpty) ...[
            const SizedBox(height: 18),
            const Text(
              'Your strongest signals',
              style: TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final skill in skills.take(8))
                  Chip(
                    avatar: const Icon(Icons.check, size: 16),
                    label: Text(skill['skill_name']?.toString() ?? 'Skill'),
                  ),
              ],
            ),
          ],
        ],
      ),
    ),
  );
}

class SkillsPage extends StatefulWidget {
  const SkillsPage({required this.api, super.key});
  final ApiService api;

  @override
  State<SkillsPage> createState() => _SkillsPageState();
}

class _SkillsPageState extends State<SkillsPage> {
  List<dynamic> skills = [];
  String? error;
  bool loading = true;
  bool working = false;
  final githubUsername = TextEditingController();
  final rawTerm = TextEditingController();
  final sourceRef = TextEditingController(text: 'student-profile');
  final confidence = TextEditingController(text: '0.8');
  Map<String, dynamic>? githubResult;

  @override
  void initState() {
    super.initState();
    _loadSkills();
  }

  @override
  void dispose() {
    githubUsername.dispose();
    rawTerm.dispose();
    sourceRef.dispose();
    confidence.dispose();
    super.dispose();
  }

  Future<void> _loadSkills() async {
    try {
      final result = await widget.api.getSkills();
      if (mounted)
        setState(() => skills = result['skills'] as List<dynamic>? ?? []);
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> _addEvidence() async {
    if (rawTerm.text.trim().isEmpty || sourceRef.text.trim().isEmpty) return;
    setState(() => working = true);
    try {
      await widget.api.addSkillEvidence(
        rawTerm: rawTerm.text.trim(),
        sourceType: 'manual',
        sourceRef: sourceRef.text.trim(),
        confidence: double.tryParse(confidence.text) ?? 0.8,
      );
      rawTerm.clear();
      await _loadSkills();
      if (mounted) _notice('Skill evidence added.');
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) setState(() => working = false);
    }
  }

  Future<void> _syncGithub() async {
    if (githubUsername.text.trim().isEmpty) return;
    setState(() => working = true);
    try {
      final result = await widget.api.syncGithub(githubUsername.text.trim());
      if (mounted) setState(() => githubResult = result);
      await _loadSkills();
      if (mounted) _notice('GitHub evidence synchronized.');
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) setState(() => working = false);
    }
  }

  void _notice(String message) => ScaffoldMessenger.of(
    context,
  ).showSnackBar(SnackBar(content: Text(message)));

  @override
  Widget build(BuildContext context) {
    final sortedSkills = [...skills]
      ..sort(
        (a, b) => ((b['confidence'] ?? 0) as num).compareTo(
          (a['confidence'] ?? 0) as num,
        ),
      );
    final quizSkills = sortedSkills.where((skill) {
      final evidence = skill['evidence'] as List<dynamic>? ?? [];
      return skill['skill_type'] == 'study_topic' ||
          evidence.any((item) => item['source_type'] == 'quiz');
    }).toList();
    final capabilitySkills = sortedSkills
        .where((skill) => !quizSkills.contains(skill))
        .toList();
    return ListView(
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Skill Zone',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Turn every project, certificate, quiz, and repository into visible proof of what you can do.',
                    style: TextStyle(color: Colors.black54),
                  ),
                ],
              ),
            ),
            IconButton(
              tooltip: 'Refresh skills',
              onPressed: _loadSkills,
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
        const SizedBox(height: 24),
        if (error != null)
          Text(
            error!,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        if (loading) const LinearProgressIndicator(),
        if (!loading) ...[
          _skillHero(sortedSkills),
          const SizedBox(height: 18),
          _evidenceTools(),
          const SizedBox(height: 18),
          _quizResults(quizSkills),
          const SizedBox(height: 18),
          _skillGrid(capabilitySkills),
        ],
      ],
    );
  }

  Widget _skillHero(List<dynamic> sortedSkills) => Card(
    color: const Color(0xff173e3a),
    child: Padding(
      padding: const EdgeInsets.all(24),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Your capability map',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 22,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  '${sortedSkills.length} tracked skills · evidence-backed confidence',
                  style: const TextStyle(color: Colors.white70),
                ),
                const SizedBox(height: 18),
                if (sortedSkills.isNotEmpty)
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final skill in sortedSkills.take(5))
                        Chip(
                          label: Text(
                            skill['skill_name']?.toString() ?? 'Skill',
                          ),
                        ),
                    ],
                  ),
              ],
            ),
          ),
          SizedBox(
            width: 120,
            height: 120,
            child: Stack(
              alignment: Alignment.center,
              children: [
                CircularProgressIndicator(
                  value: sortedSkills.isEmpty
                      ? 0
                      : ((sortedSkills
                                    .map(
                                      (item) =>
                                          (item['confidence'] ?? 0) as num,
                                    )
                                    .fold<num>(0, (a, b) => a + b) /
                                sortedSkills.length)
                            .toDouble()),
                  strokeWidth: 10,
                  backgroundColor: Colors.white24,
                  color: Brand.accent,
                ),
                Text(
                  sortedSkills.isEmpty
                      ? '0%'
                      : '${(((sortedSkills.map((item) => (item['confidence'] ?? 0) as num).fold<num>(0, (a, b) => a + b) / sortedSkills.length) * 100).round())}%',
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w800,
                    fontSize: 20,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    ),
  );

  Widget _evidenceTools() => LayoutBuilder(
    builder: (context, constraints) {
      final manual = Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Add evidence',
                style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: rawTerm,
                decoration: const InputDecoration(
                  labelText: 'Skill name',
                  hintText: 'e.g. Python',
                ),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: sourceRef,
                      decoration: const InputDecoration(
                        labelText: 'Evidence reference',
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  SizedBox(
                    width: 88,
                    child: TextField(
                      controller: confidence,
                      decoration: const InputDecoration(
                        labelText: 'Confidence',
                      ),
                      keyboardType: const TextInputType.numberWithOptions(
                        decimal: true,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: working ? null : _addEvidence,
                icon: const Icon(Icons.add_circle_outline),
                label: const Text('Add skill'),
              ),
            ],
          ),
        ),
      );
      final github = Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'GitHub signal',
                style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
              ),
              const SizedBox(height: 6),
              const Text(
                'Scan public repositories and language evidence.',
                style: TextStyle(color: Colors.black54),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: githubUsername,
                decoration: const InputDecoration(
                  labelText: 'GitHub username',
                  prefixIcon: Icon(Icons.code),
                ),
              ),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: working ? null : _syncGithub,
                icon: const Icon(Icons.sync),
                label: const Text('Sync GitHub'),
              ),
              if (githubResult != null)
                Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: Text(
                    '${githubResult!['repos_scanned'] ?? 0} repos scanned · ${githubResult!['skills_added'] ?? 0} skills added',
                    style: const TextStyle(
                      color: Brand.primary,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
            ],
          ),
        ),
      );
      return constraints.maxWidth < 800
          ? Column(children: [manual, const SizedBox(height: 16), github])
          : Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: manual),
                const SizedBox(width: 16),
                Expanded(child: github),
              ],
            );
    },
  );

  Widget _skillGrid(List<dynamic> sortedSkills) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Skill constellation',
            style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
          ),
          const SizedBox(height: 14),
          if (sortedSkills.isEmpty)
            const Text(
              'Add manual evidence or sync GitHub to start building your map.',
            ),
          for (final skill in sortedSkills) _skillTile(skill),
        ],
      ),
    ),
  );

  Widget _quizResults(List<dynamic> quizSkills) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Quiz results',
                style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
              ),
              Text(
                '${quizSkills.length} topics tracked',
                style: const TextStyle(color: Colors.black54),
              ),
            ],
          ),
          const SizedBox(height: 6),
          const Text(
            'Your quiz performance is separate from portfolio skills so you can see what needs practice.',
            style: TextStyle(color: Colors.black54),
          ),
          const SizedBox(height: 16),
          if (quizSkills.isEmpty)
            const Text(
              'Complete a study quiz to see topic accuracy here.',
              style: TextStyle(color: Colors.black54),
            ),
          for (final skill in quizSkills) _quizResultTile(skill),
        ],
      ),
    ),
  );

  Widget _quizResultTile(Map<String, dynamic> skill) {
    final evidence = (skill['evidence'] as List<dynamic>? ?? [])
        .where((item) => item['source_type'] == 'quiz')
        .toList();
    final rawAccuracy = evidence.isEmpty
        ? skill['confidence']
        : evidence.last['confidence'];
    final accuracy = ((rawAccuracy ?? 0) as num)
        .toDouble()
        .clamp(0.0, 1.0)
        .toDouble();
    final strong = accuracy >= 0.7;
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  skill['skill_name']?.toString() ?? 'Topic',
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              Text(
                '${(accuracy * 100).round()}% accuracy',
                style: TextStyle(
                  color: strong ? Brand.primary : Brand.accent,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 7),
          ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: LinearProgressIndicator(
              value: accuracy,
              minHeight: 9,
              backgroundColor: const Color(0xffe5ece8),
              color: strong ? Brand.primary : Brand.accent,
            ),
          ),
          const SizedBox(height: 5),
          Text(
            '${evidence.length} quiz signal${evidence.length == 1 ? '' : 's'}',
            style: const TextStyle(color: Colors.black54, fontSize: 12),
          ),
        ],
      ),
    );
  }

  Widget _skillTile(Map<String, dynamic> skill) {
    final confidence = ((skill['confidence'] ?? 0) as num)
        .toDouble()
        .clamp(0.0, 1.0)
        .toDouble();
    final evidence = skill['evidence'] as List<dynamic>? ?? [];
    final sources = evidence
        .map((item) => item['source_type']?.toString() ?? '')
        .where((source) => source.isNotEmpty)
        .toSet();
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  skill['skill_name']?.toString() ?? 'Skill',
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              Text(
                '${(confidence * 100).round()}%',
                style: const TextStyle(
                  color: Brand.primary,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 7),
          ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: LinearProgressIndicator(
              value: confidence,
              minHeight: 9,
              backgroundColor: const Color(0xffe5ece8),
              color: confidence >= .8 ? Brand.primary : Brand.accent,
            ),
          ),
          const SizedBox(height: 6),
          Wrap(
            spacing: 6,
            children: [
              for (final source in sources)
                Chip(
                  label: Text(source, style: const TextStyle(fontSize: 11)),
                  visualDensity: VisualDensity.compact,
                ),
            ],
          ),
        ],
      ),
    );
  }
}

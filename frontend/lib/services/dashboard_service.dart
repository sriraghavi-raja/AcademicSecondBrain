import '../models/dashboard_model.dart';
import 'api_service.dart';

class DashboardService {
  const DashboardService(this.api);

  final ApiService api;

  Future<DashboardModel> getDashboard(String studentId) async {
    // The current backend scopes this endpoint to the authenticated user.
    // Keep the student id in the public method for forward compatibility.
    final response = await api.careerDashboard();
    return DashboardModel.fromJson(response);
  }
}

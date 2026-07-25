// mobile/src/screens/HomeScreen.tsx
// 主页/仪表板界面

import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  SafeAreaView,
} from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTheme } from '../theme';
import { useAuthStore } from '../store/authStore';
import { useTaskStore } from '../store/taskStore';
import { LoadingAnimation, SyncStatusIndicator } from '../components';

interface HomeScreenProps {
  navigation: any;
}

export const HomeScreen: React.FC<HomeScreenProps> = ({ navigation }) => {
  const { theme } = useTheme();
  const { user } = useAuthStore();
  const { tasks, loading, fetchTasks } = useTaskStore();
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    fetchTasks(1);
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchTasks(1);
    setRefreshing(false);
  };

  const stats = {
    total: tasks.length,
    pending: tasks.filter((t) => t.status === 'pending').length,
    running: tasks.filter((t) => t.status === 'running').length,
    completed: tasks.filter((t) => t.status === 'completed').length,
    failed: tasks.filter((t) => t.status === 'failed').length,
  };

  const recentTasks = tasks.slice(0, 5);

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: theme.colors.background }]}
    >
      <ScrollView
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={[styles.greeting, { color: theme.colors.textSecondary }]}>
              Welcome back,
            </Text>
            <Text style={[styles.userName, { color: theme.colors.text }]}>
              {user?.name || 'User'}
            </Text>
          </View>
          <TouchableOpacity
            style={[
              styles.avatarContainer,
              { backgroundColor: theme.colors.primary + '20' },
            ]}
            onPress={() => navigation.navigate('Settings')}
          >
            <MaterialCommunityIcons
              name="account-circle"
              size={40}
              color={theme.colors.primary}
            />
          </TouchableOpacity>
        </View>

        {/* Sync Status */}
        <View style={styles.syncSection}>
          <SyncStatusIndicator status="synced" />
        </View>

        {/* Stats Cards */}
        <View style={styles.statsContainer}>
          <StatCard
            icon="list-status"
            label="Total Tasks"
            value={stats.total}
            color={theme.colors.primary}
            onPress={() => navigation.navigate('TaskList')}
          />
          <StatCard
            icon="clock-outline"
            label="Pending"
            value={stats.pending}
            color={theme.colors.warning}
            onPress={() => navigation.navigate('TaskList')}
          />
          <StatCard
            icon="play-circle-outline"
            label="Running"
            value={stats.running}
            color={theme.colors.info}
            onPress={() => navigation.navigate('TaskList')}
          />
          <StatCard
            icon="check-circle-outline"
            label="Completed"
            value={stats.completed}
            color={theme.colors.success}
            onPress={() => navigation.navigate('TaskList')}
          />
        </View>

        {/* Quick Actions */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: theme.colors.text }]}>
            Quick Actions
          </Text>
          <View style={styles.actionsGrid}>
            <ActionButton
              icon="plus-circle-outline"
              label="New Task"
              color={theme.colors.primary}
              onPress={() => navigation.navigate('CreateTask')}
            />
            <ActionButton
              icon="play-outline"
              label="Run Workflow"
              color={theme.colors.success}
              onPress={() => navigation.navigate('WorkflowMonitor')}
            />
            <ActionButton
              icon="chart-line"
              label="Analytics"
              color={theme.colors.info}
              onPress={() => navigation.navigate('Analytics')}
            />
            <ActionButton
              icon="cog-outline"
              label="Settings"
              color={theme.colors.warning}
              onPress={() => navigation.navigate('Settings')}
            />
          </View>
        </View>

        {/* Recent Tasks */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={[styles.sectionTitle, { color: theme.colors.text }]}>
              Recent Tasks
            </Text>
            <TouchableOpacity onPress={() => navigation.navigate('TaskList')}>
              <Text style={[styles.viewAll, { color: theme.colors.primary }]}>
                View All
              </Text>
            </TouchableOpacity>
          </View>

          {recentTasks.length > 0 ? (
            recentTasks.map((task) => (
              <TouchableOpacity
                key={task.id}
                style={[
                  styles.taskItem,
                  { backgroundColor: theme.colors.surface },
                ]}
                onPress={() => navigation.navigate('TaskDetail', { taskId: task.id })}
              >
                <View style={styles.taskItemContent}>
                  <Text
                    style={[styles.taskItemTitle, { color: theme.colors.text }]}
                    numberOfLines={1}
                  >
                    {task.title}
                  </Text>
                  <Text
                    style={[
                      styles.taskItemStatus,
                      { color: theme.colors.textSecondary },
                    ]}
                  >
                    {task.status}
                  </Text>
                </View>
                <MaterialCommunityIcons
                  name="chevron-right"
                  size={24}
                  color={theme.colors.textTertiary}
                />
              </TouchableOpacity>
            ))
          ) : (
            <View style={styles.emptyState}>
              <MaterialCommunityIcons
                name="inbox-outline"
                size={48}
                color={theme.colors.textTertiary}
              />
              <Text
                style={[styles.emptyStateText, { color: theme.colors.textSecondary }]}
              >
                No tasks yet
              </Text>
            </View>
          )}
        </View>

        {/* Footer Spacing */}
        <View style={{ height: 32 }} />
      </ScrollView>

      <LoadingAnimation visible={loading} message="Loading..." />
    </SafeAreaView>
  );
};

// Stat Card Component
type IconName = React.ComponentProps<typeof MaterialCommunityIcons>['name'];

interface StatCardProps {
  icon: IconName;
  label: string;
  value: number;
  color: string;
  onPress?: () => void;
}

const StatCard: React.FC<StatCardProps> = ({
  icon,
  label,
  value,
  color,
  onPress,
}) => {
  const { theme } = useTheme();

  return (
    <TouchableOpacity
      style={[
        styles.statCard,
        { backgroundColor: theme.colors.surface },
      ]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <View style={[styles.statIconContainer, { backgroundColor: color + '20' }]}>
        <MaterialCommunityIcons name={icon} size={24} color={color} />
      </View>
      <Text style={[styles.statValue, { color: theme.colors.text }]}>
        {value}
      </Text>
      <Text style={[styles.statLabel, { color: theme.colors.textSecondary }]}>
        {label}
      </Text>
    </TouchableOpacity>
  );
};

// Action Button Component
interface ActionButtonProps {
  icon: IconName;
  label: string;
  color: string;
  onPress?: () => void;
}

const ActionButton: React.FC<ActionButtonProps> = ({
  icon,
  label,
  color,
  onPress,
}) => {
  const { theme } = useTheme();

  return (
    <TouchableOpacity
      style={[
        styles.actionButton,
        { backgroundColor: theme.colors.surface },
      ]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <View style={[styles.actionIconContainer, { backgroundColor: color + '20' }]}>
        <MaterialCommunityIcons name={icon} size={28} color={color} />
      </View>
      <Text style={[styles.actionLabel, { color: theme.colors.text }]}>
        {label}
      </Text>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 16,
  },
  greeting: {
    fontSize: 14,
    fontWeight: '400',
    marginBottom: 4,
  },
  userName: {
    fontSize: 24,
    fontWeight: '700',
  },
  avatarContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  syncSection: {
    paddingHorizontal: 16,
    marginBottom: 16,
  },
  statsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: 8,
    marginBottom: 24,
  },
  statCard: {
    width: '48%',
    marginHorizontal: 8,
    marginVertical: 8,
    paddingVertical: 16,
    paddingHorizontal: 12,
    borderRadius: 12,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  statIconContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  statValue: {
    fontSize: 20,
    fontWeight: '700',
    marginBottom: 4,
  },
  statLabel: {
    fontSize: 12,
    fontWeight: '500',
  },
  section: {
    paddingHorizontal: 16,
    marginBottom: 24,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
  },
  viewAll: {
    fontSize: 14,
    fontWeight: '600',
  },
  actionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: -8,
  },
  actionButton: {
    width: '48%',
    marginHorizontal: 8,
    marginVertical: 8,
    paddingVertical: 16,
    paddingHorizontal: 12,
    borderRadius: 12,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  actionIconContainer: {
    width: 56,
    height: 56,
    borderRadius: 28,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  actionLabel: {
    fontSize: 12,
    fontWeight: '600',
    textAlign: 'center',
  },
  taskItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 12,
    marginVertical: 6,
    borderRadius: 8,
  },
  taskItemContent: {
    flex: 1,
  },
  taskItemTitle: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 4,
  },
  taskItemStatus: {
    fontSize: 12,
    fontWeight: '400',
    textTransform: 'capitalize',
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 32,
  },
  emptyStateText: {
    fontSize: 14,
    fontWeight: '500',
    marginTop: 8,
  },
});

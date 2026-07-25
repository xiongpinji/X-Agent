// mobile/src/components/TaskCard.tsx
// 任务卡片组件

import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ViewStyle,
} from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTheme } from '../theme';
import { Task } from '../types';
import { formatDate, getPriorityColor, getStatusColor } from '../utils/formatters';

type IconName = React.ComponentProps<typeof MaterialCommunityIcons>['name'];

interface TaskCardProps {
  task: Task;
  onPress?: () => void;
  onDelete?: () => void;
  style?: ViewStyle;
}

export const TaskCard: React.FC<TaskCardProps> = ({
  task,
  onPress,
  onDelete,
  style,
}) => {
  const { theme } = useTheme();

  const statusColor = getStatusColor(task.status, theme.colors);
  const priorityColor = getPriorityColor(task.priority, theme.colors);

  const getStatusIcon = (): IconName => {
    switch (task.status) {
      case 'pending':
        return 'clock-outline';
      case 'running':
        return 'play-circle-outline';
      case 'completed':
        return 'check-circle-outline';
      case 'failed':
        return 'alert-circle-outline';
      default:
        return 'help-circle-outline';
    }
  };

  const getPriorityIcon = (): IconName => {
    switch (task.priority) {
      case 'high':
        return 'alert';
      case 'medium':
        return 'minus';
      case 'low':
        return 'chevron-down';
      default:
        return 'help';
    }
  };

  return (
    <TouchableOpacity
      style={[
        styles.container,
        { backgroundColor: theme.colors.surface },
        style,
      ]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <View style={styles.header}>
        <View style={styles.titleSection}>
          <MaterialCommunityIcons
            name={getStatusIcon()}
            size={20}
            color={statusColor}
            style={styles.statusIcon}
          />
          <Text
            style={[styles.title, { color: theme.colors.text }]}
            numberOfLines={1}
          >
            {task.title}
          </Text>
        </View>
        <View
          style={[
            styles.statusBadge,
            { backgroundColor: statusColor + '20' },
          ]}
        >
          <Text style={[styles.statusText, { color: statusColor }]}>
            {task.status}
          </Text>
        </View>
      </View>

      <Text
        style={[styles.description, { color: theme.colors.textSecondary }]}
        numberOfLines={2}
      >
        {task.description}
      </Text>

      <View style={styles.footer}>
        <View style={styles.prioritySection}>
          <MaterialCommunityIcons
            name={getPriorityIcon()}
            size={16}
            color={priorityColor}
          />
          <Text style={[styles.priority, { color: priorityColor }]}>
            {task.priority}
          </Text>
        </View>

        <View style={styles.dateSection}>
          <MaterialCommunityIcons
            name="calendar-outline"
            size={14}
            color={theme.colors.textTertiary}
          />
          <Text style={[styles.date, { color: theme.colors.textTertiary }]}>
            {formatDate(task.updatedAt)}
          </Text>
        </View>

        {onDelete && (
          <TouchableOpacity
            style={styles.deleteButton}
            onPress={onDelete}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          >
            <MaterialCommunityIcons
              name="delete-outline"
              size={18}
              color={theme.colors.error}
            />
          </TouchableOpacity>
        )}
      </View>

      {task.syncStatus === 'pending' && (
        <View style={styles.syncIndicator}>
          <MaterialCommunityIcons
            name="cloud-upload-outline"
            size={12}
            color={theme.colors.warning}
          />
          <Text style={[styles.syncText, { color: theme.colors.warning }]}>
            Syncing...
          </Text>
        </View>
      )}
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  container: {
    borderRadius: 12,
    padding: 16,
    marginHorizontal: 16,
    marginVertical: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  titleSection: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
  },
  statusIcon: {
    marginRight: 8,
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
    flex: 1,
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
    marginLeft: 8,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  description: {
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 12,
  },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  prioritySection: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  priority: {
    fontSize: 12,
    fontWeight: '600',
    marginLeft: 4,
    textTransform: 'capitalize',
  },
  dateSection: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    marginLeft: 16,
  },
  date: {
    fontSize: 12,
    marginLeft: 4,
  },
  deleteButton: {
    padding: 4,
  },
  syncIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: 'rgba(0, 0, 0, 0.05)',
  },
  syncText: {
    fontSize: 11,
    marginLeft: 4,
    fontWeight: '500',
  },
});

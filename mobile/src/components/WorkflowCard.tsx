// mobile/src/components/WorkflowCard.tsx
// 工作流卡片组件

import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ViewStyle,
  ProgressBarAndroid,
  ProgressViewIOS,
  Platform,
} from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTheme } from '../theme';
import { WorkflowRun } from '../types';
import { formatDate, getStatusColor } from '../utils/formatters';

interface WorkflowCardProps {
  workflow: WorkflowRun;
  onPress?: () => void;
  onRetry?: () => void;
  style?: ViewStyle;
}

export const WorkflowCard: React.FC<WorkflowCardProps> = ({
  workflow,
  onPress,
  onRetry,
  style,
}) => {
  const { theme } = useTheme();

  const statusColor = getStatusColor(workflow.status, theme);
  const progress = workflow.progress / 100;

  const getStatusIcon = () => {
    switch (workflow.status) {
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

  const completedNodes = workflow.nodes.filter(
    (n) => n.status === 'completed'
  ).length;
  const totalNodes = workflow.nodes.length;

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
            size={24}
            color={statusColor}
            style={styles.statusIcon}
          />
          <View style={styles.titleContent}>
            <Text
              style={[styles.title, { color: theme.colors.text }]}
              numberOfLines={1}
            >
              Workflow {workflow.workflowId}
            </Text>
            <Text
              style={[styles.subtitle, { color: theme.colors.textSecondary }]}
            >
              Run ID: {workflow.id.substring(0, 8)}...
            </Text>
          </View>
        </View>
        <View
          style={[
            styles.statusBadge,
            { backgroundColor: statusColor + '20' },
          ]}
        >
          <Text style={[styles.statusText, { color: statusColor }]}>
            {workflow.status}
          </Text>
        </View>
      </View>

      <View style={styles.progressSection}>
        <View style={styles.progressHeader}>
          <Text style={[styles.progressLabel, { color: theme.colors.text }]}>
            Progress
          </Text>
          <Text
            style={[styles.progressValue, { color: theme.colors.textSecondary }]}
          >
            {workflow.progress}%
          </Text>
        </View>
        {Platform.OS === 'ios' ? (
          <ProgressViewIOS
            value={progress}
            progressTintColor={statusColor}
            style={styles.progressBar}
          />
        ) : (
          <ProgressBarAndroid
            styleAttr="Horizontal"
            indeterminate={false}
            progress={progress}
            color={statusColor}
            style={styles.progressBar}
          />
        )}
      </View>

      <View style={styles.nodesSection}>
        <Text style={[styles.nodesLabel, { color: theme.colors.textSecondary }]}>
          Nodes: {completedNodes}/{totalNodes}
        </Text>
        <View style={styles.nodesList}>
          {workflow.nodes.slice(0, 3).map((node) => (
            <View
              key={node.id}
              style={[
                styles.nodeIndicator,
                {
                  backgroundColor:
                    node.status === 'completed'
                      ? theme.colors.success
                      : node.status === 'failed'
                      ? theme.colors.error
                      : node.status === 'running'
                      ? theme.colors.warning
                      : theme.colors.border,
                },
              ]}
            />
          ))}
          {totalNodes > 3 && (
            <Text
              style={[
                styles.moreNodes,
                { color: theme.colors.textTertiary },
              ]}
            >
              +{totalNodes - 3}
            </Text>
          )}
        </View>
      </View>

      <View style={styles.footer}>
        <View style={styles.timeSection}>
          <MaterialCommunityIcons
            name="clock-outline"
            size={14}
            color={theme.colors.textTertiary}
          />
          <Text style={[styles.time, { color: theme.colors.textTertiary }]}>
            {formatDate(workflow.startedAt)}
          </Text>
        </View>

        {workflow.duration && (
          <Text style={[styles.duration, { color: theme.colors.textTertiary }]}>
            {Math.round(workflow.duration / 1000)}s
          </Text>
        )}

        {workflow.status === 'failed' && onRetry && (
          <TouchableOpacity
            style={[styles.retryButton, { borderColor: theme.colors.primary }]}
            onPress={onRetry}
          >
            <MaterialCommunityIcons
              name="refresh"
              size={16}
              color={theme.colors.primary}
            />
            <Text style={[styles.retryText, { color: theme.colors.primary }]}>
              Retry
            </Text>
          </TouchableOpacity>
        )}
      </View>

      {workflow.error && (
        <View
          style={[
            styles.errorSection,
            { backgroundColor: theme.colors.error + '10' },
          ]}
        >
          <MaterialCommunityIcons
            name="alert-circle-outline"
            size={14}
            color={theme.colors.error}
          />
          <Text
            style={[styles.errorText, { color: theme.colors.error }]}
            numberOfLines={1}
          >
            {workflow.error}
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
    marginBottom: 16,
  },
  titleSection: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
  },
  statusIcon: {
    marginRight: 12,
  },
  titleContent: {
    flex: 1,
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 12,
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
  progressSection: {
    marginBottom: 16,
  },
  progressHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  progressLabel: {
    fontSize: 12,
    fontWeight: '600',
  },
  progressValue: {
    fontSize: 12,
    fontWeight: '600',
  },
  progressBar: {
    height: 6,
    borderRadius: 3,
  },
  nodesSection: {
    marginBottom: 12,
  },
  nodesLabel: {
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 8,
  },
  nodesList: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  nodeIndicator: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  moreNodes: {
    fontSize: 11,
    fontWeight: '600',
    marginLeft: 4,
  },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: 'rgba(0, 0, 0, 0.05)',
  },
  timeSection: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  time: {
    fontSize: 12,
    marginLeft: 4,
  },
  duration: {
    fontSize: 12,
    fontWeight: '600',
    marginHorizontal: 12,
  },
  retryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 6,
    borderWidth: 1,
  },
  retryText: {
    fontSize: 12,
    fontWeight: '600',
    marginLeft: 4,
  },
  errorSection: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 12,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 8,
  },
  errorText: {
    fontSize: 12,
    marginLeft: 8,
    flex: 1,
  },
});

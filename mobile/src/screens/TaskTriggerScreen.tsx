// mobile/src/screens/TaskTriggerScreen.tsx
// P2-08: 任务触发 + 进度监控最小 UI 闭环
// 流程: 填写目标/描述 -> 提交 POST /api/v1/mobile/trigger
//      -> 自动轮询 GET /api/v1/mobile/runs/{run_id}/status (3s) -> 终态停止

import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { useRunStore } from '../store/runStore';
import { TriggerPriority, isTerminalStatus } from '../services/mobileRunService';

const PRIORITIES: TriggerPriority[] = ['low', 'normal', 'high', 'urgent'];

const STATUS_COLORS: Record<string, string> = {
  pending: '#8a6d1f',
  running: '#1f5fa8',
  completed: '#2e7d46',
  failed: '#b3362b',
  cancelled: '#6b6b6b',
};

export const TaskTriggerScreen: React.FC = () => {
  const {
    currentRun,
    submitting,
    polling,
    error,
    triggerTask,
    cancelCurrentRun,
    stopPolling,
    reset,
    clearError,
  } = useRunStore();

  const [goal, setGoal] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState<TriggerPriority>('normal');

  useEffect(() => () => stopPolling(), [stopPolling]);

  const canSubmit = goal.trim().length > 0 && !submitting;

  const handleSubmit = async () => {
    clearError();
    const task = description.trim()
      ? `${goal.trim()}\n\n${description.trim()}`
      : goal.trim();
    await triggerTask(task, priority);
  };

  const progress = currentRun ? currentRun.progress_percent / 100 : 0;
  const isTerminal = currentRun
    ? isTerminalStatus(currentRun.status)
    : false;

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <Text style={styles.sectionTitle}>触发新任务</Text>

        <Text style={styles.label}>目标 *</Text>
        <TextInput
          testID="goal-input"
          style={styles.input}
          placeholder="例如: 调研竞品定价并生成对比报告"
          value={goal}
          onChangeText={setGoal}
          maxLength={500}
        />

        <Text style={styles.label}>描述</Text>
        <TextInput
          testID="description-input"
          style={[styles.input, styles.multiline]}
          placeholder="补充背景、约束、期望产出 (可选)"
          value={description}
          onChangeText={setDescription}
          multiline
          numberOfLines={4}
          maxLength={3500}
        />

        <Text style={styles.label}>优先级</Text>
        <View style={styles.priorityRow}>
          {PRIORITIES.map((p) => (
            <TouchableOpacity
              key={p}
              testID={`priority-${p}`}
              style={[
                styles.priorityChip,
                priority === p && styles.priorityChipActive,
              ]}
              onPress={() => setPriority(p)}
            >
              <Text
                style={[
                  styles.priorityText,
                  priority === p && styles.priorityTextActive,
                ]}
              >
                {p}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <TouchableOpacity
          testID="submit-button"
          style={[styles.submitButton, !canSubmit && styles.submitDisabled]}
          onPress={handleSubmit}
          disabled={!canSubmit}
        >
          {submitting ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.submitText}>提交任务</Text>
          )}
        </TouchableOpacity>

        {error ? (
          <Text testID="error-text" style={styles.errorText}>
            {error}
          </Text>
        ) : null}

        {currentRun ? (
          <View testID="run-status-card" style={styles.statusCard}>
            <View style={styles.statusHeader}>
              <Text style={styles.sectionTitle}>任务状态</Text>
              <View
                style={[
                  styles.statusBadge,
                  { backgroundColor: STATUS_COLORS[currentRun.status] ?? '#666' },
                ]}
              >
                <Text style={styles.statusBadgeText}>{currentRun.status}</Text>
              </View>
            </View>

            <Text style={styles.runMeta} numberOfLines={1}>
              run_id: {currentRun.run_id}
            </Text>

            <View style={styles.progressTrack}>
              <View
                testID="progress-fill"
                style={[styles.progressFill, { flex: progress }]}
              />
              <View style={{ flex: 1 - progress }} />
            </View>
            <Text style={styles.progressText}>
              {currentRun.progress_percent.toFixed(0)}%
              {polling && !isTerminal ? ' · 轮询中' : ''}
            </Text>

            {currentRun.current_step ? (
              <Text style={styles.stepText}>
                当前步骤: {currentRun.current_step}
              </Text>
            ) : null}
            {currentRun.result_summary ? (
              <Text style={styles.stepText}>
                结果: {currentRun.result_summary}
              </Text>
            ) : null}
            {currentRun.error ? (
              <Text style={styles.errorText}>{currentRun.error}</Text>
            ) : null}

            <View style={styles.statusActions}>
              {!isTerminal ? (
                <TouchableOpacity
                  testID="cancel-button"
                  style={styles.cancelButton}
                  onPress={cancelCurrentRun}
                >
                  <Text style={styles.cancelText}>取消任务</Text>
                </TouchableOpacity>
              ) : (
                <TouchableOpacity
                  testID="reset-button"
                  style={styles.resetButton}
                  onPress={reset}
                >
                  <Text style={styles.resetText}>新建任务</Text>
                </TouchableOpacity>
              )}
            </View>
          </View>
        ) : null}
      </ScrollView>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  flex: { flex: 1 },
  container: { flex: 1, backgroundColor: '#f7f5f2' },
  content: { padding: 16, paddingBottom: 40 },
  sectionTitle: { fontSize: 18, fontWeight: '600', color: '#2b2b2b' },
  label: { fontSize: 13, color: '#6b6b6b', marginTop: 16, marginBottom: 6 },
  input: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#ddd6cc',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 15,
    color: '#2b2b2b',
  },
  multiline: { minHeight: 96, textAlignVertical: 'top' },
  priorityRow: { flexDirection: 'row', gap: 8 },
  priorityChip: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#ddd6cc',
    backgroundColor: '#fff',
  },
  priorityChipActive: { backgroundColor: '#3d5a45', borderColor: '#3d5a45' },
  priorityText: { fontSize: 13, color: '#6b6b6b' },
  priorityTextActive: { color: '#fff', fontWeight: '600' },
  submitButton: {
    marginTop: 24,
    backgroundColor: '#3d5a45',
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
  },
  submitDisabled: { opacity: 0.5 },
  submitText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  errorText: { color: '#b3362b', marginTop: 12, fontSize: 13 },
  statusCard: {
    marginTop: 28,
    backgroundColor: '#fff',
    borderRadius: 10,
    padding: 16,
    borderWidth: 1,
    borderColor: '#e5dfd6',
  },
  statusHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  statusBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  statusBadgeText: { color: '#fff', fontSize: 12, fontWeight: '600' },
  runMeta: { fontSize: 11, color: '#999', marginTop: 8 },
  progressTrack: {
    flexDirection: 'row',
    height: 8,
    borderRadius: 4,
    backgroundColor: '#ede8e0',
    marginTop: 12,
    overflow: 'hidden',
  },
  progressFill: { backgroundColor: '#3d5a45', borderRadius: 4 },
  progressText: { fontSize: 12, color: '#6b6b6b', marginTop: 6 },
  stepText: { fontSize: 13, color: '#444', marginTop: 8 },
  statusActions: { marginTop: 16, flexDirection: 'row' },
  cancelButton: {
    borderWidth: 1,
    borderColor: '#b3362b',
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  cancelText: { color: '#b3362b', fontWeight: '600' },
  resetButton: {
    backgroundColor: '#3d5a45',
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  resetText: { color: '#fff', fontWeight: '600' },
});

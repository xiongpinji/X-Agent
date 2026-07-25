// mobile/src/screens/WorkflowMonitorScreen.tsx
// 工作流监控界面

import React, { useEffect, useState } from 'react';
import {
  View,
  ScrollView,
  StyleSheet,
  Text,
  ActivityIndicator,
} from 'react-native';
import { WorkflowRun, WorkflowNode } from '../types';
import { ProgressBar } from '../components/ProgressBar';

interface WorkflowMonitorScreenProps {
  navigation: any;
  route: any;
}

export const WorkflowMonitorScreen: React.FC<WorkflowMonitorScreenProps> = ({
  navigation,
  route,
}) => {
  const { workflowId } = route.params ?? {};
  const [workflow, setWorkflow] = useState<WorkflowRun | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchWorkflow();
    const interval = setInterval(fetchWorkflow, 2000); // 每2秒刷新一次
    return () => clearInterval(interval);
  }, [workflowId]);

  const fetchWorkflow = async () => {
    try {
      const response = await fetch(
        `https://api.xagent.local/workflows/${workflowId}`
      );
      const data = await response.json();
      setWorkflow(data);
      setLoading(false);
    } catch (error) {
      console.error('Fetch workflow error:', error);
      setLoading(false);
    }
  };

  const renderProgressBar = () => {
    if (!workflow) return null;

    const progress = workflow.progress / 100;

    return (
      <View style={styles.progressContainer}>
        <Text style={styles.progressLabel}>Progress: {workflow.progress}%</Text>
        <ProgressBar progress={progress} style={styles.progressBar} />
      </View>
    );
  };

  const renderNodeItem = (node: WorkflowNode) => (
    <View key={node.id} style={styles.nodeItem}>
      <View style={styles.nodeHeader}>
        <Text style={styles.nodeName}>{node.name}</Text>
        <View style={[styles.nodeStatus, (styles as any)[`nodeStatus_${node.status}`]]}>
          <Text style={styles.nodeStatusText}>{node.status}</Text>
        </View>
      </View>
      {node.duration && (
        <Text style={styles.nodeDuration}>Duration: {node.duration}ms</Text>
      )}
      {node.error && (
        <Text style={styles.nodeError}>Error: {node.error}</Text>
      )}
    </View>
  );

  if (loading) {
    return (
      <View style={styles.container}>
        <ActivityIndicator size="large" color="#0000ff" />
      </View>
    );
  }

  if (!workflow) {
    return (
      <View style={styles.container}>
        <Text style={styles.errorText}>Workflow not found</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Workflow Monitor</Text>
        <View style={[styles.statusBadge, (styles as any)[`status_${workflow.status}`]]}>
          <Text style={styles.statusText}>{workflow.status}</Text>
        </View>
      </View>

      {renderProgressBar()}

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Nodes</Text>
        {workflow.nodes.map((node) => renderNodeItem(node))}
      </View>

      {workflow.result && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Result</Text>
          <Text style={styles.resultText}>
            {JSON.stringify(workflow.result, null, 2)}
          </Text>
        </View>
      )}

      {workflow.error && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Error</Text>
          <Text style={styles.errorText}>{workflow.error}</Text>
        </View>
      )}
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
    padding: 15,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
  },
  statusBadge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
  },
  status_pending: {
    backgroundColor: '#fff3cd',
  },
  status_running: {
    backgroundColor: '#cfe2ff',
  },
  status_completed: {
    backgroundColor: '#d1e7dd',
  },
  status_failed: {
    backgroundColor: '#f8d7da',
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
  },
  progressContainer: {
    marginBottom: 20,
  },
  progressLabel: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 8,
  },
  progressBar: {
    height: 8,
    borderRadius: 4,
  },
  section: {
    backgroundColor: '#fff',
    borderRadius: 8,
    padding: 15,
    marginBottom: 15,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 12,
  },
  nodeItem: {
    backgroundColor: '#f9f9f9',
    borderRadius: 6,
    padding: 12,
    marginBottom: 10,
    borderLeftWidth: 4,
    borderLeftColor: '#007AFF',
  },
  nodeHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  nodeName: {
    fontSize: 14,
    fontWeight: '600',
    flex: 1,
  },
  nodeStatus: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  nodeStatus_pending: {
    backgroundColor: '#fff3cd',
  },
  nodeStatus_running: {
    backgroundColor: '#cfe2ff',
  },
  nodeStatus_completed: {
    backgroundColor: '#d1e7dd',
  },
  nodeStatus_failed: {
    backgroundColor: '#f8d7da',
  },
  nodeStatusText: {
    fontSize: 11,
    fontWeight: '600',
  },
  nodeDuration: {
    fontSize: 12,
    color: '#666',
  },
  nodeError: {
    fontSize: 12,
    color: '#d32f2f',
    marginTop: 4,
  },
  resultText: {
    fontSize: 12,
    color: '#333',
    fontFamily: 'monospace',
  },
  errorText: {
    fontSize: 14,
    color: '#d32f2f',
  },
});

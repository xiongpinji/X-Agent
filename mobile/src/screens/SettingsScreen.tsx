// mobile/src/screens/SettingsScreen.tsx
// 设置界面

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Switch,
  SafeAreaView,
  Alert,
  TextInput,
  ActivityIndicator,
} from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTheme, ThemeMode } from '../theme';
import { useAuthStore } from '../store/authStore';
import {
  getApiConfig,
  saveApiConfig,
  DEFAULT_API_BASE_URL,
} from '../config/env';

interface SettingsScreenProps {
  navigation: any;
}

export const SettingsScreen: React.FC<SettingsScreenProps> = ({ navigation }) => {
  const { theme, setThemeMode, toggleTheme } = useTheme();
  const { user, logout } = useAuthStore();

  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const [biometricEnabled, setBiometricEnabled] = useState(false);
  const [autoSync, setAutoSync] = useState(true);
  const [wifiOnly, setWifiOnly] = useState(false);

  const handleLogout = () => {
    Alert.alert('Logout', 'Are you sure you want to logout?', [
      { text: 'Cancel', onPress: () => {} },
      {
        text: 'Logout',
        onPress: async () => {
          await logout();
          navigation.replace('Login');
        },
        style: 'destructive',
      },
    ]);
  };

  const handleThemeChange = (mode: ThemeMode) => {
    setThemeMode(mode);
  };

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: theme.colors.background }]}
    >
      <ScrollView showsVerticalScrollIndicator={false}>
        {/* Header */}
        <View style={styles.header}>
          <Text style={[styles.title, { color: theme.colors.text }]}>
            Settings
          </Text>
        </View>

        {/* Server Connection Section (base URL + API key + 连接测试) */}
        <ConnectionSection theme={theme} />

        {/* Account Section */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: theme.colors.text }]}>
            Account
          </Text>
          <SettingItem
            icon="account-circle-outline"
            label="Profile"
            value={user?.email}
            onPress={() => navigation.navigate('EditProfile')}
            theme={theme}
          />
          <SettingItem
            icon="lock-outline"
            label="Change Password"
            onPress={() => navigation.navigate('ChangePassword')}
            theme={theme}
          />
          <SettingItem
            icon="shield-account-outline"
            label="Security"
            onPress={() => navigation.navigate('Security')}
            theme={theme}
          />
        </View>

        {/* Appearance Section */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: theme.colors.text }]}>
            Appearance
          </Text>
          <View
            style={[
              styles.settingItem,
              { backgroundColor: theme.colors.surface },
            ]}
          >
            <View style={styles.settingContent}>
              <MaterialCommunityIcons
                name="palette-outline"
                size={24}
                color={theme.colors.primary}
                style={styles.icon}
              />
              <View style={styles.settingText}>
                <Text style={[styles.label, { color: theme.colors.text }]}>
                  Theme
                </Text>
                <Text style={[styles.value, { color: theme.colors.textSecondary }]}>
                  {theme.mode === 'auto'
                    ? 'Auto'
                    : theme.mode === 'light'
                    ? 'Light'
                    : 'Dark'}
                </Text>
              </View>
            </View>
            <TouchableOpacity
              onPress={() => toggleTheme()}
              style={styles.actionButton}
            >
              <MaterialCommunityIcons
                name={theme.isDark ? 'white-balance-sunny' : 'moon-waning-crescent'}
                size={20}
                color={theme.colors.primary}
              />
            </TouchableOpacity>
          </View>
        </View>

        {/* Notifications Section */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: theme.colors.text }]}>
            Notifications
          </Text>
          <ToggleItem
            icon="bell-outline"
            label="Enable Notifications"
            value={notificationsEnabled}
            onValueChange={setNotificationsEnabled}
            theme={theme}
          />
          <ToggleItem
            icon="message-outline"
            label="Task Updates"
            value={notificationsEnabled}
            onValueChange={setNotificationsEnabled}
            theme={theme}
            disabled={!notificationsEnabled}
          />
          <ToggleItem
            icon="play-circle-outline"
            label="Workflow Progress"
            value={notificationsEnabled}
            onValueChange={setNotificationsEnabled}
            theme={theme}
            disabled={!notificationsEnabled}
          />
        </View>

        {/* Sync Section */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: theme.colors.text }]}>
            Sync & Storage
          </Text>
          <ToggleItem
            icon="sync"
            label="Auto Sync"
            value={autoSync}
            onValueChange={setAutoSync}
            theme={theme}
          />
          <ToggleItem
            icon="wifi"
            label="WiFi Only"
            value={wifiOnly}
            onValueChange={setWifiOnly}
            theme={theme}
          />
          <SettingItem
            icon="database-outline"
            label="Clear Cache"
            onPress={() => {
              Alert.alert('Clear Cache', 'This will clear all cached data.', [
                { text: 'Cancel' },
                { text: 'Clear', onPress: () => {}, style: 'destructive' },
              ]);
            }}
            theme={theme}
          />
        </View>

        {/* Security Section */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: theme.colors.text }]}>
            Security
          </Text>
          <ToggleItem
            icon="fingerprint"
            label="Biometric Authentication"
            value={biometricEnabled}
            onValueChange={setBiometricEnabled}
            theme={theme}
          />
        </View>

        {/* About Section */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: theme.colors.text }]}>
            About
          </Text>
          <SettingItem
            icon="information-outline"
            label="About X-Agent"
            value="v1.0.0"
            onPress={() => navigation.navigate('About')}
            theme={theme}
          />
          <SettingItem
            icon="file-document-outline"
            label="Privacy Policy"
            onPress={() => navigation.navigate('PrivacyPolicy')}
            theme={theme}
          />
          <SettingItem
            icon="file-document-outline"
            label="Terms of Service"
            onPress={() => navigation.navigate('TermsOfService')}
            theme={theme}
          />
        </View>

        {/* Logout Button */}
        <View style={styles.section}>
          <TouchableOpacity
            style={[
              styles.logoutButton,
              { backgroundColor: theme.colors.error + '20' },
            ]}
            onPress={handleLogout}
          >
            <MaterialCommunityIcons
              name="logout"
              size={20}
              color={theme.colors.error}
              style={styles.logoutIcon}
            />
            <Text style={[styles.logoutText, { color: theme.colors.error }]}>
              Logout
            </Text>
          </TouchableOpacity>
        </View>

        {/* Footer Spacing */}
        <View style={{ height: 32 }} />
      </ScrollView>
    </SafeAreaView>
  );
};

// Server Connection Section: 配置后端地址与 x-api-key 并测试连通性
interface ConnectionSectionProps {
  theme: any;
}

const ConnectionSection: React.FC<ConnectionSectionProps> = ({ theme }) => {
  const [baseUrl, setBaseUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [status, setStatus] = useState<{ ok: boolean; message: string } | null>(
    null
  );

  useEffect(() => {
    let mounted = true;
    getApiConfig()
      .then((cfg) => {
        if (!mounted) return;
        setBaseUrl(cfg.baseUrl);
        setApiKey(cfg.apiKey ?? '');
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
    return () => {
      mounted = false;
    };
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    try {
      // 保存到 SecureStore（base URL 为运行时覆盖，优先级高于 app.json/环境变量）
      await saveApiConfig({ baseUrl, apiKey });
      setStatus({ ok: true, message: 'Connection settings saved.' });
    } catch (error) {
      setStatus({ ok: false, message: `Save failed: ${String(error)}` });
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setStatus(null);
    try {
      // 后端契约: GET /health 公开端点（backend/app/main.py），返回 {status:"ok", service:"x-agent"}
      const target = (baseUrl.trim() || DEFAULT_API_BASE_URL).replace(/\/+$/, '');
      const response = await fetch(`${target}/health`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const body = await response.json().catch(() => ({}));
      if (body.status === 'ok') {
        setStatus({
          ok: true,
          message: `Connected (service: ${body.service ?? 'unknown'})`,
        });
      } else {
        setStatus({
          ok: false,
          message: `Reachable but unhealthy: ${JSON.stringify(body).slice(0, 120)}`,
        });
      }
    } catch (error: any) {
      setStatus({
        ok: false,
        message: `Connection failed: ${error?.message ?? String(error)}`,
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: theme.colors.text }]}>
        Server Connection
      </Text>
      <View
        style={[
          styles.card,
          { backgroundColor: theme.colors.surface, borderColor: theme.colors.border },
        ]}
      >
        <Text style={[styles.label, { color: theme.colors.text }]}>
          Base URL
        </Text>
        <TextInput
          style={[
            styles.textInput,
            {
              color: theme.colors.text,
              borderColor: theme.colors.border,
              backgroundColor: theme.colors.background,
            },
          ]}
          value={baseUrl}
          onChangeText={setBaseUrl}
          placeholder={`e.g. ${DEFAULT_API_BASE_URL}`}
          placeholderTextColor={theme.colors.textTertiary}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
          editable={loaded}
        />
        <Text style={[styles.label, { color: theme.colors.text, marginTop: 12 }]}>
          API Key (x-api-key)
        </Text>
        <TextInput
          style={[
            styles.textInput,
            {
              color: theme.colors.text,
              borderColor: theme.colors.border,
              backgroundColor: theme.colors.background,
            },
          ]}
          value={apiKey}
          onChangeText={setApiKey}
          placeholder="Paste your API key"
          placeholderTextColor={theme.colors.textTertiary}
          autoCapitalize="none"
          autoCorrect={false}
          secureTextEntry
          editable={loaded}
        />
        <View style={styles.connectionButtons}>
          <TouchableOpacity
            style={[
              styles.secondaryButton,
              { borderColor: theme.colors.primary },
            ]}
            onPress={handleTestConnection}
            disabled={testing || !loaded}
          >
            {testing ? (
              <ActivityIndicator size="small" color={theme.colors.primary} />
            ) : (
              <Text
                style={[styles.secondaryButtonText, { color: theme.colors.primary }]}
              >
                Test Connection
              </Text>
            )}
          </TouchableOpacity>
          <TouchableOpacity
            style={[
              styles.primaryButton,
              { backgroundColor: theme.colors.primary },
            ]}
            onPress={handleSave}
            disabled={saving || !loaded}
          >
            {saving ? (
              <ActivityIndicator size="small" color={theme.colors.textInverse} />
            ) : (
              <Text
                style={[
                  styles.primaryButtonText,
                  { color: theme.colors.textInverse },
                ]}
              >
                Save
              </Text>
            )}
          </TouchableOpacity>
        </View>
        {status && (
          <Text
            style={[
              styles.connectionStatus,
              { color: status.ok ? '#2e7d32' : theme.colors.error },
            ]}
          >
            {status.message}
          </Text>
        )}
      </View>
    </View>
  );
};

// Setting Item Component
type IconName = React.ComponentProps<typeof MaterialCommunityIcons>['name'];

interface SettingItemProps {
  icon: IconName;
  label: string;
  value?: string;
  onPress?: () => void;
  theme: any;
}

const SettingItem: React.FC<SettingItemProps> = ({
  icon,
  label,
  value,
  onPress,
  theme,
}) => {
  return (
    <TouchableOpacity
      style={[
        styles.settingItem,
        { backgroundColor: theme.colors.surface },
      ]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <View style={styles.settingContent}>
        <MaterialCommunityIcons
          name={icon}
          size={24}
          color={theme.colors.primary}
          style={styles.icon}
        />
        <View style={styles.settingText}>
          <Text style={[styles.label, { color: theme.colors.text }]}>
            {label}
          </Text>
          {value && (
            <Text style={[styles.value, { color: theme.colors.textSecondary }]}>
              {value}
            </Text>
          )}
        </View>
      </View>
      <MaterialCommunityIcons
        name="chevron-right"
        size={24}
        color={theme.colors.textTertiary}
      />
    </TouchableOpacity>
  );
};

// Toggle Item Component
interface ToggleItemProps {
  icon: IconName;
  label: string;
  value: boolean;
  onValueChange: (value: boolean) => void;
  theme: any;
  disabled?: boolean;
}

const ToggleItem: React.FC<ToggleItemProps> = ({
  icon,
  label,
  value,
  onValueChange,
  theme,
  disabled = false,
}) => {
  return (
    <View
      style={[
        styles.settingItem,
        { backgroundColor: theme.colors.surface },
        disabled && styles.disabledItem,
      ]}
    >
      <View style={styles.settingContent}>
        <MaterialCommunityIcons
          name={icon}
          size={24}
          color={disabled ? theme.colors.textTertiary : theme.colors.primary}
          style={styles.icon}
        />
        <Text style={[styles.label, { color: theme.colors.text }]}>
          {label}
        </Text>
      </View>
      <Switch
        value={value}
        onValueChange={onValueChange}
        disabled={disabled}
        trackColor={{
          false: theme.colors.border,
          true: theme.colors.primary + '50',
        }}
        thumbColor={value ? theme.colors.primary : theme.colors.textTertiary}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  card: {
    borderWidth: 1,
    borderRadius: 8,
    padding: 12,
    marginVertical: 6,
  },
  textInput: {
    borderWidth: 1,
    borderRadius: 8,
    height: 44,
    paddingHorizontal: 12,
    fontSize: 14,
    marginTop: 4,
  },
  connectionButtons: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 16,
  },
  primaryButton: {
    flex: 1,
    height: 44,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
    marginLeft: 8,
  },
  primaryButtonText: {
    fontSize: 14,
    fontWeight: '600',
  },
  secondaryButton: {
    flex: 1,
    height: 44,
    borderRadius: 8,
    borderWidth: 1,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
  },
  secondaryButtonText: {
    fontSize: 14,
    fontWeight: '600',
  },
  connectionStatus: {
    fontSize: 12,
    marginTop: 10,
  },
  header: {
    paddingHorizontal: 16,
    paddingVertical: 16,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
  },
  section: {
    paddingHorizontal: 16,
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 12,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  settingItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 12,
    marginVertical: 6,
    borderRadius: 8,
  },
  settingContent: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  icon: {
    marginRight: 12,
  },
  settingText: {
    flex: 1,
  },
  label: {
    fontSize: 16,
    fontWeight: '500',
    marginBottom: 2,
  },
  value: {
    fontSize: 12,
    fontWeight: '400',
  },
  actionButton: {
    padding: 8,
  },
  disabledItem: {
    opacity: 0.5,
  },
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 8,
  },
  logoutIcon: {
    marginRight: 8,
  },
  logoutText: {
    fontSize: 16,
    fontWeight: '600',
  },
});

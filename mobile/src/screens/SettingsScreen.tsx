// mobile/src/screens/SettingsScreen.tsx
// 设置界面

import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Switch,
  SafeAreaView,
  Alert,
} from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTheme, ThemeMode } from '../theme';
import { useAuthStore } from '../store/authStore';

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
          <SettingItem
            icon="key-outline"
            label="API Keys"
            onPress={() => navigation.navigate('APIKeys')}
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

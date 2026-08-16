import React from 'react';
import {
  Alert,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useAuthStore } from '../store/authStore';
import { useTheme } from '../theme';

export const SettingsScreen: React.FC = () => {
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuthStore();

  const handleLogout = () => {
    Alert.alert('Logout', 'Are you sure you want to logout?', [
      { text: 'Cancel' },
      {
        text: 'Logout',
        onPress: logout,
        style: 'destructive',
      },
    ]);
  };

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: theme.colors.background }]}
    >
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={[styles.title, { color: theme.colors.text }]}>Settings</Text>

        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: theme.colors.text }]}>Account</Text>
          <View style={[styles.card, { backgroundColor: theme.colors.surface }]}>
            <MaterialCommunityIcons
              name="account-circle-outline"
              size={24}
              color={theme.colors.primary}
            />
            <View style={styles.cardText}>
              <Text style={[styles.label, { color: theme.colors.text }]}>Signed in</Text>
              <Text style={[styles.value, { color: theme.colors.textSecondary }]}>
                {user?.email ?? 'Authenticated user'}
              </Text>
            </View>
          </View>
        </View>

        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: theme.colors.text }]}>Appearance</Text>
          <TouchableOpacity
            style={[styles.card, { backgroundColor: theme.colors.surface }]}
            onPress={toggleTheme}
          >
            <MaterialCommunityIcons
              name="palette-outline"
              size={24}
              color={theme.colors.primary}
            />
            <View style={styles.cardText}>
              <Text style={[styles.label, { color: theme.colors.text }]}>Theme</Text>
              <Text style={[styles.value, { color: theme.colors.textSecondary }]}>
                {theme.mode === 'auto' ? 'Auto' : theme.mode === 'light' ? 'Light' : 'Dark'}
              </Text>
            </View>
            <MaterialCommunityIcons
              name={theme.isDark ? 'white-balance-sunny' : 'moon-waning-crescent'}
              size={20}
              color={theme.colors.primary}
            />
          </TouchableOpacity>
        </View>

        <TouchableOpacity
          style={[styles.logoutButton, { backgroundColor: theme.colors.error + '20' }]}
          onPress={handleLogout}
        >
          <MaterialCommunityIcons name="logout" size={20} color={theme.colors.error} />
          <Text style={[styles.logoutText, { color: theme.colors.error }]}>Logout</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { padding: 16, paddingBottom: 48 },
  title: { fontSize: 28, fontWeight: '700', marginBottom: 24 },
  section: { marginBottom: 24 },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 12,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 14,
    borderRadius: 8,
  },
  cardText: { flex: 1, marginLeft: 12 },
  label: { fontSize: 16, fontWeight: '500' },
  value: { fontSize: 12, marginTop: 2 },
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 8,
  },
  logoutText: { fontSize: 16, fontWeight: '600', marginLeft: 8 },
});

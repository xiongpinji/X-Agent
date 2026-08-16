import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from '@jest/globals';

describe('commercial mobile navigation', () => {
  it('exposes only authenticated backend-backed product tabs', () => {
    const source = fs.readFileSync(
      path.resolve(__dirname, '..', 'RootNavigator.tsx'),
      'utf8'
    );

    expect(source).toContain('component={TaskTriggerScreen}');
    expect(source).toContain('component={SettingsScreen}');
    expect(source).not.toContain('component={HomeScreen}');
    expect(source).not.toContain('component={TaskListScreen}');
    expect(source).not.toContain('component={WorkflowMonitorScreen}');
  });

  it('does not expose navigation or controls without mounted behavior', () => {
    const login = fs.readFileSync(
      path.resolve(__dirname, '..', '..', 'screens', 'LoginScreen.tsx'),
      'utf8'
    );
    const settings = fs.readFileSync(
      path.resolve(__dirname, '..', '..', 'screens', 'SettingsScreen.tsx'),
      'utf8'
    );

    expect(login).not.toContain("navigate('SignUp')");
    expect(login).not.toContain("navigate('ForgotPassword')");
    expect(login).not.toContain('Sign in with Biometric');
    expect(settings).not.toContain('navigation.navigate');
    expect(settings).not.toContain('Clear Cache');
    expect(settings).not.toContain('Biometric Authentication');
  });
});

// mobile/src/native/BiometricAuth.ts
// 生物识别认证原生模块

import { NativeModules, Platform } from 'react-native';

const { BiometricAuthModule } = NativeModules;

export interface BiometricAuthResult {
  success: boolean;
  error?: string;
}

class BiometricAuth {
  async isBiometricAvailable(): Promise<boolean> {
    try {
      return await BiometricAuthModule.isBiometricAvailable();
    } catch (error) {
      console.error('Check biometric availability error:', error);
      return false;
    }
  }

  async authenticate(reason: string): Promise<BiometricAuthResult> {
    try {
      const result = await BiometricAuthModule.authenticate(reason);
      return result;
    } catch (error) {
      return {
        success: false,
        error: String(error),
      };
    }
  }

  async enrollBiometric(): Promise<BiometricAuthResult> {
    try {
      const result = await BiometricAuthModule.enrollBiometric();
      return result;
    } catch (error) {
      return {
        success: false,
        error: String(error),
      };
    }
  }

  async removeBiometric(): Promise<BiometricAuthResult> {
    try {
      const result = await BiometricAuthModule.removeBiometric();
      return result;
    } catch (error) {
      return {
        success: false,
        error: String(error),
      };
    }
  }
}

export const biometricAuth = new BiometricAuth();

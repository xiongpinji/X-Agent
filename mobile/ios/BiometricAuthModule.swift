// mobile/ios/BiometricAuthModule.swift
// iOS生物识别认证模块

import Foundation
import LocalAuthentication
import React

@objc(BiometricAuthModule)
class BiometricAuthModule: NSObject {

  @objc
  static func requiresMainQueueSetup() -> Bool {
    return true
  }

  @objc
  func isBiometricAvailable(_ resolve: @escaping RCTPromiseResolveBlock,
                           rejecter reject: @escaping RCTPromiseRejectBlock) {
    let context = LAContext()
    var error: NSError?

    let available = context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error)

    if available {
      resolve(true)
    } else {
      resolve(false)
    }
  }

  @objc
  func authenticate(_ reason: String,
                   resolver resolve: @escaping RCTPromiseResolveBlock,
                   rejecter reject: @escaping RCTPromiseRejectBlock) {
    let context = LAContext()
    var error: NSError?

    guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
      reject("BIOMETRIC_NOT_AVAILABLE", "Biometric authentication not available", error)
      return
    }

    context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: reason) { success, error in
      DispatchQueue.main.async {
        if success {
          resolve(["success": true])
        } else {
          reject("BIOMETRIC_AUTH_FAILED", "Biometric authentication failed", error)
        }
      }
    }
  }

  @objc
  func enrollBiometric(_ resolve: @escaping RCTPromiseResolveBlock,
                      rejecter reject: @escaping RCTPromiseRejectBlock) {
    // iOS不支持直接调用生物识别注册
    // 用户需要在系统设置中注册
    resolve(["success": true, "message": "Please enroll biometric in system settings"])
  }

  @objc
  func removeBiometric(_ resolve: @escaping RCTPromiseResolveBlock,
                      rejecter reject: @escaping RCTPromiseRejectBlock) {
    // iOS不支持直接移除生物识别
    resolve(["success": true, "message": "Please remove biometric in system settings"])
  }
}

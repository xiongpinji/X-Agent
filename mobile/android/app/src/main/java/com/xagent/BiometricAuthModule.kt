// mobile/android/app/src/main/java/com/xagent/BiometricAuthModule.kt
// Android生物识别认证模块

package com.xagent

import android.content.Context
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.fragment.app.FragmentActivity
import com.facebook.react.bridge.*
import java.util.concurrent.Executor

class BiometricAuthModule(reactContext: ReactApplicationContext) :
    ReactContextBaseJavaModule(reactContext) {

    override fun getName(): String = "BiometricAuthModule"

    @ReactMethod
    fun isBiometricAvailable(promise: Promise) {
        try {
            val biometricManager = BiometricManager.from(reactApplicationContext)
            val canAuthenticate = biometricManager.canAuthenticate(
                BiometricManager.Authenticators.BIOMETRIC_STRONG or
                BiometricManager.Authenticators.BIOMETRIC_WEAK
            )

            val available = canAuthenticate == BiometricManager.BIOMETRIC_SUCCESS
            promise.resolve(available)
        } catch (e: Exception) {
            promise.reject("ERROR", e.message)
        }
    }

    @ReactMethod
    fun authenticate(reason: String, promise: Promise) {
        try {
            val activity = currentActivity as? FragmentActivity
                ?: throw Exception("Activity not available")

            val executor = Executor { command -> command.run() }
            val biometricPrompt = BiometricPrompt(
                activity,
                executor,
                object : BiometricPrompt.AuthenticationCallback() {
                    override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                        super.onAuthenticationSucceeded(result)
                        val response = Arguments.createMap()
                        response.putBoolean("success", true)
                        promise.resolve(response)
                    }

                    override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                        super.onAuthenticationError(errorCode, errString)
                        promise.reject("AUTH_ERROR", errString.toString())
                    }

                    override fun onAuthenticationFailed() {
                        super.onAuthenticationFailed()
                        promise.reject("AUTH_FAILED", "Authentication failed")
                    }
                }
            )

            val promptInfo = BiometricPrompt.PromptInfo.Builder()
                .setTitle("Biometric Authentication")
                .setSubtitle(reason)
                .setNegativeButtonText("Cancel")
                .build()

            biometricPrompt.authenticate(promptInfo)
        } catch (e: Exception) {
            promise.reject("ERROR", e.message)
        }
    }

    @ReactMethod
    fun enrollBiometric(promise: Promise) {
        promise.resolve(Arguments.createMap().apply {
            putBoolean("success", true)
            putString("message", "Please enroll biometric in system settings")
        })
    }

    @ReactMethod
    fun removeBiometric(promise: Promise) {
        promise.resolve(Arguments.createMap().apply {
            putBoolean("success", true)
            putString("message", "Please remove biometric in system settings")
        })
    }
}

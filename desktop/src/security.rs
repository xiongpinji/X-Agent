use aes_gcm::{
    aead::{Aead, KeyInit, Payload},
    Aes256Gcm, Nonce,
};
use rand::Rng;
use std::path::Path;

pub struct Encryption {
    key: [u8; 32],
}

impl Encryption {
    pub fn new(key: [u8; 32]) -> Self {
        Self { key }
    }

    pub fn from_password(password: &str) -> Self {
        use sha2::{Digest, Sha256};
        let mut hasher = Sha256::new();
        hasher.update(password.as_bytes());
        let result = hasher.finalize();
        let mut key = [0u8; 32];
        key.copy_from_slice(&result[..32]);
        Self { key }
    }

    pub fn encrypt(&self, plaintext: &[u8]) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
        let cipher = Aes256Gcm::new(self.key.as_ref().into());
        let mut rng = rand::thread_rng();
        let nonce_bytes: [u8; 12] = rng.gen();
        let nonce = Nonce::from_slice(&nonce_bytes);

        let ciphertext = cipher
            .encrypt(nonce, Payload::from(plaintext))
            .map_err(|e| format!("Encryption failed: {}", e))?;

        let mut result = Vec::with_capacity(12 + ciphertext.len());
        result.extend_from_slice(&nonce_bytes);
        result.extend_from_slice(&ciphertext);

        Ok(result)
    }

    pub fn decrypt(&self, ciphertext: &[u8]) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
        if ciphertext.len() < 12 {
            return Err("Ciphertext too short".into());
        }

        let (nonce_bytes, encrypted_data) = ciphertext.split_at(12);
        let nonce = Nonce::from_slice(nonce_bytes);
        let cipher = Aes256Gcm::new(self.key.as_ref().into());

        let plaintext = cipher
            .decrypt(nonce, Payload::from(encrypted_data))
            .map_err(|e| format!("Decryption failed: {}", e))?;

        Ok(plaintext)
    }
}

pub fn validate_file_path(base: &Path, requested: &Path) -> Result<(), String> {
    let canonical_base = base.canonicalize().map_err(|e| e.to_string())?;
    let canonical_requested = requested.canonicalize().map_err(|e| e.to_string())?;

    if canonical_requested.strip_prefix(&canonical_base).is_err() {
        return Err("Path traversal attempt detected".to_string());
    }

    Ok(())
}

pub fn validate_backend_origin(backend_url: &str, backend_port: u16) -> Result<(), String> {
    if backend_port == 0 {
        return Err("Backend port must be non-zero".to_string());
    }

    match backend_url {
        "http://127.0.0.1" | "http://localhost" => Ok(()),
        _ => Err("Backend URL must be http://127.0.0.1 or http://localhost".to_string()),
    }
}

pub fn validate_backend_path(path: &str) -> Result<(), String> {
    if !path.starts_with('/') {
        return Err("Backend API path must start with '/'".to_string());
    }

    if path.starts_with("//") || path.contains("://") || path.contains('\\') {
        return Err("Backend API path must be relative to the configured backend".to_string());
    }

    Ok(())
}

pub fn build_backend_url(backend_url: &str, backend_port: u16, path: &str) -> Result<String, String> {
    validate_backend_origin(backend_url, backend_port)?;
    validate_backend_path(path)?;
    Ok(format!("{}:{}{}", backend_url, backend_port, path))
}

pub fn is_safe_filename(filename: &str) -> bool {
    !filename.contains("..") && !filename.contains('/') && !filename.contains('\\')
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_encryption_decryption() {
        let encryption = Encryption::from_password("test_password");
        let plaintext = b"Hello, World!";

        let ciphertext = encryption.encrypt(plaintext).unwrap();
        let decrypted = encryption.decrypt(&ciphertext).unwrap();

        assert_eq!(plaintext, &decrypted[..]);
    }

    #[test]
    fn test_safe_filename() {
        assert!(is_safe_filename("document.txt"));
        assert!(!is_safe_filename("../etc/passwd"));
        assert!(!is_safe_filename("..\\windows\\system32"));
    }

    #[test]
    fn test_backend_origin_allows_only_localhost() {
        assert!(validate_backend_origin("http://127.0.0.1", 8000).is_ok());
        assert!(validate_backend_origin("http://localhost", 8000).is_ok());
        assert!(validate_backend_origin("https://api.example.com", 443).is_err());
        assert!(validate_backend_origin("http://0.0.0.0", 8000).is_err());
        assert!(validate_backend_origin("http://127.0.0.1", 0).is_err());
    }

    #[test]
    fn test_backend_path_must_stay_relative() {
        assert!(validate_backend_path("/health").is_ok());
        assert!(validate_backend_path("/api/agents").is_ok());
        assert!(validate_backend_path("health").is_err());
        assert!(validate_backend_path("//evil.example/path").is_err());
        assert!(validate_backend_path("/\\evil").is_err());
        assert!(validate_backend_path("/http://evil.example").is_err());
    }

    #[test]
    fn test_build_backend_url_rejects_external_inputs() {
        assert_eq!(
            build_backend_url("http://127.0.0.1", 8000, "/health").unwrap(),
            "http://127.0.0.1:8000/health"
        );
        assert!(build_backend_url("https://api.example.com", 443, "/health").is_err());
        assert!(build_backend_url("http://127.0.0.1", 8000, "https://evil.example").is_err());
    }
}

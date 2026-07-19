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

    if !canonical_requested.starts_with(&canonical_base) {
        return Err("Path traversal attempt detected".to_string());
    }

    Ok(())
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
}

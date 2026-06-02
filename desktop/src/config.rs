use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    pub backend_url: String,
    pub backend_port: u16,
    pub data_dir: PathBuf,
    pub log_level: String,
    pub theme: String,
    pub language: String,
    pub auto_update: bool,
    pub offline_mode: bool,
}

impl AppConfig {
    pub fn load() -> Result<Self, Box<dyn std::error::Error>> {
        let config_dir = Self::config_dir();
        let config_path = config_dir.join("config.json");

        if config_path.exists() {
            let content = std::fs::read_to_string(&config_path)?;
            Ok(serde_json::from_str(&content)?)
        } else {
            let config = Self::default();
            config.save()?;
            Ok(config)
        }
    }

    pub fn save(&self) -> Result<(), Box<dyn std::error::Error>> {
        let config_dir = Self::config_dir();
        std::fs::create_dir_all(&config_dir)?;
        let config_path = config_dir.join("config.json");
        let content = serde_json::to_string_pretty(self)?;
        std::fs::write(config_path, content)?;
        Ok(())
    }

    pub fn config_dir() -> PathBuf {
        if let Ok(dir) = std::env::var("XAGENT_CONFIG_DIR") {
            PathBuf::from(dir)
        } else {
            let home = dirs::home_dir().expect("Failed to get home directory");
            home.join(".xagent")
        }
    }

    pub fn data_dir(&self) -> PathBuf {
        if self.data_dir.is_absolute() {
            self.data_dir.clone()
        } else {
            Self::config_dir().join(&self.data_dir)
        }
    }
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            backend_url: "http://localhost".to_string(),
            backend_port: 8000,
            data_dir: PathBuf::from("data"),
            log_level: "info".to_string(),
            theme: "auto".to_string(),
            language: "zh-CN".to_string(),
            auto_update: true,
            offline_mode: false,
        }
    }
}

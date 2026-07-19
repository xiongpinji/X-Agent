use crate::config::AppConfig;
use crate::db::Database;
use std::sync::Arc;
use tokio::sync::RwLock;

pub struct AppState {
    pub db: Arc<Database>,
    pub config: AppConfig,
    pub backend_connected: Arc<RwLock<bool>>,
    pub agent_running: Arc<RwLock<bool>>,
}

impl AppState {
    pub fn new(db: Database, config: AppConfig) -> Self {
        Self {
            db: Arc::new(db),
            config,
            backend_connected: Arc::new(RwLock::new(false)),
            agent_running: Arc::new(RwLock::new(false)),
        }
    }

    pub async fn set_backend_connected(&self, connected: bool) {
        *self.backend_connected.write().await = connected;
    }

    pub async fn is_backend_connected(&self) -> bool {
        *self.backend_connected.read().await
    }

    pub async fn set_agent_running(&self, running: bool) {
        *self.agent_running.write().await = running;
    }

    pub async fn is_agent_running(&self) -> bool {
        *self.agent_running.read().await
    }
}

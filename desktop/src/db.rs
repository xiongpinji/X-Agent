use crate::config::AppConfig;
use sqlx::sqlite::{SqlitePool, SqlitePoolOptions};
use std::sync::Arc;

pub struct Database {
    pool: Arc<SqlitePool>,
    config: AppConfig,
}

impl Database {
    pub fn new(config: &AppConfig) -> Result<Self, Box<dyn std::error::Error>> {
        Ok(Self {
            pool: Arc::new(SqlitePool::new()),
            config: config.clone(),
        })
    }

    pub async fn init(&self) -> Result<(), Box<dyn std::error::Error>> {
        let db_path = self.config.data_dir().join("xagent.db");
        std::fs::create_dir_all(db_path.parent().unwrap())?;

        let database_url = format!("sqlite://{}", db_path.display());
        let pool = SqlitePoolOptions::new()
            .max_connections(5)
            .connect(&database_url)
            .await?;

        // Create tables
        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            "#,
        )
        .execute(&pool)
        .await?;

        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                status TEXT NOT NULL,
                input TEXT,
                output TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
            "#,
        )
        .execute(&pool)
        .await?;

        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            "#,
        )
        .execute(&pool)
        .await?;

        Ok(())
    }

    pub fn pool(&self) -> Arc<SqlitePool> {
        self.pool.clone()
    }
}

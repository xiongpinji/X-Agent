use crate::config::AppConfig;
use sqlx::sqlite::{SqlitePool, SqlitePoolOptions};
use std::sync::Arc;

pub struct Database {
    pool: Arc<SqlitePool>,
    config: AppConfig,
}

impl Database {
    pub fn new(config: &AppConfig) -> Result<Self, Box<dyn std::error::Error>> {
        // connect_lazy：非 async 构造，首次查询时才真正连接。
        // （原实现 SqlitePool::new() 不存在，且 init() 里建的池从未存回 self.pool）
        let db_path = config.data_dir().join("xagent.db");
        std::fs::create_dir_all(db_path.parent().unwrap())?;
        let database_url = format!("sqlite://{}", db_path.display());
        let pool = SqlitePoolOptions::new()
            .max_connections(5)
            .connect_lazy(&database_url)?;
        Ok(Self {
            pool: Arc::new(pool),
            config: config.clone(),
        })
    }

    pub async fn init(&self) -> Result<(), Box<dyn std::error::Error>> {
        // Create tables（使用构造期建立的池）
        let pool = self.pool.as_ref();

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
        .execute(pool)
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
        .execute(pool)
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
        .execute(pool)
        .await?;

        Ok(())
    }

    pub fn pool(&self) -> Arc<SqlitePool> {
        self.pool.clone()
    }
}

use serde::{Deserialize, Serialize};
use tauri::State;

#[derive(Debug, Serialize, Deserialize)]
pub struct AgentStatus {
    pub id: String,
    pub name: String,
    pub status: String,
    pub running: bool,
    pub created_at: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct AgentConfig {
    pub name: String,
    pub description: Option<String>,
    pub model: String,
}

#[tauri::command]
pub async fn start_agent(
    agent_id: String,
    state: State<'_, std::sync::Arc<crate::state::AppState>>,
) -> Result<AgentStatus, String> {
    state.set_agent_running(true).await;

    let backend_url = crate::security::build_backend_url(
        &state.config.backend_url,
        state.config.backend_port,
        &format!("/api/agents/{}/start", agent_id),
    )?;

    let client = reqwest::Client::new();
    let response = client
        .post(&backend_url)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        response.json().await.map_err(|e| e.to_string())
    } else {
        Err(format!("Failed to start agent: {}", response.status()))
    }
}

#[tauri::command]
pub async fn stop_agent(
    agent_id: String,
    state: State<'_, std::sync::Arc<crate::state::AppState>>,
) -> Result<AgentStatus, String> {
    let backend_url = crate::security::build_backend_url(
        &state.config.backend_url,
        state.config.backend_port,
        &format!("/api/agents/{}/stop", agent_id),
    )?;

    let client = reqwest::Client::new();
    let response = client
        .post(&backend_url)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        state.set_agent_running(false).await;
        response.json().await.map_err(|e| e.to_string())
    } else {
        Err(format!("Failed to stop agent: {}", response.status()))
    }
}

#[tauri::command]
pub async fn get_agent_status(
    agent_id: String,
    state: State<'_, std::sync::Arc<crate::state::AppState>>,
) -> Result<AgentStatus, String> {
    let backend_url = crate::security::build_backend_url(
        &state.config.backend_url,
        state.config.backend_port,
        &format!("/api/agents/{}", agent_id),
    )?;

    let client = reqwest::Client::new();
    let response = client
        .get(&backend_url)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        response.json().await.map_err(|e| e.to_string())
    } else {
        Err(format!("Failed to get agent status: {}", response.status()))
    }
}

#[tauri::command]
pub async fn list_agents(
    state: State<'_, std::sync::Arc<crate::state::AppState>>,
) -> Result<Vec<AgentStatus>, String> {
    let backend_url = crate::security::build_backend_url(
        &state.config.backend_url,
        state.config.backend_port,
        "/api/agents",
    )?;

    let client = reqwest::Client::new();
    let response = client
        .get(&backend_url)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        response.json().await.map_err(|e| e.to_string())
    } else {
        Err(format!("Failed to list agents: {}", response.status()))
    }
}

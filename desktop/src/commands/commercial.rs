use serde::Serialize;
use std::sync::Arc;
use tauri::State;

use crate::state::{
    AppState, AuthSession, CancelResponse, CommandError, RunStatusResponse, TriggerResponse,
};

#[derive(Debug, Serialize)]
pub struct BackendConfiguration {
    pub configured: bool,
    pub base_url: String,
}

#[tauri::command]
pub async fn configure_backend(
    base_url: String,
    state: State<'_, Arc<AppState>>,
) -> Result<BackendConfiguration, CommandError> {
    let base_url = state.configure_backend(&base_url).await?;
    Ok(BackendConfiguration {
        configured: true,
        base_url,
    })
}

#[tauri::command]
pub async fn login(
    email: String,
    password: String,
    state: State<'_, Arc<AppState>>,
) -> Result<AuthSession, CommandError> {
    state.login(&email, &password).await
}

#[tauri::command]
pub async fn logout(state: State<'_, Arc<AppState>>) -> Result<bool, CommandError> {
    Ok(state.logout().await)
}

#[tauri::command]
pub async fn trigger_agent(
    agent_id: String,
    task: String,
    operation_id: String,
    state: State<'_, Arc<AppState>>,
) -> Result<TriggerResponse, CommandError> {
    state.trigger_agent(&agent_id, &task, &operation_id).await
}

#[tauri::command]
pub async fn get_run_status(
    run_id: String,
    state: State<'_, Arc<AppState>>,
) -> Result<RunStatusResponse, CommandError> {
    state.get_run_status(&run_id).await
}

#[tauri::command]
pub async fn cancel_run(
    run_id: String,
    state: State<'_, Arc<AppState>>,
) -> Result<CancelResponse, CommandError> {
    state.cancel_run(&run_id).await
}

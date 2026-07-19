use serde_json::{json, Value};
use tauri::State;

#[tauri::command]
pub async fn get_settings(
    state: State<'_, std::sync::Arc<crate::state::AppState>>,
) -> Result<Value, String> {
    Ok(json!({
        "backend_url": state.config.backend_url,
        "backend_port": state.config.backend_port,
        "log_level": state.config.log_level,
        "theme": state.config.theme,
        "language": state.config.language,
        "auto_update": state.config.auto_update,
        "offline_mode": state.config.offline_mode,
    }))
}

#[tauri::command]
pub async fn update_settings(
    settings: Value,
    state: State<'_, std::sync::Arc<crate::state::AppState>>,
) -> Result<(), String> {
    // This would need to be implemented with mutable state
    // For now, just log the update
    log::info!("Settings update requested: {:?}", settings);
    Ok(())
}

#[tauri::command]
pub async fn get_theme(
    state: State<'_, std::sync::Arc<crate::state::AppState>>,
) -> Result<String, String> {
    Ok(state.config.theme.clone())
}

#[tauri::command]
pub async fn set_theme(
    theme: String,
    state: State<'_, std::sync::Arc<crate::state::AppState>>,
) -> Result<(), String> {
    if !["light", "dark", "auto"].contains(&theme.as_str()) {
        return Err("Invalid theme".to_string());
    }
    log::info!("Theme changed to: {}", theme);
    Ok(())
}

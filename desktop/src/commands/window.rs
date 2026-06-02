use tauri::{AppHandle, Manager};

#[tauri::command]
pub async fn minimize_window(app_handle: AppHandle) -> Result<(), String> {
    if let Some(window) = app_handle.get_window("main") {
        window.minimize().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
pub async fn maximize_window(app_handle: AppHandle) -> Result<(), String> {
    if let Some(window) = app_handle.get_window("main") {
        window.maximize().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
pub async fn close_window(app_handle: AppHandle) -> Result<(), String> {
    if let Some(window) = app_handle.get_window("main") {
        window.close().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
pub async fn toggle_devtools(app_handle: AppHandle) -> Result<(), String> {
    if let Some(window) = app_handle.get_window("main") {
        window.open_devtools();
    }
    Ok(())
}

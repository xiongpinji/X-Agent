use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use tauri::State;

#[derive(Debug, Serialize, Deserialize)]
pub struct FileInfo {
    pub path: String,
    pub name: String,
    pub is_dir: bool,
    pub size: u64,
    pub modified: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct DirectoryEntry {
    pub path: String,
    pub name: String,
    pub is_dir: bool,
    pub size: u64,
}

#[tauri::command]
pub async fn read_file(
    path: String,
    state: State<'_, std::sync::Arc<crate::state::AppState>>,
) -> Result<String, String> {
    let file_path = PathBuf::from(&path);
    let base_dir = state.config.data_dir();

    crate::security::validate_file_path(&base_dir, &file_path)
        .map_err(|e| format!("Security check failed: {}", e))?;

    std::fs::read_to_string(&file_path).map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn write_file(
    path: String,
    content: String,
    state: State<'_, std::sync::Arc<crate::state::AppState>>,
) -> Result<(), String> {
    let file_path = PathBuf::from(&path);
    let base_dir = state.config.data_dir();

    crate::security::validate_file_path(&base_dir, &file_path)
        .map_err(|e| format!("Security check failed: {}", e))?;

    if let Some(parent) = file_path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }

    std::fs::write(&file_path, content).map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn list_directory(
    path: String,
    state: State<'_, std::sync::Arc<crate::state::AppState>>,
) -> Result<Vec<DirectoryEntry>, String> {
    let dir_path = PathBuf::from(&path);
    let base_dir = state.config.data_dir();

    crate::security::validate_file_path(&base_dir, &dir_path)
        .map_err(|e| format!("Security check failed: {}", e))?;

    let mut entries = Vec::new();

    for entry in std::fs::read_dir(&dir_path).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let path = entry.path();
        let metadata = entry.metadata().map_err(|e| e.to_string())?;

        entries.push(DirectoryEntry {
            path: path.to_string_lossy().to_string(),
            name: path
                .file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string(),
            is_dir: metadata.is_dir(),
            size: metadata.len(),
        });
    }

    Ok(entries)
}

#[tauri::command]
pub async fn create_directory(
    path: String,
    state: State<'_, std::sync::Arc<crate::state::AppState>>,
) -> Result<(), String> {
    let dir_path = PathBuf::from(&path);
    let base_dir = state.config.data_dir();

    crate::security::validate_file_path(&base_dir, &dir_path)
        .map_err(|e| format!("Security check failed: {}", e))?;

    std::fs::create_dir_all(&dir_path).map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn delete_file(
    path: String,
    state: State<'_, std::sync::Arc<crate::state::AppState>>,
) -> Result<(), String> {
    let file_path = PathBuf::from(&path);
    let base_dir = state.config.data_dir();

    crate::security::validate_file_path(&base_dir, &file_path)
        .map_err(|e| format!("Security check failed: {}", e))?;

    std::fs::remove_file(&file_path).map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn delete_directory(
    path: String,
    state: State<'_, std::sync::Arc<crate::state::AppState>>,
) -> Result<(), String> {
    let dir_path = PathBuf::from(&path);
    let base_dir = state.config.data_dir();

    crate::security::validate_file_path(&base_dir, &dir_path)
        .map_err(|e| format!("Security check failed: {}", e))?;

    std::fs::remove_dir_all(&dir_path).map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn get_file_info(
    path: String,
    state: State<'_, std::sync::Arc<crate::state::AppState>>,
) -> Result<FileInfo, String> {
    let file_path = PathBuf::from(&path);
    let base_dir = state.config.data_dir();

    crate::security::validate_file_path(&base_dir, &file_path)
        .map_err(|e| format!("Security check failed: {}", e))?;

    let metadata = std::fs::metadata(&file_path).map_err(|e| e.to_string())?;
    let modified = metadata
        .modified()
        .ok()
        .and_then(|t| {
            t.duration_since(std::time::UNIX_EPOCH)
                .ok()
                .map(|d| d.as_secs())
        })
        .unwrap_or(0);

    Ok(FileInfo {
        path: file_path.to_string_lossy().to_string(),
        name: file_path
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .to_string(),
        is_dir: metadata.is_dir(),
        size: metadata.len(),
        modified: chrono::DateTime::from_timestamp(modified as i64, 0)
            .map(|dt| dt.to_rfc3339())
            .unwrap_or_default(),
    })
}

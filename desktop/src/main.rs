// Prevents an additional console window on Windows in release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod state;

use std::sync::Arc;
use tauri::generate_handler;

use crate::state::AppState;

fn main() {
    tauri::Builder::default()
        .manage(Arc::new(AppState::new()))
        .invoke_handler(generate_handler![
            commands::commercial::configure_backend,
            commands::commercial::login,
            commands::commercial::logout,
            commands::commercial::trigger_agent,
            commands::commercial::get_run_status,
            commands::commercial::cancel_run,
        ])
        .run(tauri::generate_context!())
        .expect("failed to run X-Agent Desktop");
}

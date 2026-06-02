// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod config;
mod db;
mod ipc;
mod security;
mod state;
mod tray;
mod utils;

use tauri::{
    generate_handler, App, AppHandle, GlobalShortcutManager, Manager, SystemTray,
    SystemTrayEvent,
};
use std::sync::Arc;

use crate::config::AppConfig;
use crate::db::Database;
use crate::state::AppState;

fn main() {
    env_logger::init();

    let app_config = AppConfig::load().expect("Failed to load config");
    let db = Database::new(&app_config).expect("Failed to initialize database");

    let app_state = Arc::new(AppState::new(db, app_config));

    tauri::Builder::default()
        .setup(|app| {
            setup_app(app, app_state.clone())?;
            Ok(())
        })
        .system_tray(SystemTray::new().with_menu(tray::build_menu()))
        .on_system_tray_event(|app, event| tray::handle_tray_event(app, event))
        .invoke_handler(generate_handler![
            commands::file::read_file,
            commands::file::write_file,
            commands::file::list_directory,
            commands::file::create_directory,
            commands::file::delete_file,
            commands::file::delete_directory,
            commands::file::get_file_info,
            commands::agent::start_agent,
            commands::agent::stop_agent,
            commands::agent::get_agent_status,
            commands::agent::list_agents,
            commands::api::call_backend_api,
            commands::api::get_backend_status,
            commands::settings::get_settings,
            commands::settings::update_settings,
            commands::settings::get_theme,
            commands::settings::set_theme,
            commands::window::minimize_window,
            commands::window::maximize_window,
            commands::window::close_window,
            commands::window::toggle_devtools,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

fn setup_app(app: &mut App, state: Arc<AppState>) -> Result<(), Box<dyn std::error::Error>> {
    let app_handle = app.handle();

    // Store state in app
    app.manage(state.clone());

    // Setup global shortcuts
    setup_global_shortcuts(&app_handle)?;

    // Initialize database
    state.db.init().expect("Failed to initialize database");

    // Start backend connection
    let app_handle_clone = app_handle.clone();
    tauri::async_runtime::spawn(async move {
        if let Err(e) = ipc::connect_to_backend(&app_handle_clone).await {
            log::error!("Failed to connect to backend: {}", e);
        }
    });

    Ok(())
}

fn setup_global_shortcuts(app_handle: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    let mut shortcut_manager = app_handle.global_shortcut_manager();

    // Register global shortcut to show/hide window
    shortcut_manager.register("CmdOrCtrl+Shift+X", {
        let app_handle = app_handle.clone();
        move || {
            if let Some(window) = app_handle.get_window("main") {
                if window.is_visible().unwrap_or(false) {
                    let _ = window.hide();
                } else {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
        }
    })?;

    Ok(())
}

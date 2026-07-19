use tauri::{
    AppHandle, CustomMenuItem, Manager, SystemTrayMenu, SystemTrayMenuItem, SystemTrayEvent,
};

pub fn build_menu() -> SystemTrayMenu {
    let show = CustomMenuItem::new("show", "显示");
    let hide = CustomMenuItem::new("hide", "隐藏");
    let settings = CustomMenuItem::new("settings", "设置");
    let quit = CustomMenuItem::new("quit", "退出");

    SystemTrayMenu::new()
        .add_item(show)
        .add_item(hide)
        .add_native_item(SystemTrayMenuItem::Separator)
        .add_item(settings)
        .add_native_item(SystemTrayMenuItem::Separator)
        .add_item(quit)
}

pub fn handle_tray_event(app: &AppHandle, event: SystemTrayEvent) {
    match event {
        SystemTrayEvent::LeftClick { .. } => {
            if let Some(window) = app.get_window("main") {
                if window.is_visible().unwrap_or(false) {
                    let _ = window.hide();
                } else {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
        }
        SystemTrayEvent::MenuItemClick { id, .. } => match id.as_str() {
            "show" => {
                if let Some(window) = app.get_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
            "hide" => {
                if let Some(window) = app.get_window("main") {
                    let _ = window.hide();
                }
            }
            "settings" => {
                if let Some(window) = app.get_window("main") {
                    let _ = window.emit("navigate", "/settings");
                }
            }
            "quit" => {
                std::process::exit(0);
            }
            _ => {}
        },
        _ => {}
    }
}

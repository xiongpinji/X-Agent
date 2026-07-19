use serde_json::{json, Value};
use tauri::State;

#[tauri::command]
pub async fn call_backend_api(
    method: String,
    path: String,
    body: Option<Value>,
    state: State<'_, std::sync::Arc<crate::state::AppState>>,
) -> Result<Value, String> {
    let backend_url = format!(
        "{}:{}{}",
        state.config.backend_url, state.config.backend_port, path
    );

    let client = reqwest::Client::new();

    let response = match method.as_str() {
        "GET" => client.get(&backend_url).send().await,
        "POST" => {
            let mut req = client.post(&backend_url);
            if let Some(b) = body {
                req = req.json(&b);
            }
            req.send().await
        }
        "PUT" => {
            let mut req = client.put(&backend_url);
            if let Some(b) = body {
                req = req.json(&b);
            }
            req.send().await
        }
        "DELETE" => client.delete(&backend_url).send().await,
        "PATCH" => {
            let mut req = client.patch(&backend_url);
            if let Some(b) = body {
                req = req.json(&b);
            }
            req.send().await
        }
        _ => return Err("Unsupported HTTP method".to_string()),
    };

    match response {
        Ok(resp) => {
            if resp.status().is_success() {
                resp.json().await.map_err(|e| e.to_string())
            } else {
                Err(format!("Backend error: {}", resp.status()))
            }
        }
        Err(e) => Err(e.to_string()),
    }
}

#[tauri::command]
pub async fn get_backend_status(
    state: State<'_, std::sync::Arc<crate::state::AppState>>,
) -> Result<Value, String> {
    let backend_url = format!(
        "{}:{}/health",
        state.config.backend_url, state.config.backend_port
    );

    let client = reqwest::Client::new();
    match client.get(&backend_url).send().await {
        Ok(response) => {
            if response.status().is_success() {
                state.set_backend_connected(true).await;
                response.json().await.map_err(|e| e.to_string())
            } else {
                state.set_backend_connected(false).await;
                Err(format!("Backend error: {}", response.status()))
            }
        }
        Err(e) => {
            state.set_backend_connected(false).await;
            Err(e.to_string())
        }
    }
}

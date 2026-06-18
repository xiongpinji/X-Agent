use futures::StreamExt;
use tauri::{AppHandle, Manager};

pub async fn connect_to_backend(app_handle: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    let config = app_handle.state::<std::sync::Arc<crate::state::AppState>>();
    let backend_url = crate::security::build_backend_url(
        &config.config.backend_url,
        config.config.backend_port,
        "/health",
    )
    .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidInput, e))?;

    // Try to connect to backend
    let client = reqwest::Client::new();
    match client.get(&backend_url).send().await {
        Ok(response) if response.status().is_success() => {
            config.set_backend_connected(true).await;
            log::info!("Connected to backend at {}", backend_url);
            Ok(())
        }
        _ => {
            config.set_backend_connected(false).await;
            log::warn!("Failed to connect to backend at {}", backend_url);
            Err("Backend connection failed".into())
        }
    }
}

pub async fn call_backend(
    app_handle: &AppHandle,
    method: &str,
    path: &str,
    body: Option<serde_json::Value>,
) -> Result<serde_json::Value, Box<dyn std::error::Error>> {
    let config = app_handle.state::<std::sync::Arc<crate::state::AppState>>();
    let url = crate::security::build_backend_url(
        &config.config.backend_url,
        config.config.backend_port,
        path,
    )
    .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidInput, e))?;
    let client = reqwest::Client::new();

    let response = match method {
        "GET" => client.get(&url).send().await?,
        "POST" => {
            let mut req = client.post(&url);
            if let Some(b) = body {
                req = req.json(&b);
            }
            req.send().await?
        }
        "PUT" => {
            let mut req = client.put(&url);
            if let Some(b) = body {
                req = req.json(&b);
            }
            req.send().await?
        }
        "DELETE" => client.delete(&url).send().await?,
        _ => return Err("Unsupported HTTP method".into()),
    };

    if response.status().is_success() {
        Ok(response.json().await?)
    } else {
        Err(format!("Backend error: {}", response.status()).into())
    }
}

pub async fn stream_backend(
    app_handle: &AppHandle,
    path: &str,
    body: serde_json::Value,
) -> Result<impl futures::Stream<Item = Result<String, Box<dyn std::error::Error>>>, Box<dyn std::error::Error>> {
    let config = app_handle.state::<std::sync::Arc<crate::state::AppState>>();
    let url = crate::security::build_backend_url(
        &config.config.backend_url,
        config.config.backend_port,
        path,
    )
    .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidInput, e))?;
    let client = reqwest::Client::new();

    let response = client.post(&url).json(&body).send().await?;

    if response.status().is_success() {
        Ok(response.bytes_stream().map(|result| {
            result
                .map(|bytes| String::from_utf8_lossy(&bytes).to_string())
                .map_err(|e| Box::new(e) as Box<dyn std::error::Error>)
        }))
    } else {
        Err(format!("Backend error: {}", response.status()).into())
    }
}

use reqwest::{Client, StatusCode, Url};
use serde::{de::DeserializeOwned, Deserialize, Serialize};
use std::time::Duration;
use tokio::sync::RwLock;

const MAX_RESPONSE_BYTES: usize = 1_048_576;

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct CommandError {
    pub code: &'static str,
    pub message: &'static str,
    pub status: Option<u16>,
}

impl CommandError {
    pub const fn new(code: &'static str, message: &'static str) -> Self {
        Self {
            code,
            message,
            status: None,
        }
    }

    fn from_status(status: StatusCode) -> Self {
        let (code, message) = match status.as_u16() {
            400 | 422 => ("validation_failed", "The request was rejected."),
            401 => ("authentication_failed", "Authentication failed."),
            403 => (
                "authorization_failed",
                "This account is not allowed to perform the action.",
            ),
            404 => ("not_found", "The requested resource was not found."),
            409 => (
                "conflict",
                "The operation conflicts with the current state.",
            ),
            429 => ("rate_limited", "Too many requests. Try again later."),
            _ => ("backend_unavailable", "The X-Agent service is unavailable."),
        };
        Self {
            code,
            message,
            status: Some(status.as_u16()),
        }
    }
}

#[derive(Debug, Deserialize)]
struct LoginWireResponse {
    access_token: String,
    user: serde_json::Value,
}

#[derive(Debug, Serialize)]
pub struct AuthSession {
    pub authenticated: bool,
    pub user: serde_json::Value,
}

#[derive(Debug, Serialize, Deserialize, PartialEq)]
pub struct TriggerResponse {
    pub run_id: String,
    pub trace_id: String,
    pub status: String,
    pub created_at: String,
}

#[derive(Debug, Serialize, Deserialize, PartialEq)]
pub struct RunStatusResponse {
    pub run_id: String,
    pub trace_id: String,
    pub status: String,
    pub progress_percent: f64,
    pub current_step: String,
    pub started_at: Option<String>,
    pub completed_at: Option<String>,
    pub result_summary: String,
    pub error: Option<String>,
    pub error_code: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, PartialEq)]
pub struct CancelResponse {
    pub run_id: String,
    pub status: String,
}

pub struct AppState {
    client: Client,
    backend_url: RwLock<Option<Url>>,
    access_token: RwLock<Option<String>>,
}

impl AppState {
    pub fn new() -> Self {
        Self {
            client: Client::builder()
                .connect_timeout(Duration::from_secs(10))
                .timeout(Duration::from_secs(30))
                .build()
                .expect("desktop HTTP client configuration must be valid"),
            backend_url: RwLock::new(None),
            access_token: RwLock::new(None),
        }
    }

    pub async fn configure_backend(&self, raw: &str) -> Result<String, CommandError> {
        let normalized = validate_backend_url(raw)?;
        *self.backend_url.write().await = Some(normalized.clone());
        *self.access_token.write().await = None;
        Ok(normalized.to_string().trim_end_matches('/').to_owned())
    }

    pub async fn login(&self, email: &str, password: &str) -> Result<AuthSession, CommandError> {
        let email = email.trim();
        if email.is_empty() || email.len() > 320 || password.is_empty() || password.len() > 4096 {
            return Err(CommandError::new(
                "invalid_credentials",
                "Email and password are required.",
            ));
        }
        let response: LoginWireResponse = self
            .send_json(
                reqwest::Method::POST,
                "/api/v1/auth/login",
                Some(serde_json::json!({"email": email, "password": password})),
                false,
            )
            .await?;
        if response.access_token.is_empty() || response.access_token.len() > 4096 {
            return Err(CommandError::new(
                "invalid_backend_response",
                "The X-Agent service returned an invalid response.",
            ));
        }
        *self.access_token.write().await = Some(response.access_token);
        Ok(AuthSession {
            authenticated: true,
            user: response.user,
        })
    }

    pub async fn logout(&self) -> bool {
        let Some(token) = self.access_token.write().await.take() else {
            return true;
        };
        let Some(base) = self.backend_url.read().await.clone() else {
            return false;
        };
        let Ok(url) = base.join("/api/v1/auth/logout") else {
            return false;
        };
        self.client
            .post(url)
            .header(reqwest::header::AUTHORIZATION, format!("Bearer {token}"))
            .send()
            .await
            .is_ok_and(|response| response.status().is_success())
    }

    pub async fn trigger_agent(
        &self,
        agent_id: &str,
        task: &str,
        operation_id: &str,
    ) -> Result<TriggerResponse, CommandError> {
        let agent_id = bounded_text(agent_id, 128, "agent_id")?;
        let task = bounded_text(task, 4096, "task")?;
        let operation_id = bounded_text(operation_id, 220, "operation_id")?;
        self.send_json(
            reqwest::Method::POST,
            "/api/v1/mobile/trigger",
            Some(serde_json::json!({
                "agent_id": agent_id,
                "task": task,
                "operation_id": operation_id,
                "notify_on_complete": false,
                "metadata": {"client": "desktop"}
            })),
            true,
        )
        .await
    }

    pub async fn get_run_status(&self, run_id: &str) -> Result<RunStatusResponse, CommandError> {
        let run_id = validate_run_id(run_id)?;
        self.send_json(
            reqwest::Method::GET,
            &format!("/api/v1/mobile/runs/{run_id}/status"),
            None,
            true,
        )
        .await
    }

    pub async fn cancel_run(&self, run_id: &str) -> Result<CancelResponse, CommandError> {
        let run_id = validate_run_id(run_id)?;
        self.send_json(
            reqwest::Method::POST,
            &format!("/api/v1/mobile/runs/{run_id}/cancel"),
            None,
            true,
        )
        .await
    }

    async fn send_json<T: DeserializeOwned>(
        &self,
        method: reqwest::Method,
        path: &str,
        body: Option<serde_json::Value>,
        authenticated: bool,
    ) -> Result<T, CommandError> {
        let base = self.backend_url.read().await.clone().ok_or_else(|| {
            CommandError::new(
                "backend_not_configured",
                "Configure the X-Agent service first.",
            )
        })?;
        let url = base.join(path).map_err(|_| {
            CommandError::new("invalid_backend_url", "The X-Agent service URL is invalid.")
        })?;
        let mut request = self.client.request(method, url);
        if authenticated {
            let token = self.access_token.read().await.clone().ok_or_else(|| {
                CommandError::new(
                    "authentication_required",
                    "Sign in before running an Agent.",
                )
            })?;
            request = request.header(reqwest::header::AUTHORIZATION, format!("Bearer {token}"));
        }
        if let Some(payload) = body {
            request = request.json(&payload);
        }
        let mut response = request.send().await.map_err(|_| {
            CommandError::new("backend_unavailable", "The X-Agent service is unavailable.")
        })?;
        let status = response.status();
        if !status.is_success() {
            return Err(CommandError::from_status(status));
        }
        if response
            .content_length()
            .is_some_and(|size| size > MAX_RESPONSE_BYTES as u64)
        {
            return Err(invalid_backend_response());
        }
        let mut bytes = Vec::new();
        while let Some(chunk) = response
            .chunk()
            .await
            .map_err(|_| invalid_backend_response())?
        {
            if bytes.len().saturating_add(chunk.len()) > MAX_RESPONSE_BYTES {
                return Err(invalid_backend_response());
            }
            bytes.extend_from_slice(&chunk);
        }
        serde_json::from_slice(&bytes).map_err(|_| invalid_backend_response())
    }
}

fn invalid_backend_response() -> CommandError {
    CommandError::new(
        "invalid_backend_response",
        "The X-Agent service returned an invalid response.",
    )
}

fn validate_backend_url(raw: &str) -> Result<Url, CommandError> {
    let trimmed = raw.trim().trim_end_matches('/');
    let mut url = Url::parse(trimmed).map_err(|_| {
        CommandError::new("invalid_backend_url", "Enter a valid X-Agent service URL.")
    })?;
    let host = url.host_str().unwrap_or_default();
    let local = matches!(host, "localhost" | "127.0.0.1" | "::1");
    if (url.scheme() != "https" && !(url.scheme() == "http" && local))
        || !url.username().is_empty()
        || url.password().is_some()
        || url.query().is_some()
        || url.fragment().is_some()
        || !matches!(url.path(), "" | "/")
    {
        return Err(CommandError::new(
            "invalid_backend_url",
            "Use HTTPS, or HTTP only for localhost development.",
        ));
    }
    url.set_path("/");
    Ok(url)
}

fn bounded_text<'a>(value: &'a str, max: usize, field: &str) -> Result<&'a str, CommandError> {
    let normalized = value.trim();
    if normalized.is_empty() || normalized.chars().count() > max {
        let message = match field {
            "task" => "Enter a task between 1 and 4096 characters.",
            "operation_id" => "The operation identifier is invalid.",
            _ => "The Agent identifier is invalid.",
        };
        return Err(CommandError::new("invalid_request", message));
    }
    Ok(normalized)
}

fn validate_run_id(run_id: &str) -> Result<&str, CommandError> {
    let normalized = run_id.trim();
    if normalized.len() > 64 || uuid::Uuid::parse_str(normalized).is_err() {
        return Err(CommandError::new(
            "invalid_run_id",
            "The run identifier is invalid.",
        ));
    }
    Ok(normalized)
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    use tokio::net::TcpListener;

    async fn serve(responses: Vec<&'static str>) -> (String, tokio::task::JoinHandle<Vec<String>>) {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let address = listener.local_addr().unwrap();
        let task = tokio::spawn(async move {
            let mut requests = Vec::new();
            for response in responses {
                let (mut stream, _) = listener.accept().await.unwrap();
                let mut buffer = vec![0_u8; 16_384];
                let count = stream.read(&mut buffer).await.unwrap();
                requests.push(String::from_utf8_lossy(&buffer[..count]).into_owned());
                let reply = format!(
                    "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                    response.len(),
                    response
                );
                stream.write_all(reply.as_bytes()).await.unwrap();
            }
            requests
        });
        (format!("http://127.0.0.1:{}", address.port()), task)
    }

    #[test]
    fn backend_url_rejects_remote_plaintext_and_url_credentials() {
        assert_eq!(
            validate_backend_url("http://example.test")
                .unwrap_err()
                .code,
            "invalid_backend_url"
        );
        assert!(validate_backend_url("https://user:pass@example.test").is_err());
        assert!(validate_backend_url("https://example.test/api").is_err());
        assert!(validate_backend_url("http://localhost:8000").is_ok());
        assert!(validate_backend_url("https://api.example.test/").is_ok());
    }

    #[tokio::test]
    async fn authenticated_agent_lifecycle_uses_fixed_paths_and_bearer_header() {
        let run_id = "11111111-1111-4111-8111-111111111111";
        let (base, server) = serve(vec![
            r#"{"access_token":"access-secret","refresh_token":"refresh-secret","user":{"id":"user-1"}}"#,
            r#"{"run_id":"11111111-1111-4111-8111-111111111111","trace_id":"trace-1","status":"pending","created_at":"now"}"#,
            r#"{"run_id":"11111111-1111-4111-8111-111111111111","trace_id":"trace-1","status":"completed","progress_percent":100,"current_step":"Done","started_at":"now","completed_at":"now","result_summary":"answer","error":null,"error_code":null}"#,
            r#"{"run_id":"11111111-1111-4111-8111-111111111111","status":"cancelled"}"#,
            r#"{"logged_out":true}"#,
        ]).await;
        let state = AppState::new();
        state.configure_backend(&base).await.unwrap();
        state.login("owner@example.test", "password").await.unwrap();
        state
            .trigger_agent("agent-1", "task", "desktop-op-1")
            .await
            .unwrap();
        state.get_run_status(run_id).await.unwrap();
        state.cancel_run(run_id).await.unwrap();
        assert!(state.logout().await);

        let requests = server.await.unwrap();
        assert!(requests[0].starts_with("POST /api/v1/auth/login HTTP/1.1"));
        assert!(requests[1].starts_with("POST /api/v1/mobile/trigger HTTP/1.1"));
        assert!(
            requests[2].starts_with(&format!("GET /api/v1/mobile/runs/{run_id}/status HTTP/1.1"))
        );
        assert!(requests[3].starts_with(&format!(
            "POST /api/v1/mobile/runs/{run_id}/cancel HTTP/1.1"
        )));
        assert!(requests[4].starts_with("POST /api/v1/auth/logout HTTP/1.1"));
        for request in &requests[1..] {
            assert!(request
                .to_ascii_lowercase()
                .contains("authorization: bearer access-secret"));
        }
        assert!(!requests[0].contains("access-secret"));
    }
}

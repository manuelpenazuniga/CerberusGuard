use std::{net::SocketAddr, sync::{Arc, Mutex}};

use anyhow::{Context, Result};
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use cerberus_types::TrustEvent;
use clap::Parser;
use rusqlite::{params, Connection};
use serde_json::{json, Value};
use tower_http::cors::CorsLayer;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[derive(Parser, Debug)]
#[command(name = "cerberus-collector")]
struct Args {
    #[arg(long, default_value = "0.0.0.0:9090")]
    listen: String,
    #[arg(long, default_value = "./cerberusguard.sqlite")]
    db: String,
}

#[derive(Clone)]
struct AppState {
    db: Arc<Mutex<Connection>>,
}

#[derive(serde::Deserialize)]
struct EventsQuery {
    limit: Option<usize>,
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::from_default_env())
        .with(tracing_subscriber::fmt::layer())
        .init();

    let args = Args::parse();
    let conn = Connection::open(&args.db).with_context(|| format!("open db {}", args.db))?;
    init_db(&conn)?;

    let state = AppState {
        db: Arc::new(Mutex::new(conn)),
    };

    let app = Router::new()
        .route("/health", get(health))
        .route("/events", post(post_event).get(get_events))
        .route("/correlations/{id}", get(get_correlation))
        .route("/metrics", get(get_metrics))
        .with_state(state)
        .layer(CorsLayer::permissive());

    let addr: SocketAddr = args.listen.parse().context("invalid --listen address")?;
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;
    Ok(())
}

fn init_db(conn: &Connection) -> Result<()> {
    conn.execute_batch(
        "
        CREATE TABLE IF NOT EXISTS trust_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          timestamp TEXT NOT NULL,
          agent_id TEXT NOT NULL,
          request_id TEXT,
          correlation_id TEXT NOT NULL,
          layer TEXT NOT NULL,
          verdict TEXT NOT NULL,
          action TEXT NOT NULL,
          payload TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_trust_events_correlation_id ON trust_events(correlation_id);
        CREATE INDEX IF NOT EXISTS idx_trust_events_agent_id ON trust_events(agent_id);
        CREATE INDEX IF NOT EXISTS idx_trust_events_timestamp ON trust_events(timestamp);
        ",
    )?;
    Ok(())
}

async fn health() -> &'static str {
    "ok"
}

async fn post_event(
    State(state): State<AppState>,
    Json(event): Json<TrustEvent>,
) -> impl IntoResponse {
    // `payload` is free-form JSON, so re-serialisation can in principle fail
    // (although in practice arbitrary `serde_json::Value` always serialises).
    let payload = match serde_json::to_string(&event.payload) {
        Ok(value) => value,
        Err(err) => return (StatusCode::BAD_REQUEST, format!("invalid payload json: {err}")),
    };
    // Layer/Verdict are payload-less enums; `as_str()` is infallible by
    // construction and matches the serde-serialised form exactly (guarded
    // by `as_str_matches_serde_serialised_form` in cerberus-types tests).
    let layer = event.layer.as_str();
    let verdict = event.verdict.as_str();

    let conn = match state.db.lock() {
        Ok(guard) => guard,
        Err(err) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("db lock poisoned: {err}"),
            );
        }
    };

    match conn.execute(
        "INSERT INTO trust_events
        (timestamp, agent_id, request_id, correlation_id, layer, verdict, action, payload)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
        params![
            event.timestamp.to_rfc3339(),
            event.agent_id,
            event.request_id,
            event.correlation_id,
            layer,
            verdict,
            event.action,
            payload
        ],
    ) {
        Ok(_) => (StatusCode::CREATED, "created".to_string()),
        Err(err) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("failed to persist event: {err}"),
        ),
    }
}

async fn get_events(
    State(state): State<AppState>,
    Query(query): Query<EventsQuery>,
) -> impl IntoResponse {
    let limit = query.limit.unwrap_or(100).min(1000);
    let conn = match state.db.lock() {
        Ok(guard) => guard,
        Err(err) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": format!("db lock poisoned: {err}") })),
            );
        }
    };
    let sql = "SELECT timestamp, agent_id, request_id, correlation_id, layer, verdict, action, payload
               FROM trust_events
               ORDER BY timestamp DESC
               LIMIT ?1";
    match query_events(&conn, sql, params![limit as i64]) {
        Ok(events) => (StatusCode::OK, Json(Value::Array(events))),
        Err(err) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": format!("query failed: {err}") })),
        ),
    }
}

async fn get_correlation(
    State(state): State<AppState>,
    Path(correlation_id): Path<String>,
) -> impl IntoResponse {
    let conn = match state.db.lock() {
        Ok(guard) => guard,
        Err(err) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": format!("db lock poisoned: {err}") })),
            );
        }
    };
    let sql = "SELECT timestamp, agent_id, request_id, correlation_id, layer, verdict, action, payload
               FROM trust_events
               WHERE correlation_id = ?1
               ORDER BY timestamp ASC";
    match query_events(&conn, sql, params![correlation_id]) {
        Ok(events) => (StatusCode::OK, Json(Value::Array(events))),
        Err(err) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": format!("query failed: {err}") })),
        ),
    }
}

async fn get_metrics(State(state): State<AppState>) -> impl IntoResponse {
    let conn = match state.db.lock() {
        Ok(guard) => guard,
        Err(err) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": format!("db lock poisoned: {err}") })),
            );
        }
    };

    let by_layer = match aggregate_counts(&conn, "layer") {
        Ok(map) => map,
        Err(err) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": format!("metrics layer failed: {err}") })),
            );
        }
    };
    let by_verdict = match aggregate_counts(&conn, "verdict") {
        Ok(map) => map,
        Err(err) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": format!("metrics verdict failed: {err}") })),
            );
        }
    };
    (
        StatusCode::OK,
        Json(json!({
            "counts_by_layer": by_layer,
            "counts_by_verdict": by_verdict
        })),
    )
}

fn query_events<P>(conn: &Connection, sql: &str, params: P) -> Result<Vec<Value>, rusqlite::Error>
where
    P: rusqlite::Params,
{
    let mut stmt = conn.prepare(sql)?;
    let rows = stmt.query_map(params, |row| {
        let payload_text: String = row.get(7)?;
        let payload = match serde_json::from_str::<Value>(&payload_text) {
            Ok(value) => value,
            Err(_) => Value::Null,
        };
        Ok(json!({
            "timestamp": row.get::<_, String>(0)?,
            "agent_id": row.get::<_, String>(1)?,
            "request_id": row.get::<_, Option<String>>(2)?,
            "correlation_id": row.get::<_, String>(3)?,
            "layer": row.get::<_, String>(4)?,
            "verdict": row.get::<_, String>(5)?,
            "action": row.get::<_, String>(6)?,
            "payload": payload
        }))
    })?;
    rows.collect()
}

fn aggregate_counts(conn: &Connection, field: &str) -> Result<Value, rusqlite::Error> {
    let sql = format!(
        "SELECT {field}, COUNT(*) as count FROM trust_events GROUP BY {field} ORDER BY count DESC"
    );
    let mut stmt = conn.prepare(&sql)?;
    let rows = stmt.query_map([], |row| {
        let key: String = row.get(0)?;
        let count: i64 = row.get(1)?;
        Ok((key, count))
    })?;

    let mut obj = serde_json::Map::new();
    for row in rows {
        let (key, count) = row?;
        obj.insert(key, json!(count));
    }
    Ok(Value::Object(obj))
}

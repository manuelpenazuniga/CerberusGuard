use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Layer {
    LobsterTrap,
    PennyPrompt,
    ClawCrate,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Verdict {
    Allow,
    Deny,
    Log,
    HumanReview,
    RateLimit,
    Quarantine,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct TrustEvent {
    pub timestamp: DateTime<Utc>,
    pub agent_id: String,
    pub request_id: Option<String>,
    pub correlation_id: String,
    pub layer: Layer,
    pub verdict: Verdict,
    pub action: String,
    pub payload: serde_json::Value,
}

#[cfg(test)]
mod tests {
    use super::{Layer, TrustEvent, Verdict};
    use chrono::Utc;
    use serde_json::json;

    #[test]
    fn serializes_expected_layer_and_verdict_shape() {
        let event = TrustEvent {
            timestamp: Utc::now(),
            agent_id: "agent-1".to_string(),
            request_id: Some("req-1".to_string()),
            correlation_id: "corr-1".to_string(),
            layer: Layer::LobsterTrap,
            verdict: Verdict::Deny,
            action: "prompt_blocked".to_string(),
            payload: json!({"rule_id":"pii"}),
        };

        let serialized = serde_json::to_string(&event).expect("serialize event");
        assert!(serialized.contains("\"layer\":\"lobster_trap\""));
        assert!(serialized.contains("\"verdict\":\"DENY\""));
    }

    #[test]
    fn round_trips_through_json() {
        let event = TrustEvent {
            timestamp: Utc::now(),
            agent_id: "agent-2".to_string(),
            request_id: None,
            correlation_id: "corr-2".to_string(),
            layer: Layer::PennyPrompt,
            verdict: Verdict::Allow,
            action: "budget_check".to_string(),
            payload: json!({"remaining_usd": 10.5}),
        };

        let serialized = serde_json::to_string(&event).expect("serialize event");
        let decoded: TrustEvent = serde_json::from_str(&serialized).expect("decode event");

        assert_eq!(decoded.agent_id, event.agent_id);
        assert_eq!(decoded.request_id, event.request_id);
        assert_eq!(decoded.correlation_id, event.correlation_id);
        assert_eq!(decoded.layer, event.layer);
        assert_eq!(decoded.verdict, event.verdict);
        assert_eq!(decoded.action, event.action);
        assert_eq!(decoded.payload, event.payload);
    }
}

// SPDX-License-Identifier: Apache-2.0
// Vibetram original offline status-only integration/tests; see MODIFICATIONS.json.
//! Same required wire fields/types; no owner path or personal hostname.
pub(super) fn wire(envelope:&super::protocol::ServerEnvelope)->serde_json::Result<String>{
    let mut value=serde_json::to_value(envelope)?;
    if let Some(result)=value.get_mut("message").and_then(|m|m.get_mut("result")).and_then(|r|r.as_object_mut()) {
        if result.contains_key("codexHome") {
            result.insert("codexHome".into(),serde_json::json!("/"));
            result.insert("userAgent".into(),serde_json::json!("Codex Status Pilot"));
        }
        if result.contains_key("serverName") {result.insert("serverName".into(),serde_json::json!("Android Status Pilot"));}
    }
    serde_json::to_string(&value)
}

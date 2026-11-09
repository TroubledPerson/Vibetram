// SPDX-License-Identifier: Apache-2.0
// Vibetram original offline status-only integration/tests; see MODIFICATIONS.json.
use super::*;
use super::super::protocol::ServerEvent;
use crate::OutgoingMessage;
use codex_app_server_protocol::{ConfigWarningNotification, ServerNotification, ServerNotificationEnvelope};

fn canary() -> ServerEnvelope {
    ServerEnvelope {
        client_id: ClientId("unit-fixture".into()),
        stream_id: StreamId("unit-stream".into()),
        seq_id: 1,
        event: ServerEvent::ServerMessage {
            message: Box::new(OutgoingMessage::AppServerNotification(ServerNotificationEnvelope {
                notification: ServerNotification::ConfigWarning(ConfigWarningNotification {
                    summary: "SYNTHETIC_OUTBOUND_CANARY".into(),
                    details: None,
                    path: None,
                    range: None,
                }),
                emitted_at_ms: Some(1234),
            })),
        },
    }
}

#[test]
fn buffer_ack_accounting_is_exact_and_repeated_ack_does_not_underflow() {
    let (mut buffer, used) = BoundedOutboundBuffer::new();
    let frame = canary();
    buffer.insert(&frame);
    assert_eq!(*used.borrow(), 1);
    buffer.ack(&frame.client_id, &StreamId("wrong-stream".into()), 1, None);
    assert_eq!(*used.borrow(), 1);
    buffer.ack(&frame.client_id, &frame.stream_id, 1, None);
    buffer.ack(&frame.client_id, &frame.stream_id, 1, None);
    assert_eq!(*used.borrow(), 0);
    assert_eq!(buffer.server_envelopes().count(), 0);
}

// Diagnostic boundary: this primitive preserves arbitrary notification content.
// This does not exercise the socket writer or establish live transmission.
#[test]
fn generic_buffer_and_serializer_preserve_unfiltered_synthetic_canary() {
    let (mut buffer, used) = BoundedOutboundBuffer::new();
    buffer.insert(&canary());
    let serialized = serde_json::to_string(buffer.server_envelopes().next().expect("frame"))
        .expect("serialize");
    assert!(serialized.contains("SYNTHETIC_OUTBOUND_CANARY"));
    assert_eq!(*used.borrow(), 1);
}
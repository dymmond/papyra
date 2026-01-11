# Redis Streams Consumer Groups in Papyra

## Introduction

Redis Streams provide a powerful data structure for managing real-time data streams.
Consumer groups in Redis Streams enable multiple consumers to cooperatively consume messages
from a stream, ensuring each message is processed by exactly one consumer.

Papyra leverages Redis Streams consumer groups to build scalable, fault-tolerant streaming applications.

This document explains the concepts, motivation, lifecycle, operations, failure scenarios, tuning, metrics,
CLI commands, and best practices for using Redis Streams consumer groups in Papyra.

---

## Concepts

### Redis Streams

A Redis Stream is an append-only data structure that stores messages with IDs and associated fields.
It supports efficient data ingestion and consumption.

### Consumer Groups

A consumer group is a set of consumers that share the responsibility of processing messages from a stream.
Each message is delivered to exactly one consumer within the group.

### Papyra's Use of Consumer Groups

Papyra uses Redis Streams consumer groups to:

- Enable scalable parallel processing.
- Provide message delivery guarantees.
- Track message processing state.
- Handle failures and retries.

---

## Motivation

Using consumer groups in Papyra provides:

- **Scalability:** Multiple consumers can process messages concurrently.
- **Fault Tolerance:** Messages can be re-assigned if a consumer fails.
- **Exactly-Once Processing:** Messages are acknowledged upon successful processing.
- **Load Balancing:** Messages are distributed across consumers.

---

## Mapping to Redis

| Papyra Concept        | Redis Streams Consumer Group Concept    |
|----------------------|-----------------------------------------|
| Stream               | Redis Stream (key)                       |
| Consumer Group       | Redis Consumer Group                     |
| Consumer             | Redis Consumer within the group         |
| Message              | Stream Entry (ID + fields)               |
| Acknowledgment       | XACK command                            |
| Pending Messages     | Pending Entries List (PEL)               |
| Claim Messages       | XCLAIM command                          |

---

## Lifecycle of Consumer Groups in Papyra

1. **Create Stream:** The stream is created or exists in Redis.
2. **Create Consumer Group:** Papyra creates a consumer group on the stream.
3. **Add Consumers:** Consumers join the group and start reading messages.
4. **Read Messages:** Consumers read new messages or claim pending ones.
5. **Process Messages:** Consumers process messages.
6. **Acknowledge Messages:** After processing, messages are acknowledged.
7. **Handle Failures:** Unacknowledged messages are claimed or retried.
8. **Delete Consumer/Group:** When no longer needed, consumers or groups can be deleted.

---

## Reading Messages

### Reading New Messages

Consumers read new messages using the `XREADGROUP` command with the `>` ID,
which delivers only new messages not yet delivered to any consumer.

Example:

```
XREADGROUP GROUP group-name consumer-name COUNT 10 STREAMS mystream >
```

### Reading Pending Messages

Consumers can read their own pending messages or claim pending messages from other consumers.

---

## Acknowledging Messages

After successful processing, consumers acknowledge messages using the `XACK` command to remove them
from the Pending Entries List (PEL).

Example:

```
XACK mystream group-name 1526985058136-0
```

---

## Pending Messages and Claiming

### Pending Entries List (PEL)

Each consumer group maintains a PEL, which tracks messages delivered but not acknowledged.

### Claiming Messages

If a consumer fails or takes too long to process a message, another consumer can claim the message using `XCLAIM`.

Example:

```
XCLAIM mystream group-name new-consumer 60000 1526985058136-0
```

This claims the message if it has been idle for at least 60 seconds.

---

## Examples

### Creating a Consumer Group

```bash
XGROUP CREATE mystream group-name $ MKSTREAM
```

### Reading Messages as a Consumer

```bash
XREADGROUP GROUP group-name consumer1 COUNT 5 STREAMS mystream >
```

### Acknowledging a Message

```bash
XACK mystream group-name 1526985058136-0
```

### Claiming a Pending Message

```bash
XCLAIM mystream group-name consumer2 60000 1526985058136-0
```

---

## Failure Scenarios

- **Consumer Crash:** Messages assigned to the crashed consumer remain pending and can be claimed by others.
- **Message Processing Failure:** Messages can be retried or moved to a dead-letter queue.
- **Network Partitions:** Duplicate deliveries may occur; idempotent processing is recommended.

---

## Tuning

- **Max Pending Messages:** Limit the number of pending messages per consumer to avoid overload.
- **Idle Time for Claiming:** Adjust the idle time threshold to control when messages are eligible for claiming.
- **Batch Size:** Tune the number of messages read per call to balance latency and throughput.
- **Stream Trimming:** Use `XTRIM` to limit stream length and control memory usage.

---

## Metrics

- **Pending Messages Count:** Number of messages pending acknowledgment.
- **Consumers Count:** Number of active consumers in a group.
- **Stream Length:** Total messages in the stream.
- **Processing Latency:** Time between message creation and acknowledgment.
- **Claimed Messages:** Number of messages claimed due to failure or timeout.

---

## CLI Commands

- `XGROUP CREATE` - Create a consumer group.
- `XREADGROUP` - Read messages from a consumer group.
- `XACK` - Acknowledge message processing.
- `XPENDING` - View pending messages for a group.
- `XCLAIM` - Claim pending messages.
- `XDEL` - Delete messages from the stream.
- `XINFO GROUPS` - Get info about consumer groups.
- `XINFO CONSUMERS` - Get info about consumers.

---

## Best Practices

- **Use Idempotent Processing:** Ensure message processing can safely be retried.
- **Monitor Pending Messages:** Alert when pending messages grow unexpectedly.
- **Handle Claims Gracefully:** Implement logic to avoid duplicate processing.
- **Use Dead-Letter Queues:** For messages that repeatedly fail processing.
- **Scale Consumers Appropriately:** Match consumer count to workload.
- **Trim Streams Regularly:** To avoid unbounded memory growth.
- **Use Consumer Names Meaningfully:** For easier debugging and monitoring.

---

## Summary

Redis Streams consumer groups provide a robust foundation for building scalable and fault-tolerant streaming
applications.

Papyra leverages these features to enable efficient message processing with strong delivery guarantees.

Understanding the lifecycle, commands, failure modes, and tuning options is essential for building reliable
applications using Redis Streams consumer groups in Papyra.

# The multiplayer protocol

What two Dosidicus instances say to each other on a LAN, in what order, and
what every message contains. Field names, constants and limits are taken from
the code (encounter protocol **4**); every JSON example was produced by the
code's own `to_payload()` methods, or copied from the dict literal that builds
the message where there is no class.

Related reading: the plugin's [README](../README) (rules, consent modes,
running two instances), [rocks.md](rocks.md) (throws and impacts),
[fights.md](fights.md), [reproduction.md](reproduction.md) and
[social-network.md](social-network.md) (the `aquarium_nearby` sense).

---

## 1. Overview

### 1.1 Purpose

A squid can leave its own tank and visit another player's tank on the same
LAN. It goes when its own network decides to (see 5.2), the other tank's host
agrees to let it in, and for the length of the visit the two squid share one
tank: each can see the other, compete for objects, throw things at the other,
fight or mate, and each remembers the individual afterwards.

### 1.2 The remote mind

> A visiting squid's brain stays on its own machine. The host runs its body,
> not its mind.

The visitor's network, weights, memories, drives and learning keep running at
home. The host tank holds only a body (`HostBody`/`VisitorActor`) with a
position, a facing and whatever it is carrying. Each round trip:

```
   HOST TANK                                   VISITOR'S HOME INSTANCE
   ---------                                   -----------------------
   what the visitor can see  --perception_frame->  its own sensors
                                                   its own propagation
                                                   decision_engine.select_action
   carry it out, resolve it  <--action_intent----  the winning action neuron
   what actually happened    --consequence------>  its own drives and memory
```

Every running instance plays both roles at once: it hosts other people's squid
(`MultiplayerPlugin.host_body`) and is the home of its own squid when that one
is away (`MultiplayerPlugin.visitor_mind`). It subscribes to both directions of
every remote-mind message.

### 1.3 Trust model

- **Nothing from the wire is trusted.** Every remote-mind message is rebuilt
  by a `from_payload()` classmethod that validates types, clamps every number
  and truncates every string; anything that does not parse raises
  `ProtocolError` and is dropped at the handler. Identities are re-parsed by
  `SquidIdentity.from_payload`, so a malformed uuid can never become a memory
  key. Object references are opaque ids the host issued, never filenames or
  paths.
- **Private state never crosses in the remote-mind messages.** Perception,
  intents and consequences carry only what the other party could observe or
  what physically happened. A payload containing any key in `FORBIDDEN_KEYS`
  (weights, neuron state, drives, memories, ...), at any depth, is refused
  outright (section 7). The two presence broadcasts, `object_sync` and
  `heartbeat`, predate this rule; they carry no drives (7.3).
- **The only weights that ever cross are a gamete**: after a mating, a random
  half of the visitor's synapses between the neurons every newborn has, sent
  to the host for the egg (4.8).
- **There is no authentication or encryption.** Everything is UDP multicast:
  every instance on the group receives every datagram, and "addressed" in this
  document means a field that receivers filter on, not a private channel. A
  visit id works as an unauthenticated token (7.6). The design target is a
  trusted LAN.

### 1.4 Node id versus squid uuid

| | Node id | Squid uuid |
|---|---|---|
| Names | one running game instance, i.e. the tank and its socket | one squid, for its whole life |
| Format | `squid_` + 6 lowercase hex characters, e.g. `squid_4f9a2c` (`uuid4().hex[:6]`, made in `MultiplayerPlugin.setup`) | a standard uuid, e.g. `a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d` (`Squid.uuid`) |
| Lifetime | random, new every time the plugin sets up; never saved | created at birth, saved and restored with the squid |
| On the wire | the envelope's `node_id`; also repeated inside some payloads; the `to` field of `squid_exit` | `SquidIdentity.uuid`; `peer_uuid` fields; the first 8 characters of each side are in every `visit_id` |
| Used for | transport: self-filtering, de-duplication, peer discovery, addressing a host, drawing a remote squid | everything social: consent, encounter memory (`peer:<uuid>`), recognition, matings, fights, hits |

A restarted game keeps its squid's uuid but gets a new node id, which is why
nothing a squid remembers is filed under a node id. `NetworkNode` itself falls back to
`squid_` + 8 hex characters only if it is constructed without an id, which the
plugin never does.

### 1.5 Versioning

- `ENCOUNTER_PROTOCOL_VERSION = 4` (`identity.py`). It travels inside every
  `SquidIdentity` as `protocol`, not in the envelope. History from the
  source: **2** other squid are seen through vision (`squid_in_view`);
  **3** frames report `in_fight` and intents carry `aggression`, `defence` and
  `fitness`; **4** idempotent rock impacts (`throw_id`) and neural visitor
  throws.
- A host checks the identity in each `squid_exit`: if
  `identity.protocol != ENCOUNTER_PROTOCOL_VERSION` it refuses with reason
  `protocol_mismatch` (`SquidIdentity.is_compatible`,
  `ConsentPolicy.evaluate`). There is no negotiation: peers must run the same
  version.
- The check is one-way. The visitor does not check the protocol in the
  resident identity that frames carry, and an identity that omits `protocol`
  is parsed as the current version.
- Within a version, readers default fields that are missing (an intent
  without `practice` is a novice thrower, `practice = 0`) and ignore keys
  they do not know, except a `gamete`, which refuses any extra top-level key.
- The plugin's own version (`PLUGIN_VERSION = "1.2.0"`) is never sent.

---

## 2. Transport

### 2.1 Socket

| Setting | Value | Source |
|---|---|---|
| Protocol | IPv4 UDP multicast | `mp_network_node.py` |
| Group : port | `224.3.29.71 : 10000` (`MULTICAST_GROUP`, `MULTICAST_PORT`) | `mp_constants.py` |
| TTL | `IP_MULTICAST_TTL = 2` (can cross one router) | `NetworkNode.initialize_socket_structure` |
| Loopback | `IP_MULTICAST_LOOP = 1`, so two instances on one machine hear each other | same |
| Bind | `('', 10000)` with `SO_REUSEADDR` (and `SO_REUSEPORT` where available), so several instances share the port | same |
| Membership | joined on every usable local IPv4 address (ranked 192.168 > 172.16-31 > 10 > other; loopback and link-local skipped), then once more on `0.0.0.0` | `_get_all_send_ips` |
| Sending | each datagram is sent once **per interface** in that list, setting `IP_MULTICAST_IF` before each `sendto` | `send_message` |
| Receiving | a daemon listener thread calls `recvfrom(65535)` (`RECEIVE_BUFFER_SIZE`) with a 0.1 s timeout and puts raw bytes on a queue (max 500 entries; when full, the oldest entry is discarded) | `_listen_for_multicast` |
| Draining | a 50 ms `QTimer` on the Qt thread decodes the queue and dispatches handlers | `_process_network_node_queue` |
| Reconnect | a dead socket or listener is rebuilt, at most every 5 s (`connection_retry_interval`) | `try_reconnect`, `watchdog_check` |
| Override | a `MULTICAST_BIND_IP` constant, if added to `mp_constants.py`, replaces the auto-detected local IP (shown in the UI and sent as `object_sync.node_info.ip`); it does not change the interfaces used | `_get_local_ip` |

Because every datagram goes out on several interfaces and the receiver is
joined on several, one logical message usually arrives two or three times on
the same machine; the de-duplication in 2.6 removes the copies.

### 2.2 Discovery

There is no handshake and no peer list on the wire. A peer exists when its
`heartbeat` is heard.

- `heartbeat` is sent from the world-sync tick when more than 8 s have passed
  since the last one (so roughly every 8-9 s), and once on demand from the
  menu's *Refresh connections*.
- Each heartbeat received stores `_peers_last_heard[payload.node_id] = now`.
- An aquarium counts as nearby while some peer was heard within
  `HEARD_WITHIN = 30.0` s (`src/venturing.py`). Every sync tick (0.5 s) the
  plugin writes the percept `aquarium_heard` (100 or 0) into the brain; the
  grown sense `aquarium_nearby` reads it (`SOCIAL_SENSORS` in
  `src/brain_constants.py`).
- A departing squid addresses the peer heard **most recently** within that
  window (`visit_destination`).
- `NetworkNode.known_nodes` maps `node_id -> (sender IP, last-seen time, last
  payload)` and is refreshed by **every** accepted message, not only
  heartbeats. It feeds the status widget and dashboard; it is not used to
  choose a destination.
- Nobody acts on `player_leave` (3.1); a peer that goes quiet simply ages out
  of the 30 s window.

### 2.3 Envelope

Every message is one JSON object, one per datagram:

```json
{
  "node_id": "squid_4f9a2c",
  "timestamp": 1760958000.123456,
  "type": "action_intent",
  "payload": { "visit_id": "3f2a9c1e-a1b2c3d4-19a0146abfb", "...": "..." }
}
```

| Field | Type | Meaning |
|---|---|---|
| `node_id` | string | The sender's node id (1.4). Receivers drop messages carrying their own id. |
| `timestamp` | number | The sender's `time.time()` (seconds since the epoch, float) at sending. Informational: never compared with the receiver's clock, and not used for de-duplication (2.6). |
| `type` | string | Message type (section 3). Selects the handler `on_network_<type>`. |
| `payload` | object | The message body (section 4). |

`NetworkNode.send_message_batch` defines a second shape
(`{"node_id", "timestamp", "batch": true, "messages": [{"type", "payload"}, ...]}`),
but nothing calls it and a receiver discards it because it has no `type`.

### 2.4 Encoding and compression

- **Serialisation**: `json.dumps(envelope).encode('utf-8')`, Python's
  defaults (tuples become arrays; `NaN`/`Infinity` are not rejected).
- **Compression**: every message is compressed with `zlib.compress` at zlib's
  default level (`NetworkUtilities.compress_message`). `use_compression` is
  `True` and nothing turns it off; there is no size threshold. A compressed
  datagram therefore starts with the zlib header bytes `78 9c`.
- **Detection on receipt**: there is no flag. The receiver tries
  `zlib.decompress` on every datagram; if that raises `zlib.error` it parses
  the bytes as plain UTF-8 JSON instead
  (`NetworkUtilities.decompress_message`). There is no cap on the
  decompressed size.
- If serialisation fails, `compress_message` sends a small uncompressed
  `{"error": ..., "details": ..., "original_type": ...}` object instead. It has
  no `node_id`, so every receiver drops it.

Sizes of the examples in section 4, as sent:

| Message | JSON bytes | After zlib |
|---|---|---|
| `heartbeat` | 169 | 126 |
| `visit_response` | 191 | 150 |
| `squid_exit` | 443 | 261 |
| `object_sync` | 673 | 389 |
| `perception_frame` (2 items) | 669 | 386 |
| `action_intent` | 368 | 228 |
| `consequence` (`fight_resolved`) | 352 | 234 |
| `gamete` (26 genes: half of a default newborn brain's 52 synapses) | 984 | 335 |
| `gamete` (85 genes: every pair of newborn neurons wired one way) | 3022 | 806 |
| `gamete` (171 genes: every ordered pair wired, the most a sender can produce) | 5924 | 1374 |

### 2.5 Size limits

- `MAX_PACKET_SIZE = 1472`: a 1500-byte Ethernet MTU less 20 bytes of IPv4
  header and 8 of UDP, so a datagram up to this size is never fragmented.
- The sender only **warns** when a compressed message is larger; it still
  sends it, and the network may fragment it.
- The receiver reads a whole datagram (`RECEIVE_BUFFER_SIZE = 65535`), so a
  larger message arrives intact if the network delivers it. (It used to read
  only 1472 bytes: on Linux and macOS the rest was cut off and the packet
  dropped, on Windows the call failed and the listener reconnected.)
- No received message may decompress to more than `MAX_MESSAGE_BYTES`
  (256 KiB); a datagram that would is refused rather than inflated.
- The largest message, a gamete, stays under 1472 bytes anyway (table above).
- Field-level limits (string lengths, list lengths, numeric ranges) are listed
  with each message in section 4 and summarised in 7.4.

### 2.6 Receiving: what is dropped, in order

1. **Listener queue full** (500 waiting datagrams): the oldest is discarded.
2. **Undecodable** (neither zlib+JSON nor JSON, or not UTF-8): dropped.
3. **Not a JSON object, or no `node_id`**: dropped.
4. **Own message** (`node_id` equals this node's id): dropped
   (`packets_dropped_self`).
5. **Duplicate**: the key `(node_id, digest of the datagram's bytes)` was
   seen in the last 10 s (`_dedup_ttl`): dropped
   (`packets_dropped_duplicate`). This removes the per-interface copies, which
   are byte for byte the same datagram. (Keyed on `(node_id, timestamp)`
   instead, different messages sent back to back on a coarse clock - a frame
   and its consequences - were dropped as copies.)
6. Otherwise `known_nodes` is updated and the message is passed on.
7. **No `type`**: dropped.
8. **Dispatch**: the hook `on_network_<type>` is triggered on the plugin
   manager with `node=<NetworkNode>, message=<envelope>, addr=(ip, port)`. A
   type with no registered hook only produces a warning in the log and goes
   no further.
9. **Handler checks**: each handler validates its own payload (table below).
   Rejections are logged and the message is ignored; nothing is sent back.

`packet_validator.PacketValidator` describes a stricter gate (required
envelope fields, `node_id` matching `^[a-zA-Z0-9_-]+$`, a timestamp within
3600 s of the receiver's clock, an allow-list of types and per-type structure
checks), **but nothing in the receive path calls it**; only the tests do. The
checks that actually run are these:

| Type | Checked by the handler |
|---|---|
| `squid_exit` | `payload.payload` and its `node_id` must exist; own exits ignored; `to`, if present, must be this node's id; identity re-parsed (`None` means refusal `unusable_identity`) |
| `visit_response` | the sender must be the node this squid addressed; `payload.peer_uuid` must equal this squid's uuid - or, for a refusal, `payload.to` its node id |
| `perception_frame` | the sender must be the node this squid asked to visit; `PerceptionFrame.from_payload`, then `RemotePerception.accept` (squid is away, visit id, `seq`) |
| `action_intent` | `ActionIntent.from_payload`; `visit_id` must name a current visitor, and the sender must be the node it arrived from; then `HostBody.apply_intent` (`seq`, lease) |
| `consequence` | the sender must be this squid's host; `Consequence.from_payload`; `visit_id` must equal this squid's current visit; `hit`/`rock_thrown` need a `throw_id` and are taken once |
| `visit_end` | `VisitEnd.from_payload`; this squid's own visit first (from its host), otherwise a visitor hosted here (from its node) |
| `gamete` | `Gamete.from_payload`; `visit_id` of a current visitor, from the node it arrived from; the resident's recorded mating and mate must match |
| `heartbeat` | `payload.node_id` must be present and not this node |
| `object_sync` | sender taken from `payload.node_info.id` or `payload.squid.node_id`; only updates a remote squid already drawn here |

---

## 3. Message catalogue

Everything is multicast to the whole group. The **Addressing** column says how
the intended receiver recognises a message as its own.

### 3.1 Messages in use

| Type | Sender → receiver | Addressing | Sent when | Handler |
|---|---|---|---|---|
| `heartbeat` | every instance → all | broadcast | about every 8-9 s (from `sync_game_state`); on *Refresh connections* | `handle_heartbeat` |
| `object_sync` | every instance → all | broadcast; used only by a host that is drawing that sender's squid | every `SYNC_INTERVAL` (1.0 s) | `handle_object_sync` |
| `player_leave` | instance → all | broadcast | in `disable()` and again in `cleanup()`, so twice on disabling | none registered |
| `squid_exit` | visitor's home → one host | `payload.payload.to` = the host's node id | the squid reaches the left or right side while venturing (5.2); repeated every 3 s until it is answered | `handle_squid_exit_message` |
| `visit_response` | host → visitor's home | `payload.peer_uuid` = the visitor's squid uuid; accepted only from the node addressed | once per `squid_exit` the host takes | `handle_visit_response` |
| `perception_frame` | host → visitor's home | `payload.visit_id` | immediately on admission, then every round trip, one per visitor | `handle_perception_frame` → `VisitorMind.on_perception_frame` |
| `action_intent` | visitor's home → host | `payload.visit_id` | every round trip while linked and an action clears its threshold; plus one `act_ink` intent each time ink starts firing | `handle_action_intent` → `HostBody.apply_intent` |
| `consequence` | host → visitor's home | `payload.visit_id` | in each round trip, after the frame, one per queued event | `handle_consequence` → `VisitorMind.on_consequence` |
| `visit_end` | either side | `payload.visit_id` | the visit ends (5.8) | `handle_visit_end` |
| `gamete` | visitor's home → host | `payload.visit_id` and `payload.mating_id` | each time a `mated` consequence arrives - including a mating retold on a later visit (4.8) | `handle_gamete` |

### 3.2 Legacy and unused types

| Type | Status |
|---|---|
| `squid_return` | Sent only by the dead autopilot (`RemoteSquidController`, never constructed). **Not listened for**: its handler moved this node's squid and rewrote its drives from the received `activity_summary`. |
| `squid_move` | Nothing sends it. Not listened for. |
| `rock_throw` | `throw_rock_network` has no caller. Not listened for: its handler loaded an image from a path the peer chose. |
| `state_update` | Nothing sends it. `handle_state_update` only logs. |
| `visit_request`, `squid_action`, `player_join`, `new_squid_arrival` | Named in `PacketValidator`'s allow-list only. Never sent, no handler. `squid_exit` plays the part of `visit_request`. |

### 3.3 Local hooks that produce messages

These are not network messages but are registered beside them:

| Hook | Raised by | Effect on the wire |
|---|---|---|
| `on_rock_hit` | `TamagotchiLogic.on_rock_hit`, when a thrown rock or poop strikes a squid in this tank | queues `consequence` `hit` for each visitor involved (`handle_rock_hit`) |
| `on_squid_died` | the core, when this tank's resident dies | `visit_end` `ejected` to every visitor; `visit_end` `departed` if the resident was itself away (`handle_resident_died`) |

---

## 4. Message shapes

Coordinates are scene pixels in the tank named, with `y` growing downwards.
"Clamped" means out-of-range values are forced into range, not rejected;
non-numbers become the default.

### 4.1 `SquidIdentity` (embedded)

Carried in `squid_exit`, `object_sync` and every `perception_frame`.

```json
{"uuid": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d", "name": "Inky", "personality": "timid", "protocol": 4}
```

| Field | Type | Limits on receipt | Meaning |
|---|---|---|---|
| `uuid` | string | must match `^[0-9a-fA-F-]{32,36}$` and parse as a uuid, else the whole identity is rejected; rewritten to canonical lower-case dashed form | the squid (`Squid.uuid`) |
| `name` | string | characters other than letters, digits, `_`, space, `-`, `'`, `.` removed; at most 32; empty becomes `"Squid"` | display name |
| `personality` | string | cleaned like `name`, then lower-cased; missing becomes `"squid"` | the personality label, display only |
| `protocol` | integer | must convert with `int()`, else the identity is rejected; missing means the current version | encounter protocol version (1.5) |

### 4.2 `squid_exit`

Visitor's home → the host it is addressing. The exit data is nested one level
down, under `payload.payload`.

```json
{
  "payload": {
    "node_id": "squid_4f9a2c",
    "direction": "right",
    "position": {"x": 1224.0, "y": 388.5},
    "color": [171, 100, 233],
    "squid_width": 56,
    "squid_height": 56,
    "window_width": 1280,
    "window_height": 900,
    "identity": {"uuid": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d", "name": "Inky", "personality": "timid", "protocol": 4},
    "to": "squid_b71e03"
  }
}
```

| Field (`payload.payload.*`) | Type | Values | Meaning |
|---|---|---|---|
| `node_id` | string | node id | the sender; required, or the host ignores the message |
| `direction` | string | `left` or `right` | the side it left by (it never leaves by the surface or the sand). The host draws an exit arrow and brings the body in at the opposite side. |
| `position` | object | `{x, y}` | the squid's top-left corner in its own tank when it left |
| `color` | array | `[r, g, b]`, each 100-255 | from an MD5 of the node id (`Squid._get_squid_color`) |
| `squid_width`, `squid_height` | number | px | body size, for drawing and the entry position |
| `window_width`, `window_height` | number | px | the visitor's own tank size |
| `identity` | object | 4.1, or `{}` if the squid has no uuid | who is asking; the host's consent decision rests on it |
| `to` | string | node id | the one host asked (`address_exit`). Any other host ignores the message. Without `to`, every host that hears it may answer. |

### 4.3 `visit_response`

Host → visitor's home. `ConsentDecision.to_payload()`.

```json
{"accepted": true, "reason": "accepted", "peer_uuid": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
 "to": "squid_4e51c5"}
```

| Field | Type | Values | Meaning |
|---|---|---|---|
| `accepted` | boolean | | admitted or not |
| `reason` | string | see below | why |
| `peer_uuid` | string | squid uuid, or `""` when the identity was unusable | the squid the answer is for |
| `to` | string | node id | the node that asked; what a refusal with no `peer_uuid` is matched on |

| `reason` | Constant | When |
|---|---|---|
| `accepted` | `REASON_ACCEPTED` | admitted |
| `tank_closed` | `REASON_CLOSED` | the resident is dead (its tank is waiting for the egg), or the policy is in `closed` mode |
| `unusable_identity` | `REASON_BAD_IDENTITY` | no identity, or one that would not parse |
| `protocol_mismatch` | `REASON_INCOMPATIBLE` | `identity.protocol` is not this build's version |
| `denied` | `REASON_DENIED` | the uuid is on the block list |
| `not_on_allow_list` | `REASON_UNKNOWN_PEER` | `known` mode and the uuid is not on the allow list |
| `tank_full` | `REASON_AT_CAPACITY` | already `max_visitors` (3) visitors |

A dead resident is checked first. After that `ConsentPolicy.evaluate` checks,
in order: identity, protocol, block list, `closed` mode, allow list
(`known` mode), capacity. The plugin builds its `ConsentPolicy` in `open` mode
with `max_visitors = 3`, and nothing currently changes the mode or the lists.

### 4.4 `perception_frame`

Host → visitor's home. What the visiting squid can observe from where its body
is. `PerceptionFrame.to_payload()`.

```json
{
  "visit_id": "3f2a9c1e-a1b2c3d4-19a0146abfb",
  "seq": 42,
  "sent_at": 1760958000.123456,
  "x": 312.5,
  "y": 401.25,
  "tank": [1280.0, 900.0],
  "facing": "left",
  "sensors": {
    "can_see_food": 100.0,
    "plant_proximity": 37.5,
    "external_stimulus": 24.0,
    "squid_in_view": 100.0,
    "squid_proximity": 61.3,
    "in_fight": 0.0
  },
  "resident": {"uuid": "3f2a9c1e-7b4d-4e8a-9c21-5d6f0a1b2c3d", "name": "Manuel", "personality": "adventurous", "protocol": 4},
  "items": [
    {"id": "item0", "dx": -120.4, "dy": 35.0, "contested": true},
    {"id": "item3", "dx": 210.0, "dy": -80.5, "contested": false}
  ]
}
```

| Field | Type | Limits on receipt | Meaning |
|---|---|---|---|
| `visit_id` | string | required, non-empty; trimmed, at most 64 | the visit (5.5) |
| `seq` | integer | clamped 0 to 10^12 | the host's frame counter. One counter per host process, shared by all its visitors, so a visitor sees increasing but not consecutive numbers. |
| `sent_at` | number | clamped 0 to 10^12 | host clock at sending |
| `x`, `y` | number | clamped ±10^5; sent rounded to 2 dp | the body's position in the host tank |
| `tank` | array | `[width, height]`, each clamped 1 to 10^5; default `[1280, 900]` | host tank size |
| `facing` | string | `left`, `right`, `up`, `down`; anything else becomes `right` | which way the body faces |
| `sensors` | object | required, else the frame is rejected; only the six names below are kept, each clamped 0-100; sent rounded to 2 dp | observable sensor values |
| `resident` | object or null | 4.1, re-parsed | who lives in this tank; `null` if the host has no squid |
| `items` | array | at most 8 entries; entries whose `id` fails the id rule are skipped | rocks within sight |
| `items[].id` | string | trimmed, at most 40, only letters, digits, `-`, `_` | opaque, host-issued (`item<n>`); meaningful only to the host that issued it |
| `items[].dx`, `items[].dy` | number | clamped ±10^5; sent rounded to 1 dp | the item's centre relative to the body |
| `items[].contested` | boolean | | the item is nearer the resident than the visitor |

The sensors (`OBSERVABLE_SENSORS`, computed by `HostBody._observable_sensors`):

| Sensor | Range | Host computes |
|---|---|---|
| `can_see_food` | 0 or 100 | 100 when food is within `SIGHT_RANGE` (400 px) |
| `plant_proximity` | 0-100 | `100 - distance_to_nearest_plant / 300 * 100` |
| `external_stimulus` | 0-60 | 12 per food item in the tank |
| `squid_in_view` | 0 or 100 | 100 when the resident is in the body's view cone (72°, `src/vision_cone.py`) and not itself away |
| `squid_proximity` | 0-100 | `100 - distance_to_resident / 1000 * 100` (`vision_cone.proximity`) |
| `in_fight` | 0 or 100 | 100 while the body is in a fight animation (`body_busy_until`) |

The first three drive the visitor's built-in sensors of the same name while it
is away (`REMOTE_DRIVEN_SENSORS`); the last three are written into its brain
as percepts (`perceive`), which reach its network through the social senses
and neurons it grows.

### 4.5 `action_intent`

Visitor's home → host. One decision of the visitor's own network, as a lease on
its body. `ActionIntent.to_payload()`.

```json
{
  "visit_id": "3f2a9c1e-a1b2c3d4-19a0146abfb",
  "seq": 17,
  "sent_at": 1760958000.123456,
  "action": "act_play",
  "activation": 72.4,
  "confidence": 0.631,
  "heading": "",
  "target_id": "item0",
  "lease": 1.5,
  "aggression": 55.3,
  "defence": 40.0,
  "fitness": 1.823,
  "practice": 37
}
```

| Field | Type | Limits on receipt | Meaning |
|---|---|---|---|
| `visit_id` | string | required, non-empty; trimmed, at most 64 | the visit, as named by the host |
| `seq` | integer | clamped 0 to 10^12 | per visit, starting at 1; `act_ink` intents share the counter |
| `sent_at` | number | clamped 0 to 10^12 | **visitor's** clock at sending. The host converts it to its own clock with the smallest delay it has seen from this visitor (`VisitorActor.clock_offset`), so a constant clock skew cancels; the lease runs from the converted time |
| `action` | string | must be one of the eight action neurons, else the intent is rejected: `act_move`, `act_eat`, `act_flee`, `act_play`, `act_shelter`, `act_rest`, `act_ink`, `act_collapse` | the winning action neuron. There is no other vocabulary. |
| `activation` | number | clamped 0-100; sent to 2 dp | that neuron's activation |
| `confidence` | number | clamped 0-1; sent to 3 dp | from `select_action` |
| `heading` | string | `left`, `right`, `up`, `down`, else `""` | only for `act_move`: towards the nearest item in the frame, otherwise the way it faces |
| `target_id` | string | the item-id rule from 4.4, else `""` | only for `act_play`: the nearest item in the frame |
| `lease` | number | clamped 0 to `INTENT_LEASE` (1.5 s) | how long the intent stays valid; a visitor cannot ask for longer |
| `aggression` | number | clamped 0-100, default 0; sent to 1 dp | its grown `aggression` neuron (0 if it has none). Decides who starts a fight, the visitor's commitment when it attacks, and (with `activation`) how hard its body throws a rock in the host's tank. |
| `defence` | number | clamped 0-100, default 0; sent to 1 dp | how hard it would fight back (`fighting.commitment(attacking=False)`) |
| `fitness` | number | clamped 0-3, default 1.0; sent to 3 dp | `fighting.squid_fitness` of its body at home |
| `practice` | integer | clamped 0 to 100000, default 0 | throws made (rocks and poop) from its own statistics at home. Sets how far its throws stray in the host's tank (`throwing.release`); it does not decide whether it throws. |

What the host does with each action (`HostBody._ACTIONS`): `act_move` steps
18 px (`VISITOR_STEP`) along `heading`; `act_eat` steps towards the nearest
food or eats it within 120 px (`GRASP_RANGE`); `act_flee` steps away from the
resident; `act_shelter` steps towards the nearest plant; `act_play` steps
towards and takes the target rock, swims at the resident if that is nearer and
in view, or throws a rock it is holding; `act_rest` and `act_collapse` only set
what the body is visibly doing. In practice a visitor never sends `act_flee`,
`act_rest` or `act_collapse`: when one of those wins it goes home instead
(5.8).

An **ink intent** is sent outside the competition, once when the visitor's
`act_ink` starts firing. It carries `action: "act_ink"`, its `activation`, and
defaults for everything else (`aggression 0`, `fitness 1.0`, `practice 0`). The
host draws an ink cloud and does **not** store it as `last_intent`, so it never
replaces the fighting values or the movement lease of the previous intent.

### 4.6 `consequence`

Host → visitor's home. Something that happened to the visitor's body, as a
fact. `Consequence.to_payload()`.

```json
{
  "visit_id": "3f2a9c1e-a1b2c3d4-19a0146abfb",
  "kind": "hit",
  "at": 1760958000.123456,
  "detail": {"what": "rock", "speed": 14.3, "throw_id": "84cd611b4f0343e68f59f8d11aa89298", "taken": true, "peer_uuid": "3f2a9c1e-7b4d-4e8a-9c21-5d6f0a1b2c3d"}
}
```

| Field | Type | Limits on receipt | Meaning |
|---|---|---|---|
| `visit_id` | string | required, non-empty; trimmed, at most 64 | the visit |
| `kind` | string | one of the eight kinds below, else rejected | what happened |
| `at` | number | clamped 0 to 10^12 | host clock when it was recorded |
| `detail` | object | a non-object becomes `{}`; at most the first 12 keys, each cut to 32 characters; booleans kept; numbers clamped ±10^6; strings cut to 64; any other value (array, object, null) dropped | the facts, per kind |

| `kind` (constant) | `detail` | Sent when | The visitor |
|---|---|---|---|
| `contest_resolved` (`CONSEQUENCE_CONTEST`) | `{"won": true}` or `{"won": false, "reason": "held"}` | its `act_play` reached a rock: it took it, or the resident was holding it | satisfaction +8 when won, anxiety +6 when lost; noted in the encounter |
| `ate` (`CONSEQUENCE_ATE`) | `{"ok": true}` | its `act_eat` ate food | hunger −12 (if its lifecycle lets it eat) |
| `blocked` (`CONSEQUENCE_BLOCKED`) | `{"what": "eat"}` | the food could not be taken | satisfaction −2 |
| `ejected` (`CONSEQUENCE_EJECTED`) | `{"reason": "link_lost"}` | queued when the host abandons a silent visitor; see 5.9, it is not delivered in practice | recorded only |
| `mated` (`CONSEQUENCE_MATED`) | `{"mating_id": "3f2a9c1e-a1b2c3d4-19a0146abfb-mate"}` | the host recorded a mating with its resident; repeated on 3 round trips (`MATED_ANNOUNCEMENTS`), and 3 more whenever that visitor comes back | files the mating once by id; sends a `gamete` |
| `fight_resolved` (`CONSEQUENCE_FIGHT`) | `{"fight_id", "won", "you_started", "chance", "their_ability", "your_ability"}` | the host resolved a fight; queued 3 times at once, so sent 3 times back to back | applies the fight's consequences once per `fight_id` |
| `hit` (`CONSEQUENCE_HIT`) | `{"what", "speed", "throw_id", "taken", "peer_uuid"}` | a thrown rock or poop struck a squid, and the visitor was the one struck or the one that threw | feels it (`taken: true`) or notes a hit given, once per `throw_id` |
| `rock_thrown` (`CONSEQUENCE_THROWN`) | `{"throw_id", "aimed_at", "driven_by", "drive", "speed", "angle"}` | the visitor's own `act_play` threw the rock it held | remembers its own throw; counts it in its statistics |

`fight_resolved`, from the visitor's side:

| Key | Type | Meaning |
|---|---|---|
| `fight_id` | string | uuid4, one per fight |
| `won` | boolean | whether the **visitor** won |
| `you_started` | boolean | whether the visitor was the attacker |
| `chance` | number | the visitor's chance of winning, 0-1, 3 dp |
| `their_ability` | number | the resident's fighting ability, 1 dp |
| `your_ability` | number | the visitor's fighting ability, 1 dp: `100 × fitness × (0.5 + commitment / 100)`, with commitment its `aggression` if it attacked or `defence` if not, both from its last intent |

`hit`, the facts of an impact:

| Key | Type | Meaning |
|---|---|---|
| `what` | string | `rock` or `poop` (anything else is read as `rock`) |
| `speed` | number | the throw's planned release speed, 1 dp (px per 50 ms step) |
| `throw_id` | string | 32 hex characters, one per physical throw |
| `taken` | boolean | `true`: the visitor was struck. `false`: the visitor's throw struck someone |
| `peer_uuid` | string | the other squid: the thrower when `taken` is true, the one struck when false |

On the receiving end a strike is felt through `throwing.HIT_EFFECTS`: a rock
costs 2 health and startles; poop does no harm but lowers cleanliness by 20 and
happiness by 10 and raises anxiety by 15. The thrower's aim and its reasons are
**never** in a `hit`.

`rock_thrown`, the thrower's own record, sent only about the visitor's own
throw:

| Key | Type | Meaning |
|---|---|---|
| `throw_id` | string | 32 hex characters |
| `aimed_at` | string | the name of the squid it aimed at; omitted when it threw along its gaze |
| `driven_by` | string | `act_play` or `aggression`, whichever was stronger |
| `drive` | number | that neuron's activation, 0-100, 1 dp |
| `speed` | number | intended release speed, 2 dp |
| `angle` | number | aim angle in degrees, 1 dp |

### 4.7 `visit_end`

Either direction. `VisitEnd.to_payload()`.

```json
{"visit_id": "3f2a9c1e-a1b2c3d4-19a0146abfb", "reason": "departed"}
```

| Field | Type | Limits on receipt | Meaning |
|---|---|---|---|
| `visit_id` | string | required, non-empty; trimmed, at most 64 | the visit |
| `reason` | string | `departed`, `ejected` or `link_lost`; anything else becomes `departed` | `departed`: the visitor chose to leave. `ejected`: the host ended it. `link_lost`: neither chose it. |

`VisitEnd` is the one remote-mind message whose `from_payload` does not run
the `FORBIDDEN_KEYS` check; it reads only those two fields.

### 4.8 `gamete`

Visitor's home → host, after a mating. The only time any of a squid's weights
leave its machine. `Gamete.to_payload()`; genes shortened here.

```json
{
  "visit_id": "3f2a9c1e-a1b2c3d4-19a0146abfb",
  "mating_id": "3f2a9c1e-a1b2c3d4-19a0146abfb-mate",
  "genes": {"act_flee->act_collapse": 0.5956, "act_flee->act_ink": 0.9512, "act_flee->act_rest": -0.5588}
}
```

| Field | Type | Limits on receipt | Meaning |
|---|---|---|---|
| (keys) | | exactly `visit_id`, `mating_id`, `genes`; any other key and the gamete is rejected | |
| `visit_id` | string | required, non-empty; trimmed, at most 64 | the visit in which the mating happened |
| `mating_id` | string | must match `^[A-Za-z0-9_-]{1,64}$` | the mating (`mating_id_for(visit_id)` = the visit id's first 58 characters + `-mate`) |
| `genes` | object | `src->dst` keys only; both ends must be newborn neurons and different; values must be numbers (not booleans), clamped to −1..1; only the first 600 (`MAX_GENES`) entries are read; an empty result rejects the gamete | half of the visitor's synapses between the 19 neurons every newborn has (`brain_constants.newborn_neurons()`: the seven drives, `can_see_food`, `is_startled`, `threat_level`, `is_sleeping`, and the eight action neurons), each weight to 4 dp |

The visitor makes one gamete per mating id (`src/inheritance.gamete`, a random
half of those synapses; 26 genes for a default newborn brain, more for a squid
whose learning has wired more of them) and resends the same one each time the
news arrives, until the mating is in its long-term record (written when the
visit's encounter is closed). After that, a later re-announcement is ignored
and no gamete is sent.

The host keeps it only if `visit_id` names a current visitor, its resident's
lifecycle records exactly this `mating_id` with that visitor's uuid as mate,
the egg is still incubating, and nothing has been kept from that parent yet
(`Lifecycle.add_genes`); it then saves.

### 4.9 `heartbeat`

```json
{"node_id": "squid_4f9a2c", "status": "active", "squid_pos": [640.0, 410.5]}
```

| Field | Type | Meaning |
|---|---|---|
| `node_id` | string | the sender's node id. The handler reads this, not the envelope's. |
| `status` | string | `active` (periodic) or `active_refresh_request` (menu refresh) |
| `squid_pos` | array | `[x, y]` of the sender's squid in its own tank; absent on a refresh. Not used by the receiver. |

### 4.10 `object_sync`

The world sync: the sender's own squid as it is in its own tank.

```json
{
  "squid": {
    "x": 640.0, "y": 410.5,
    "direction": "left", "image_direction_key": "left",
    "looking_direction": 3.141592653589793,
    "view_cone_angle": 1.0471975511965976,
    "status": "roaming",
    "carrying_rock": false, "is_sleeping": false,
    "color": [140, 212, 96],
    "node_id": "squid_4f9a2c",
    "view_cone_visible": false,
    "squid_width": 56, "squid_height": 56,
    "identity": {"uuid": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d", "name": "Inky", "personality": "timid", "protocol": 4}
  },
  "objects": [],
  "node_info": {"id": "squid_4f9a2c", "ip": "192.168.1.23"}
}
```

| Field | Type | Meaning |
|---|---|---|
| `squid.x`, `squid.y` | number | position in the sender's tank |
| `squid.direction`, `squid.image_direction_key` | string | movement direction; which sprite to draw |
| `squid.looking_direction` | number | view direction, radians |
| `squid.view_cone_angle` | number | radians (default π/3) |
| `squid.status` | string | what it is visibly doing |
| `squid.carrying_rock`, `squid.is_sleeping`, `squid.view_cone_visible` | boolean | |
| `squid.color` | array | `[r, g, b]`, each 80-220, from a hash of the node id (a different scheme from `squid_exit`'s `color`) |
| `squid.node_id` | string | sender node id |
| `squid.squid_width`, `squid.squid_height` | number | px |
| `squid.identity` | object or null | 4.1 |
| `objects` | array | always empty: `_get_objects_state` deliberately mirrors nothing |
| `node_info` | object | `{"id": node id, "ip": the sender's chosen LAN address}` |

A receiver acts on it only for a squid it is already drawing, which in practice
means a visitor it admitted: it updates that drawing's target position, status
label, sprite and view cone from these fields, and, for a peer whose identity
it learned from a `squid_exit`, reports that uuid to the resident's
`process_squid_detection` (which reacts on first sight only). Messages from any
other peer change nothing. Note that for an admitted visitor `squid.x`/`y` are
the coordinates of its frozen body at home, not of its body in this tank
(`VisitorActor.x`/`y`), yet they are what the drawing's target position is set
from.

### 4.11 `player_leave`

```json
{"node_id": "squid_4f9a2c", "reason": "plugin_disabled"}
```

`reason` is `plugin_disabled` (from `disable()`) or
`plugin_unloaded_or_disabled` (from `cleanup()`). No handler is registered.

### 4.12 Legacy shapes

For completeness; nothing in the current flow sends these (3.2).

| Type | Payload |
|---|---|
| `squid_return` | `{"node_id": <the returning squid's home node id>, "activity_summary": {"food_eaten", "rock_interactions", "rocks_stolen", "time_away", "carried_items_details": [...]}, "return_direction": "left"}` |
| `rock_throw` | `{"rock_data": {"filename", "direction", "initial_pos_x", "initial_pos_y", "scale"}}` |
| `squid_move` | the `squid` object of `object_sync` |
| `state_update` | anything; logged only |

---

## 5. Visit lifecycle

### 5.1 Sequence

```
 VISITOR'S HOME (node squid_4f9a2c)                      HOST (node squid_b71e03)
 ----------------------------------                      ------------------------
       |<------------------ heartbeat, every ~8 s ----------------------|
       |------------------- heartbeat --------------------------------->|
 aquarium_heard = 100 (a peer heard within 30 s)
 aquarium_nearby grows; if its network drives
 it to explore, it swims for the nearer side
       |
 reaches the left/right side
       |--- squid_exit {payload: {..., identity, to: "squid_b71e03"}} ->|  any other host: 'to' is not me, ignore
       |      (again every 3 s until it leaves or stops venturing)      |  resident alive? consent policy
       |                                                                |
       |<-- visit_response {accepted: false, reason, peer_uuid} --------|  refused: nothing else happens
 refused: stays home, may ask again
       |                                                                |
       |<-- visit_response {accepted: true, reason: "accepted", ...} ---|  accepted: draw the visitor, admit a
 begin_visit: home body frozen, senses                                  |  body, name the visit
 now read the host's frames                                             |
       |<-- perception_frame {visit_id, seq} (straight away) -----------|
 adopts visit_id from its first frame                                   |
       |                                                                |
 ======|========= every ROUND_TRIP_INTERVAL (0.5 s), both sides =========|=======
       |<-- perception_frame {seq++} -----------------------------------|  host tick: timeouts, mating news
       |<-- consequence {kind, detail} x 0..n --------------------------|  events queued since the last cycle
 own sensors -> own network -> select_action                            |
       |--- action_intent {seq++, lease 1.5 s} ------------------------>|  apply_intent: move, eat, play, throw;
       |                                                                |  contact, contest, fight, mating
       |--- gamete (only after a 'mated' consequence) ----------------->|  kept with the resident's egg
 ======|=========================================================================
       |                                                                |
 flight, rest or exhaustion wins, or it falls asleep:
       |--- visit_end {reason: "departed"} ---------------------------->|  remove body, close encounter
   or the host ends it:
       |<-- visit_end {reason: "ejected" | "link_lost"} ----------------|
   or no frame for 4 s:
       |--- visit_end {reason: "link_lost"} --------------------------->|
 end_visit: squid usable at home again,
 the visit filed as a memory of the resident
```

### 5.2 Deciding to go

Multiplayer being on only makes a visit possible. A squid ventures out while,
together (`src/venturing.why_not`): its lifecycle allows visiting (a parent
stays with its egg; a dead squid goes nowhere); its grown `aquarium_nearby`
sense is above 0; it is not fleeing or chasing food; its `act_move` neuron is
firing past its threshold; and the synapse `aquarium_nearby → act_move` is
excitatory. While that holds, the tank's side walls stop holding it in
(`Squid.move_squid`).

### 5.3 Asking to come in

When the venturing squid touches the left or right edge,
`Squid.check_boundary_exit` builds the exit data (4.2) and calls
`MultiplayerPlugin.address_exit`, which sets `to` to the peer heard most
recently within 30 s. With no such peer the squid stays put and nothing is
sent. Otherwise it multicasts `squid_exit` and will not send another for 3 s
(`EXIT_RETRY_SECONDS`). Nothing happens to the squid at home yet.

### 5.4 Consent

A host that hears a `squid_exit` (`handle_squid_exit_message`) ignores its own
and any whose `to` names another node. It then re-parses the identity and
decides: a dead resident refuses with `tank_closed`; otherwise
`ConsentPolicy.evaluate` runs the checks of 4.3. A refusal is answered with
`visit_response` and nothing else: no body is made, so a refused visitor cannot
enter.

### 5.5 Admission

On acceptance the host, in this order: stores the visitor's identity against
its node id; sends `visit_response` (accepted); draws the exit arrow; draws the
visitor at the mirror side of its tank; names the visit,
`new_visit_id(host_uuid, visitor_uuid)` =
`<host uuid[:8]>-<visitor uuid[:8]>-<host time in ms, hex>`
(e.g. `3f2a9c1e-a1b2c3d4-19a0146abfb`); admits a `VisitorActor` at the entry
point, facing into the tank; turns the resident's view cone to the newcomer;
re-announces a mating if this visitor is the resident's recorded mate; and
sends the first `perception_frame` at once. The **host names the visit**; the
visitor learns the name from that first frame.

The visitor accepts a `visit_response` only if `peer_uuid` is its own squid's
uuid and the sender is the node it addressed. Accepted, `VisitorMind.begin_visit`
freezes its body at home (`can_move = False`, `is_transitioning = True`), hides
it there (the tank says whose tank the squid is visiting; `end_visit` shows it
again) and points its three remote-driven senses at the host's frames. Refused, it stays
home (no `visit_end`, since no visit exists) and, if it is still venturing,
asks again 3 s later.

### 5.6 The round trip

Both roles run on the same 500 ms `QTimer` (`sync_game_state` →
`run_round_trip`, gated at `ROUND_TRIP_INTERVAL = 0.5` s). In each cycle:

- **Host**, `HostBody.tick()` first: queues a `mated` consequence for a
  visitor still owed one, ends visits silent for 12 s, marks visitors silent
  for 4 s with no live lease as `stalled`. Then, for each remaining visitor,
  it sends one `perception_frame` followed by every queued `consequence`.
- **Visitor**, `VisitorMind.tick()`: if its squid is asleep, it goes home; if
  no frame was accepted for 4 s, it goes home with `link_lost`; otherwise it
  reads its own brain state (propagated from the sensors the host's frame is
  driving), runs `decision_engine.select_action`, and sends one
  `action_intent`. Exhaustion (`act_collapse`), flight (`act_flee`) or rest
  (`act_rest`) winning ends the visit instead; a stubborn squid may hold off
  rest for a while and send its next-strongest action. Nothing clearing its
  threshold means no intent, and the body stops.
- **Host, on each intent** (`apply_intent`): it must come from the node the
  visitor arrived from, the visit id must match, `seq` must be greater than
  the last applied, and the lease (`sent_at + lease`, `sent_at` converted to
  the host's clock) must still be live.
- **Host, drawing**: each cycle the visitor's drawing is moved towards where
  its body is in this tank, facing the way the body faces
  (`RemoteEntityManager.follow_body`); its home's `object_sync` no longer
  places it, since its home body is frozen by the glass. The resident's eyes
  see the drawing, so this is where the resident sees it. The body then carries out the
  action (4.5) unless it is in a fight animation, and the host works out
  contact with the resident (a mating roll after 2 s of contact within
  120 px, once per visit, at `mating_chance`).

### 5.7 Consequences

Consequences are queued as the host resolves things (in `apply_intent`, in a
fight's resolution, in the rock-hit hook) and sent on the next cycle after the
frame. They report facts only (7.5). The visitor folds each one into its own
drives, statistics and the open encounter, and its own network decides what
to make of it.

### 5.8 How a visit ends

| Who | `reason` | When | Source |
|---|---|---|---|
| visitor | `departed` | `act_flee`, `act_rest` or `act_collapse` wins; or its squid is asleep | `VisitorMind.go_home` |
| visitor | `departed` | multiplayer is disabled or unloaded while it is away; its squid dies while away | `MultiplayerPlugin.disable`, `handle_resident_died` |
| visitor | `link_lost` | no accepted frame for `LINK_TIMEOUT` (4 s) | `VisitorMind.tick` |
| host | `link_lost` | no intent for `VISIT_ABANDON_TIMEOUT` (12 s) | `HostBody.tick` |
| host | `ejected` | multiplayer disabled or unloaded; the resident dies | `disable`, `handle_resident_died` |

The side that ends a visit sends `visit_end` (a visitor that never learned its
visit id sends nothing). The receiver ends it without answering: the host
removes the body and its drawing and closes the resident's encounter; the
visitor's `end_visit` closes its own encounter into memory, gives its own
senses back and makes its squid movable and visible again. `end_visit` cannot
leave a squid stranded: every failure path ends there.

### 5.9 Timeouts

| Silence | Host | Visitor |
|---|---|---|
| intent older than its lease (1.5 s) | stops applying it; the body is not moved | |
| 4 s (`LINK_TIMEOUT`) | no intent and no live lease: the body is marked `stalled` | no frame accepted: comes home, `visit_end link_lost` |
| 12 s (`VISIT_ABANDON_TIMEOUT`) | ends the visit, `visit_end link_lost` | |

The host never predicts or substitutes behaviour for a silent visitor. The
lease is measured in the host's clock: each intent's `sent_at` is shifted by
the smallest delay seen from that visitor, so the two machines' clocks need
not agree. Whatever is queued for a visitor - the `ejected` that
`HostBody.tick` queues at 12 s included - is sent before its body is removed,
then the `visit_end`.

### 5.10 Refusal

A refused visitor stays home and its squid keeps its normal walls once it
stops venturing. While it is still venturing it asks again every 3 s; the
host's `ConsentPolicy` remembers decisions (`DECISION_TTL = 30` s) but does not
consult them when evaluating, so each request is decided afresh. A refusal for
`unusable_identity` has no uuid to address (`peer_uuid: ""`); every
`visit_response` also names the node that asked (`to`), and that is what such
a refusal is matched on, so the squid comes home rather than asking forever.

### 5.11 Replays and duplicates

UDP can lose, reorder and (with several interfaces) duplicate datagrams.
Nothing is acknowledged; instead, everything that matters is either idempotent
or repeated.

| Mechanism | Where | What it protects |
|---|---|---|
| `(node_id, digest of the datagram)` seen within 10 s | `NetworkNode.receive_messages` | the same datagram arriving once per interface |
| `visit_id` | every remote-mind message | a packet from an earlier visit to the same tank. A new id is made for every admission (millisecond timestamp). |
| frame `seq`, strictly increasing | `RemotePerception.accept` | duplicate or out-of-order frames; reset when a visit begins |
| intent `seq` greater than the last applied, and a live lease | `HostBody.apply_intent` | duplicate, reordered or late intents |
| `mating_id` = `<visit_id>-mate` | host: one roll per visit; visitor: `PeerLedger.has_mated`, `EncounterSession.note_mated` | a visit can produce one mating, filed once however often `mated` is repeated (3 times per announcement) |
| `fight_id` (uuid4) | visitor: `SquidStatistics.record_fight_result(fight_id)`; host likewise | `fight_resolved` is sent 3 times; outcome applied once |
| `throw_id` (32 hex) | host: `(throw_id, target_uuid)` reported once (`_reported_rock_hits`); resident: felt once (`TamagotchiLogic._felt_rock_hits`); visitor: `(visit_id, throw_id, kind, taken)` once for the life of the process (`VisitorMind._rock_hits`) | one physical impact is felt and counted once on every side |
| gamete kept once per parent per egg | `Lifecycle.add_genes` | the gamete is resent with every `mated` received, on this visit or when the mating is retold on a later one |
| none | `contest_resolved`, `ate`, `blocked` | relies on the transport de-duplication only |

### 5.12 What each side keeps

Nothing about the protocol itself (visit ids, sequence numbers, node ids) is
saved. What persists is what happened:

| | Host (its resident) | Visitor (at home) |
|---|---|---|
| Encounter | memory `peer:<visitor uuid>`, if memorable | memory `peer:<resident uuid>`, if memorable; social learning applied to its synapses |
| Fight | statistics (`fight_id`), memory `fight:<id>`, consequences to body and drives, permanent aggression rise | the same, from `fight_resolved` |
| Rock or poop hits | counted in the encounter with the other squid (`peer:<uuid>`), or kept as `rock:<throw_id>` / `poop:<throw_id>` when no encounter with it is open; health and drives | the same, from `hit` |
| Its own throws | | memory of the throw; statistics (`rock_thrown`) |
| Mating | lifecycle reproduction record and egg, saved at once; the mate's genes with the egg, saved at once | memory of the mating against the resident; nothing in its body or lifecycle changes |
| Drives | changed by hits and fights | changed by `ate`, `contest_resolved`, `blocked`, hits and fights |

---

## 6. Timing constants

| Constant | Value | Source | Meaning |
|---|---|---|---|
| `ROUND_TRIP_INTERVAL` | 0.5 s | `remote_protocol.py` | frame/intent cadence; also the plugin's sync timer interval |
| `INTENT_LEASE` | 1.5 s | `remote_protocol.py` | longest an intent stays valid (host caps `lease` at this) |
| `LINK_TIMEOUT` | 4.0 s | `remote_protocol.py` | visitor with no frame comes home; host marks a silent body `stalled` |
| `VISIT_ABANDON_TIMEOUT` | 12.0 s | `remote_protocol.py` | host ends a visit with no intent |
| `SYNC_INTERVAL` | 1.0 s | `mp_constants.py` | `object_sync` cadence |
| heartbeat interval | 8.0 s | `mp_plugin_logic.py` (`sync_game_state`, literal) | minimum gap between periodic heartbeats |
| `HEARD_WITHIN` | 30.0 s | `src/venturing.py` | how long a heard peer counts as a nearby aquarium |
| `EXIT_RETRY_SECONDS` | 3.0 s | `src/squid.py` | gap between `squid_exit` requests |
| `DECISION_TTL` | 30.0 s | `consent.py` | how long a consent decision is remembered (not used by admission) |
| `_dedup_ttl` | 10.0 s | `mp_network_node.py` | how long a `(node_id, datagram digest)` key is remembered |
| `connection_retry_interval` | 5.0 s | `mp_network_node.py` | minimum gap between socket reconnects |
| message drain | 50 ms | `mp_plugin_logic.py` (`message_process_timer`) | how often received datagrams are decoded and handled |
| socket timeout | 0.1 s | `mp_network_node.py` | listener's `recvfrom` timeout |
| `MATED_ANNOUNCEMENTS` | 3 round trips | `host_body.py` | how many times `mated` is sent |
| `mating_contact_seconds` | 2.0 s | `host_body.py` (`DEFAULT_MATING_CONTACT_SECONDS`), `config.ini [Lifecycle]` | contact before the one mating roll |
| `FIGHT_COOLDOWN` | 25.0 s | `mp_plugin_logic.py` | per pair, between fights |
| fight animation | 3.2 s | `mp_plugin_logic.py` (`show_fight_cloud`) | `body_busy_until`; `in_fight` is 100 meanwhile |

The round-trip gate and the timer share the same 0.5 s, so a timer tick that
fires slightly early skips a cycle; the effective cadence is 0.5 to 1.0 s.

---

## 7. Privacy and safety

### 7.1 What never crosses in the remote-mind messages

`FORBIDDEN_KEYS` (`remote_protocol.py`), matched case-insensitively against
every key at any depth:

```
weights  state  brain  brain_state  neurons  neuron_positions
memory  memories  short_term_memory  long_term_memory
neurogenesis  capability  plasticity  provenance  causal_learning
hunger  happiness  satisfaction  anxiety  curiosity  cleanliness  sleepiness
personality_bias  peer_ledger
```

`PerceptionFrame`, `ActionIntent` and `Consequence` refuse a payload containing
any of them (`_reject_private`; more than 200 nested values also refuses it),
and `PerceptionFrame.to_payload` filters the sensors to `OBSERVABLE_SENSORS`
before sending, so a host bug cannot leak another one. A `Gamete` accepts only
its three keys. No filename, scene handle or path can be expressed: items are
host-issued ids, and a target id the host did not issue resolves to nothing.

### 7.2 The one exception by design: the gamete

Weights cross once per mating, and only as 4.8 describes: half of the synapses
between newborn neurons, no grown neuron, no state, no memory, reduced on
arrival to exactly that and kept only for the host's own egg from that mating.

### 7.3 What the presence broadcasts do carry

`object_sync` and `heartbeat` are older than the rules above. `object_sync`
goes to the whole group every second while multiplayer is on, visiting or not:
the sender's `status`, `is_sleeping`, position, view direction, its identity
and its LAN address (`node_info.ip`). It used to carry `hunger` and
`happiness` too - private drives, broadcast to every tank; it no longer does,
and a test holds it to `FORBIDDEN_KEYS`. `heartbeat` carries its position.

### 7.4 Clamping and limits

| Value | Limit |
|---|---|
| any `visit_id` | non-empty string, trimmed, at most 64 characters |
| sensors, `activation`, `aggression`, `defence` | 0-100 |
| `confidence` | 0-1 |
| `fitness` | 0-3 |
| `practice` | integer 0-100000 |
| `lease` | 0-1.5 s |
| positions and offsets | ±10^5 px; tank size 1 to 10^5 |
| `seq`, `sent_at`, `at` | 0 to 10^12 |
| frame items | at most 8; ids at most 40 characters of `[A-Za-z0-9_-]` |
| `heading`, `facing` | one of `left`, `right`, `up`, `down` |
| `action` | one of the eight action neurons |
| consequence `detail` | at most 12 keys of at most 32 characters; booleans, numbers (±10^6) and strings (at most 64) only |
| identity | uuid pattern and parse; name at most 32 plain characters |
| gamete | at most 600 genes, newborn-neuron synapses only, weights −1..1 |
| datagram | read whole (65535 bytes); at most 256 KiB once decompressed (2.5) |

### 7.5 Facts, never intent

- A **hit** tells the struck squid what struck it, how fast, which throw and
  who threw it. It never says whom the thrower aimed at, at what angle, or
  which neuron drove the throw and how strongly; those go only to the
  thrower, in its own `rock_thrown`.
- A **fight** tells the visitor who started it, who won, its chance and both
  abilities. It does not carry the resident's neuron values or reasons.
  Who starts a fight is decided from each squid's own `aggression` neuron:
  the resident's read locally, the visitor's from its last intent.
- A **contest** reports possession (`won`, or `held`), never a verdict.
- A **mating** reports only its id.
- The host never decides anything for the visitor: `apply_intent` is a
  dispatch on the action the visitor's network chose, and the host has none
  of the visitor's state to branch on.

### 7.6 Limits of the trust model

- Senders are not authenticated. Several handlers take the sender from a field
  inside the payload (`heartbeat.node_id`, `object_sync.node_info.id`,
  `squid_exit`'s inner `node_id`) rather than the envelope.
- Remote-mind messages are matched on `visit_id` and on the envelope's
  `node_id`: a host takes intents, `visit_end` and gametes for a visit only
  from the node its visitor arrived from, and a visitor takes frames,
  consequences and `visit_end` only from the host it asked to visit. Visit ids
  travel in clear, and node ids are self-declared, so this keeps visits from
  crossing by accident or by a careless peer - not from a determined forger.
- Only the remote-mind messages are listened for among those that act on a
  squid. The legacy `squid_return`, `rock_throw` and `squid_move` are not.
- There is no encryption and no rate limiting. The design assumes a trusted
  LAN.

---

## 8. Where in the code

| Concern | Where |
|---|---|
| Socket, envelope, compression, receive pipeline, de-duplication, `known_nodes` | `plugins/multiplayer/mp_network_node.py` (`NetworkNode`) |
| zlib helpers, node-id helper | `plugins/multiplayer/network_utilities.py` |
| Group, port, packet size, sync interval | `plugins/multiplayer/mp_constants.py` |
| Hook registration (`on_network_<type>` → handler) | `mp_plugin_logic.py`, `MultiplayerPlugin._register_hooks` |
| Heartbeat, world sync, round-trip timer | `mp_plugin_logic.py`, `sync_game_state`, `_get_squid_state`, `start_sync_timer`, `run_round_trip` |
| Discovery and choosing a host | `mp_plugin_logic.py`, `handle_heartbeat`, `visit_destination`, `address_exit`, `_perceive_aquariums`; `src/venturing.py` |
| Leaving the tank | `src/squid.py`, `is_venturing`, `check_boundary_exit`, `_exit_identity` |
| Admission and consent | `mp_plugin_logic.py`, `handle_squid_exit_message`, `handle_visit_response`; `plugins/multiplayer/consent.py` |
| Identity and protocol version | `plugins/multiplayer/identity.py` |
| Remote-mind message classes, limits, `FORBIDDEN_KEYS`, timings | `plugins/multiplayer/remote_protocol.py` |
| Host side: frames, intents, consequences, timeouts, contact and mating roll | `plugins/multiplayer/host_body.py` (`HostBody`, `VisitorActor`) |
| Visitor side: senses, decision, intents, consequences, going home, gamete | `plugins/multiplayer/visitor_mind.py` (`VisitorMind`, `RemotePerception`) |
| Remote-mind handlers | `mp_plugin_logic.py`, `handle_perception_frame`, `handle_action_intent`, `handle_consequence`, `handle_visit_end`, `end_visit_as_host`, `handle_gamete` |
| Fights | `mp_plugin_logic.py`, `show_fight_cloud`, `_who_starts_a_fight`, `resolve_fight`; `src/fighting.py` |
| Rock and poop impacts | `mp_plugin_logic.py`, `handle_rock_hit`; `src/tamagotchi_logic.py`, `on_rock_hit`, `throw_visitor_rock`; `src/interactions.py`, `throw_from_visitor`; `src/throwing.py` |
| Gamete contents | `src/inheritance.py` (`gamete`, `clean_gamete`); `src/lifecycle.py` (`is_valid_mating_id`, `Lifecycle.add_genes`) |
| Packet allow-list (not wired in) | `plugins/multiplayer/packet_validator.py` |
| Tests | `tests/test_peer_discovery.py`, `tests/test_encounter_stage0.py`, `tests/test_remote_mind_stage1.py`, `tests/test_reproduction_lifecycle.py`, `tests/test_rock_throwing.py`, `tests/test_protocol_hardening.py`; LAN harnesses in `tools/test_lan_round_trip.py`, `tools/test_rock_multiplayer.py`, `tools/test_venture_multiplayer.py` |

### Android (Nearby) transport

The Android build reuses the same payload classes (section 4) over one
consented Google Nearby link instead of multicast
(`android/dosidicus_mobile/engine/peer_visit.py`).
Its envelope is `{"protocol": 4, "kind": <type>, "payload": {...}}`: no node
id, no timestamp, no compression, serialised with `allow_nan=False`. Packets
over 16384 bytes are ignored, a packet whose `protocol` differs is dropped,
and the link opens with a `hello` message,
`{"identity": <SquidIdentity>, "hosting": <bool>}`, in place of
`squid_exit`/`visit_response`. A parent (which stays with its egg) or a dead
squid sends no `hello` as a visitor, and a dead squid admits nobody.

After `hello` the kinds and shapes are exactly section 4's:

| Direction | Kinds |
|---|---|
| host -> visitor | `perception_frame`, `consequence` (including `mated`), `visit_end` |
| visitor -> host | `action_intent`, `gamete`, `visit_end` |

The host runs the shared `HostBody`, including `HostBody.tick()` each half
second: a mating is rolled once per visit with the `[Lifecycle]` defaults and
announced over the next round trips; the visitor resends its `gamete` with
each announcement, and the host keeps the first one (a resend is a valid
packet that changes nothing). A gamete naming another visit, another mating
or another mate is rejected.

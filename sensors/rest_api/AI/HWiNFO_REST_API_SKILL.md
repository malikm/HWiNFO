---
name: hwinfo-rest-api
description: Use when reading hardware sensor data or managing the sensor filter (hide/monitoring/logging flags) through the sensor REST API - endpoints, JSON layouts, TLS/CORS rules, request examples, error handling.
---

# HWiNFO REST API

JSON over HTTP(S). Read live sensor readings and manage a per-sensor filter (hide / monitoring / logging).

## Connecting

- Base URL: `https://<host>:<port>` (or `http://` when the server runs without TLS).
- TLS may use a self-signed certificate: clients must trust it or skip verification (`curl -k`). A browser must trust it
  once before pages from another origin can call the API.
- **No authentication yet.** Only use it on trusted networks; the filter endpoints change server state.
- CORS: JSON responses carry `Access-Control-Allow-Origin: *`. CORS preflight (OPTIONS) is not supported, so a
  cross-origin browser POST must be a "simple request": send `Content-Type: text/plain` (the body is still JSON; the
  server ignores the content type). Non-browser clients are unaffected.
- Responses are UTF-8 and not cacheable. Use absolute paths (`/api/...`); a wrong path returns a **plain-text**
  `404 Not Found`, not JSON. A wrong method on a known path returns `405`.
- While the server shuts down, requests get a plain-text `503 server is stopping`.

## Version

Every JSON of the API carries a root `"Version"` (integer). **Each kind of JSON has its own version**, they can change
independently: a client must compare the version of a JSON with the versions it knows for THAT kind, not with one global
number. Currently all four are **1**.

**Backward compatibility:** a side supports a range `min..current` per JSON, not a single number. It writes `current` and
accepts every version from `min` to `current`. When a JSON moves to version 2 the server raises `current` to 2 and keeps
`min` at 1 while version 1 is still handled, so old clients keep working; a version outside the range is an error
(`unsupported 'Version' 3 (supported: 1..2)`). A server that supports 1..2 serves `read` / `sdb` in its `current` version.

| JSON | Version | Direction | Rule |
|---|---|---|---|
| `GET /api/sensors/read` | 1 | server -> client | the server sends `"Version": 1` (first key). Client: **must check it**: missing = error, a version outside the client's supported range = error; do not use the data |
| `GET /api/sensors/sdb` | 1 | server -> client | the server sends `"Version"` (the file's own; `1` is added when the file has none; a file with another version gives `500`). Client: same rule as `read` |
| `POST /api/sensors/filter/apply` | 1 | client -> server | `Version` **required**: missing, not an integer or not supported = `400 {"error":"'Version' is missing"}` / `"'Version' must be an integer"` / `"unsupported 'Version' 2 (supported: 1)"` (the supported number is that JSON's own) |
| `POST /api/sensors/logging/setup` | 1 | client -> server | same rule as `filter/apply` |

Bodies of `filter/reset`, `logging/start`, `logging/stop` and `update_display` are ignored (no Version needed).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/ping` | `{"pong":true,"t":1762848000123.456}`; tiny reply to measure round-trip time. `t` = server UTC epoch ms (3 decimals) for clock sync (see "Timing" below) |
| GET | `/api/sensors/read` | live sensor readings |
| GET | `/api/sensors/sdb` | Sensor Database (SDB): full description of the sensors (hierarchy, location, reading type, unit, tooltip, hide/monitoring/logging flags), modeled on what HWiNFO can export; stored filter merged in |
| POST | `/api/sensors/filter/apply` | apply a filter to the current sensor tree so only the wanted sensors remain (body = flags tree) |
| POST | `/api/sensors/filter/reset` | discard the filter and all changes made by `apply`, restoring the default tree (body ignored) |
| POST | `/api/sensors/logging/setup` | options of HWiNFO's built-in logging (file, format, limits; body = JSON, see below): `200 {"ok":true}` or `400 {"error":..}` |
| POST | `/api/sensors/logging/start` | start HWiNFO's built-in logging with the `setup` options; only readings with `logging` = 1 are written (body ignored): `409 {"error":..}` if logging is already running, else `200 {"ok":true}` |
| POST | `/api/sensors/logging/stop` | stop HWiNFO's built-in logging and close the file (body ignored): `409 {"error":..}` if logging is not running, else `200 {"ok":true}` |
| POST | `/api/sensors/update_display` | makes HWiNFO redraw the sensor list in its Sensors window (invalidates the UI only; does NOT read fresh values); use after `filter/apply` / `filter/reset` (body ignored), `200 {"ok":true}` |

### POST /api/sensors/logging/setup

Body (root `"Version": 1` is **required**, see "Version" above; all other values are strings; `Note` and `NOTE` are two separate free-text keys; unknown keys are ignored; the JSON must not contain comments):

```json
{ "Version": 1, "file name": "log", "file path": "", "file type": "csv", "data/time format": "default", "csv separator": ",",
  "json type": "by timestamp", "logging time limit": "10", "logging delay": "0", "no buffering": "Yes",
  "Note": "", "NOTE": "" }
```

`file path` = free text (folder of the log file). Allowed: `file type` csv | json | yaml; `data/time format` default | RFC 3339 | ISO 8601; `json type` by timestamp |
by sensors; `logging time limit` / `logging delay` = seconds (number >= 0). Invalid body or value: `400 {"error":..}`.
These options configure HWiNFO's built-in logging; `logging/start` begins it, `logging/stop` ends it, and it also ends when `logging time limit` is reached.

### GET /api/sensors/read

`200` with the readings, or `503 {"error":"<reason>"}` when the sensor source is unavailable.

```json
{
  "Version":         1,                            // required format version (see "Version")
  "Timestamp RS":    "11.11.2026 14:43:09.431",   // read start (server local time)
  "Timestamp":       "11.11.2026 14:43:09.559",   // all sensors read
  "Timestamp RE":    "11.11.2026 14:43:09.590",   // read + JSON end
  "Timestamp RS ms": 1794404589431.396,            // the same three instants as UTC epoch ms (see Timing)
  "Timestamp ms":    1794404589559.047,
  "Timestamp RE ms": 1794404589590.982,
  "<sensor name>": {
    "<reading name>": { "<type>": { "Value": "19,324" } },
    "<group name>": {
      "<type>": { "Value": "1.172" },                                        // the group's own value (optional)
      "<reading name>": { "<type>": { "Value": "..." } }
    }
  }
}
```

Real example (captured from a running server):

```json
{ "Version": 1, "Timestamp RS": "...", "Timestamp": "...", "Timestamp RE": "...", "Timestamp RS ms": 1794404589431.396, ...,
  "System: ASUS ": { "Virtual Memory Committed": { "8": { "Value": "19,324" } } } }
```

- Top-level strings and numbers are timing fields; every top-level **object** is a sensor. Key order is meaningful
  (display order). The root `"Version": 1` comes first (see "Version" above); it is not a sensor.
- **The reading type is a tree level, not a field.** A reading is NOT `{"Value": .., "Type": 8}`. It is
  `"<reading name>": { "<type>": { "Value": ".." } }` where `<type>` is the number as a **string key**:
  `"0"` NONE, `"1"` TEMP, `"2"` VOLT, `"3"` FAN, `"4"` CURRENT, `"5"` POWER, `"6"` CLOCK, `"7"` USAGE, `"8"` OTHER
  (SENSOR_ENTRY_TYPE). One name can occur with several types (`"<name>": {"1": {..}, "7": {..}}`, same name, different
  sub-sensors): treat each `<name>/<type>` as its own reading. The type node holds `Value` only.
- A **group** is an object that has child objects other than type nodes. It may also carry its own value, as numeric
  type keys next to its sub-nodes: `"<group>": { "2": {"Value": "1.172"}, "<child>": { "2": {..} } }`.
  Nesting depth is arbitrary. How to tell them apart: a numeric key whose object has `Value` is a type node, any
  other object key is a child (a client usually folds the type level into the reading, it is not a displayed level).
- `Value` is a **string**, already formatted; it may contain thousands separators (`"12,952"`) or text (`"Yes"`/`"No"`).
  Strip commas before parsing numbers.
- There is **no `Unit`, no `Tooltip` (and no `Type` field) in `read`**: static data is not sent each time. The unit
  (`"MB"`, `"%"`, `"°C"`, empty string = no unit) and the description of a reading are the `Unit` and `Tooltip` strings
  in its node of `GET /api/sensors/sdb`; clients fetch the SDB once (before showing the first values) and look them up
  by sensor / reading name (and type). Without an SDB, show the values without a unit.
- **Timing:** next to the three local-time strings the root carries the same instants as numbers,
  UTC epoch milliseconds with 3 decimals: `"Timestamp RS ms"`, `"Timestamp ms"`, `"Timestamp RE ms"` (not sensors, not
  strings: skip them like `Version`). They come first in the object, before the sensors. `RS` = before the sensor read, `Timestamp` = after it,
  `RE` = JSON tree built (serialization itself is not included). Clients measure the clock offset with `/api/ping`
  (`offset = t - (t0 + t3)/2` of the ping with the smallest RTT, error <= RTT/2), then: request -> RS = `RS - offset - t0`,
  readout = `Timestamp - RS`, JSON build = `RE - Timestamp`, RE -> received = `t3 - (RE - offset)`, total = `t3 - t0`.
- Readings update at the sensor source's own rate (about every 2 s).

### GET /api/sensors/sdb

The Sensor Database (SDB): a hierarchical description of all sensors (hierarchy, location, reading type, unit, tooltip, flags). It is the static counterpart of `read`, which carries only values: load it once, then match each `read` value to its node by sensor / reading name and type. The flags-only form of the same tree is what `filter/apply` accepts. Errors: `404 {"error":"..."}` if the tree is not available, `500 {"error":"..."}` if it is
invalid.

Shape: **sensor -> sensor**, or **sensor -> group -> sensor**. Root `"Version": 1` comes first (see "Version" above).

**Type level** (same as in `read`): a reading name maps to its type(s) and the flags sit one level lower:
`"<reading name>": { "<type>": { hide, monitoring, logging, tSensorLocation, tReadingLocation, tReadingType } }`
(`<type>` = the reading type number as a string key, e.g. `"8"`; the same name may occur with several types). A group keeps
its own flags the same way, next to its sub-nodes: `"<group>": { "2": {flags}, "<child>": { "2": {flags} } }`.
The nodes with `hide` are still the flagged nodes; the numeric key is just an extra level above them.
- A node with a `hide` key carries flags `hide`, `monitoring`, `logging` (each 0 or 1). Sensors also carry the metadata
  objects `tSensorLocation`, `tReadingLocation` and `tReadingType` `{eType, eTypeUnion}`; these are **not** children.
  They also carry `"Unit": "<unit of the reading>"` and `"Tooltip": "<description of the reading>"` (strings, static data
  for display, they are not flags: do not send them back in a filter, the server keeps them when it merges the stored
  filter into the tree). In the type-level layout they sit in the type node (`"<name>": {"8": {hide, ..., "Unit": "MB",
  "Tooltip": "..."}}`).
- Every other object value is a child node; a flagged node may have children. Groups also carry the three flags.
- `tReadingType.eType`: 0 None, 1 Temperature, 2 Voltage, 3 Fan, 4 Current, 5 Power, 6 Clock, 7 Usage, 8 Other;
  `eTypeUnion` selects the sub-type inside that category.
- **Meaning of the flags** (they mirror HWiNFO itself, per sensor or reading):
  - `hide` = 1: the sensor/reading is hidden inside HWiNFO (not shown in its UI). For this API it is **omitted from
    `GET /api/sensors/read`**.
  - `monitoring` = 0: monitoring of the sensor/reading is stopped/paused in HWiNFO, but it is not hidden there. For
    this API it is also **omitted from `read`** (`hide` and `monitoring` act the same way on `read`).
  - `logging` = 0: HWiNFO does not log the sensor/reading. It has **no effect on `read`**; the reading is still returned.
- Rule: **hide = 1 forces monitoring = 0, and monitoring cannot be enabled while hide = 1.** Send it that way (a client
  UI should disable the monitoring checkbox while hide is on).
- After a successful apply the response has the applied filter's structure (nodes missing from it are gone, new nodes are
  present) while keeping the metadata of nodes that already existed.

### POST /api/sensors/filter/apply

Body (max 1 MB, else `413`): the flags-only tree, same nesting as `/api/sensors/sdb` (including the type level, if the sdb has it),
every flagged node with exactly the three flags. The root `"Version": 1` is **required**:

```json
{ "Version": 1,
  "Sensor A": {
    "Reading 1": { "hide": 0, "monitoring": 1, "logging": 1 },
    "Group X":   { "hide": 0, "monitoring": 1, "logging": 1,
                   "Reading 2": { "hide": 1, "monitoring": 0, "logging": 1 } } } }
```

With the type level the same filter looks like
`"Sensor A": { "Reading 1": { "8": { "hide": 0, "monitoring": 1, "logging": 1 } } }`.

- `200 {"ok":true,"sensors":N}`, N = number of flagged nodes.
- `400 {"error":"..."}`: body is not a JSON object, `Version` is missing / not an integer / unsupported, a value in a group is not an object (except the root `Version`), a
  flagged node lacks a flag, a flag is not the integer 0 or 1, or nesting is deeper than 16.
- The filter replaces the previous one entirely. It is kept by the server until reset or restart.
- It is applied to `/api/sensors/read`: a reading whose own node, or any group/sensor above it, has `hide = 1` or
  `monitoring = 0` is **omitted** from the response (not sent with an old value); a sensor left without readings is
  omitted too. `logging` does not affect `read`. Names missing from the filter stay visible. With the type level the flags of the matching `<type>` node
  are used. Clients must treat a missing reading as "not monitored", not keep showing its last value.
- `/api/sensors/sdb` shows the stored filter merged into the original tree.

### POST /api/sensors/filter/reset

`200 {"ok":true}`. Afterwards `/api/sensors/sdb` returns the original tree again.

## Examples

```bash
curl -sk https://HOST:PORT/api/ping
curl -sk https://HOST:PORT/api/sensors/read
curl -sk https://HOST:PORT/api/sensors/sdb
curl -sk -X POST -H "Content-Type: text/plain" --data @filter.json https://HOST:PORT/api/sensors/filter/apply
curl -sk -X POST -H "Content-Type: text/plain" -d "" https://HOST:PORT/api/sensors/filter/reset
```

### Logging with curl

Order: configure, start, stop. `setup` validates and sets the options of HWiNFO's built-in logging; `start` answers `409` if logging is already running, `stop` answers `409` if it is not.

```bash
# 1. settings from a file (plain JSON: the logging.json sample in the repo has '#' comments that must be removed)
curl -sk -X POST -H "Content-Type: text/plain" --data @logging_setup.json https://HOST:PORT/api/sensors/logging/setup
# ... or inline (bash; in cmd.exe use double quotes and escape the inner ones as \")
curl -sk -X POST -H "Content-Type: text/plain"      -d '{"Version":1,"file name":"log","file path":"C:/logs","file type":"csv","logging time limit":"10"}'      https://HOST:PORT/api/sensors/logging/setup
# 2. start (body ignored)
curl -sk -X POST -H "Content-Type: text/plain" -d "" https://HOST:PORT/api/sensors/logging/start
# 3. stop (body ignored)
curl -sk -X POST -H "Content-Type: text/plain" -d "" https://HOST:PORT/api/sensors/logging/stop
```

Every call answers `{"ok":true}`, or `{"error":"..."}` with `400` (bad setup body) / `409` (wrong state). Add `-i` to see
the status code, or `-w "%{http_code}"`. Use `http://` and drop `-k` when the server runs with `--http`.

```js
const r = await fetch('/api/sensors/filter/apply', {
  method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: JSON.stringify(flags) });
const j = await r.json().catch(() => ({}));                  // 404 / 503 bodies are not JSON
if (!r.ok || j.error) throw new Error(j.error || 'HTTP ' + r.status);
```

## Agent checklist

0. Every JSON has a root `"Version"` (integer, currently 1; see "Version"). Send it in every POST body; on received data, check it: a missing Version is an error, and so is a version the client does not support (outside its `min..current` range): stop, report it and do not use the data.

1. `GET /api/ping` first: connection refused = server not running, TLS error = untrusted certificate.
2. `GET /api/sensors/read`: on `503` report the `error` text to the user.
3. Check `res.ok` before `res.json()`; plain-text error bodies exist (404, 503 while stopping).
4. To change a filter: GET `/api/sensors/sdb`, edit the flags, reduce the tree to flags only (keep nesting), enforce
   hide => monitoring 0, POST it, then GET `/api/sensors/sdb` again to confirm.
5. Do not poll `read` too fast. POST only when the user intends the change.

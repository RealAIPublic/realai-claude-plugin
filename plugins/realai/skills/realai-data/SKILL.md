---
name: realai-data
description: Workflow guide for querying the RealAI MCP — entity resolution, schema discovery, and query construction.
---

## Overview

This skill defines how to interact with the realai mcp. It covers the correct call sequence, how to resolve entity names, how to discover schema, and how to construct queries.

Use this skill when the task is about accessing data — finding entities, exploring what data exists, or building a query. For analysis built on top of that data, use the realai-analyst skill.

All data must come live from the MCP tools at query time. Do not cache schema results, hardcode entity IDs, topic names, or field values between sessions.

---

## Tools

| Tool                    | Purpose                                                                       |
| ----------------------- | ----------------------------------------------------------------------------- |
| `entity_search_by_name` | Resolve a name string to a typed entity with a primary key                    |
| `explore_data`          | Discover available entity types, topics, and fields from the live schema      |
| `query_data`            | Execute a structured query against an entity using topics from `explore_data` |

---

## Mandatory Call Sequence

The tools are designed to be called in a fixed order. Skipping steps causes errors.

1. **`entity_search_by_name`** — if the user gave you a name (market, property, city, etc.) that needs to be resolved to an ID. Skip if you already have the entity ID.
2. **`explore_data` scope `"entities"`** _(conditional)_ — call when you need to confirm entity types, identify foreign-key relationships, or look up a lowercase entity name. Skip if the entity type is already known.
3. **`explore_data` scope `"topics"`** — get the exact topic name strings for the target entity type. This step is required before calling `query_data`. Topic names are opaque identifiers — they cannot be guessed from natural language.
4. **`explore_data` scope `"fields"`** _(optional)_ — get queryable field names for one or more specific topics. Call this when you need to know which fields a topic exposes before building filters or selecting specific columns.
5. **`query_data`** — execute the query using entity type, topics, filters, and sort from the steps above.

Never skip step 3. Never guess or infer topic names.

---

## Entity Resolution

Use `entity_search_by_name` to convert a user-provided name into a primary key and entity type.

- Use 1–2 words of the name for best results — not the full string
- If no results are returned, shorten the query to 1–2 words. For markets, use the city name only (e.g., `"Atlanta"` not `"Atlanta Metro Area"`). For properties, use street number and street name only, without suite or unit suffixes.
- Returns: `entityId` (primary key), `entityType` (uppercase display category, e.g. `PLACE`, `MARKET`, `PROPERTY`), `name`, `score` (match confidence 0–1), `displayGroup`, and `attributes` (`address` populated for property results, null otherwise; `source_type` carries the lowercase entity name to pass to `query_data`). Use `score` to judge confidence — scores below 0.85 should be confirmed before proceeding.
- Does not index single-family properties — use the SFR lookup pattern below instead

**entityType mapping:** `entityType` is an uppercase display category and cannot be passed to `query_data`. Use `attributes.source_type` directly — it is the lowercase entity name for `query_data` for every result type (`census_place`, `market`, `property_mfr`, etc.). No cross-reference to `explore_data` scope `"entities"` is needed for this mapping; that scope is for confirming foreign keys and grains, not for translating a search hit.

---

## Schema Discovery

### scope `"entities"`

Call once to get all available entity types. Each entity includes its identity fields and any foreign keys that reference other entities.

To identify valid geographic grains beneath a parent entity: scan the `identity_fields` of every entity in the result — any entity with a `foreign_key` whose `references_entity` matches the parent's entity type is a valid grain. Derive options from the live schema; do not hardcode them.

### scope `"topics"`

Call once per entity type before building any query. Returns the exact topic name strings needed for `query_data`. These strings can be an empty array [] to return only identity fields with no topic data.

### scope `"fields"`

Call when you need to inspect the specific fields within a topic before writing filters or selecting columns. Pass the `topics` parameter to limit results to the topics you care about.

Always call fresh. Do not reuse schema results from a previous session.

---

## Query Construction

Grain availability and required filters are defined once in `references/grain-coverage.md`. Sibling skills must link to it, never restate it

### Required parameters

- `title` — a brief human-readable description of what the query is for
- `entity` — the entity type to query (from `explore_data` scope `"entities"`)

### Optional parameters

- `topics` — topic objects, each with a `topic` string from `explore_data` scope `"topics"`. Omit or pass `[]` to return only identity fields with no topic data.

### Topics

Each topic object requires a `topic` string. Optionally add a `fields` array to return only specific columns instead of all fields for that topic. Pass `topics: []` to `query_data` to retrieve only identity fields with no topic data.

### Filters

Filters use dot-notation field paths:

- Topic fields: `"topic.field"` — e.g., `"household_financials_snapshot.median"`
- Identity fields: bare name — e.g., `"id"`, `"name"`

Available operations:

| Operation              | Use for                                      |
| ---------------------- | -------------------------------------------- |
| `EQUALS`               | Exact match on a single value                |
| `EQUAL_IGNORE_CASE`    | Case-insensitive exact match                 |
| `IN`                   | Match any value in a list                    |
| `NOT_IN`               | Exclude values in a list                     |
| `GREATER_THAN`         | Numeric or date greater than                 |
| `GREATER_OR_EQUAL`     | Numeric or date greater than or equal        |
| `LESS_THAN`            | Numeric or date less than                    |
| `LESS_OR_EQUAL`        | Numeric or date less than or equal           |
| `IS_NOT_NULL`          | Field has a value (no `value` param needed)  |
| `IS_NULL`              | Field has no value (no `value` param needed) |
| `CONTAINS`             | Substring match                              |
| `CONTAINS_IGNORE_CASE` | Case-insensitive substring match             |

### Sort

`sort_by` uses the same dot-notation as filters. Each entry requires a `field` and `type` of `ASCENDING` or `DESCENDING`.

### Pagination

- Default limit: 100 rows
- Max limit: 1000 rows
- Use `offset` to page through results

---

## Common Patterns

### Resolve a name, then query children

1. Call `entity_search_by_name` with 1–2 words of the parent name
2. Note the returned `id` and `entity` type
3. Call `explore_data` scope `"topics"` for the child entity type
4. Call `query_data` on the child entity, filtered by the parent's ID using the child's foreign key field

### Single-family property lookup

The `property` entity has 126M+ rows. An address filter alone will time out. You must combine it with a geographic identity field filter to make the query viable.

1. Resolve the geographic context first — call `entity_search_by_name` to get the `id` for the relevant market, county, state, or zipcode.
2. Query the `property` entity with an empty `topics` array and two filters:
   - A geographic identity field (`zipcode_id`, `county_id`, `market_id`, or `state_id`) EQUALS the resolved ID from step 1 — use the tightest grain available
   - `address` CONTAINS_IGNORE_CASE the street address (street number + street name only)
3. Note the returned `id` from the identity fields.
4. Query `property_residential` filtered by `id` EQUALS that value with whichever topics you need.
   Do not use `entity_search_by_name` for SFR — it won't find them. Do not filter `property` on address alone — it will always time out.

### Progressive geographic widening

Start at the tightest grain. If the result count is too low, widen to the next grain up.

Typical order (tightest → widest): `centum` → `neighborhood` → `zipcode` → `census_place` → `submarket` → `county` → `market` → `state` → `nation`

Each grain requires its own `explore_data` scope `"topics"` call since topic names may differ between entity types.

### Multi-topic query

Include multiple topic objects in a single `query_data` call to retrieve fields from several topics at once. All topics must be valid for the same entity type.

Topics with `separate_data_source: true` cannot be combined with each other. A single `query_data` call may include at most one such topic. Snapshot topics (no `separate_data_source` flag) can be freely combined with each other.

### Time series topics

Many own-table (`separate_data_source: true`) topics carry required filters — not only time series. Check `required_filters` in the `explore_data scope "topics"` response for every topic before calling `query_data`; a missing required filter returns a 400.

Two patterns: (a) `period_type` required — use `required_filters[].field` as the filter field and one value from `required_filters[].values` as the filter value; (b) `id` required — use field `"id"`, operation `EQUALS`, and the entity's primary key as the value. Missing either returns a 400.

Valid `period_type` values differ by topic and are case-sensitive. Always read them from `required_filters[].values` in the `explore_data scope "topics"` response. Do not infer casing from other topics.

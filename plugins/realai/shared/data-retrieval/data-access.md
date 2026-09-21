# Working with the RealAI MCP

This is the single retrieval workflow for all four skills in Claude Code and Cowork.
Use the host's existing authenticated RealAI MCP tools. Do not build an HTTP client,
read credentials, or require a local runtime to retrieve data. Tool prefixes vary by host;
use the exposed tools matching `entity_search_by_name`, `explore_data`, and `query_data`.

## Contents

- [Start from the question](#start-from-the-question)
- [Resolve the subject](#resolve-the-subject)
- [Discover once, reuse within the conversation](#discover-once-reuse-within-the-conversation)
- [Construct a bounded query](#construct-a-bounded-query)
- [Read results and extend only as needed](#read-results-and-extend-only-as-needed)
- [Recover without loops](#recover-without-loops)

## Start from the question

Identify the subject, relevant measure, and period. Reuse resolved IDs, live schema, and
results already available in this conversation. A follow-up usually needs only the new
measure or comparison. Do not start every answer with a complete data pull.

Use `topic-catalog.md` to find candidate topics and `grain-coverage.md` for coverage.
These references help plan; current tool schemas and live discovery define valid calls.
Keep existing evidence with its dates. Refresh when the user asks for current data, the
subject changes, or a schema/coverage error indicates it is stale. Do not carry unverified
IDs or schema from another conversation as current facts.

## Resolve the subject

Search a distinctive name fragment, usually 1–2 words. Confirm location and entity type
against the user's intent. A high search score measures string similarity, not identity;
ask only when plausible candidates remain ambiguous. Use a state filter only if the user
supplied the state. Shorten an unsuccessful name search before assuming no coverage.

Use the result's `entityId` and `attributes.source_type` for downstream calls. The latter
identifies the query entity, including `property_mfr`; do not simply lowercase `entityType`
or treat a multifamily result as the master `property` entity. If source_type is absent,
check live entity definitions rather than guessing.

Single-family homes are not in name search. Resolve geographic context, then query the
master `property` entity with `topics: []`, a geographic identity filter, and a distinctive
street address using `CONTAINS_IGNORE_CASE`. Use the matching `id` on `property_residential`.
Do not scan the master property table by address alone. If geography is unknown, ask for
city/state or ZIP before a broad property lookup.

## Discover once, reuse within the conversation

1. Use `explore_data(scope: "entities")` when entity types or parent/child relationships
   are not already known. Its identity fields expose foreign keys; geography is not one
   universal nesting ladder.
2. Before the first query for an entity type, use `explore_data(scope: "topics", entity: …)`.
   Reuse that response for later subjects of the same type. It supplies exact topic names,
   `required_filters`, `separate_data_source`, and available source metadata.
3. Use `explore_data(scope: "fields", entity: …, topics: […])` before projecting fields,
   or when a filter/sort field is not already verified. Restrict discovery to the relevant
   topics. Required-filter field names are already supplied by topic discovery.

Required-filter values are case-sensitive. Copy the discovered `required_filters[].field`
as supplied; it is already dot-notated when appropriate. Copy a permitted value from
`required_filters[].values` when present. A required identity filter may have no value
list; supply the resolved ID. Even when not required, constrain the subject and period.

## Construct a bounded query

`query_data` accepts `title`, `entity`, `topics`, `filters`, `sort_by`, `limit`, and `offset`.
Use a brief description for `title`. `topics` is an array of objects, each containing
`topic` and, optionally, `fields`; projection is **inside each topic object**, never a
separate top-level `fields` argument. `topics: []` requests identity fields only.

Combine relevant topics for one entity when none has `separate_data_source: true`.
A topic carrying that flag must be queried **alone**, without any other topic. Follow the
live flag rather than assuming all snapshots combine or all time series are separate.

For a small subject pull, requesting the relevant topic without projection is a useful
baseline. For large or wide candidate sets, use verified `topics[].fields` to keep only
the measures, dates, and quality fields needed. Projection field names are bare names from
field discovery. Filters and sorting use `topic.field` for topic fields and bare identity
fields such as `id` or `market_id`.

Filter operations: `EQUALS`, `EQUAL_IGNORE_CASE`, `IN`, `NOT_IN`, `GREATER_THAN`,
`GREATER_OR_EQUAL`, `LESS_THAN`, `LESS_OR_EQUAL`, `IS_NOT_NULL`, `IS_NULL`, `CONTAINS`,
`CONTAINS_IGNORE_CASE`. Omit `value` for the two NULL checks. Sort entries use `field` and
`type: "ASCENDING"` or `"DESCENDING"`; translate discovery's default-sort descriptions
into this call shape if setting an explicit sort.

The default limit is 100 rows; the maximum is 1,000. Narrow filters as well as output:
a small limit does not make a table-wide scan cheap. On the large master `property`
entity, combine a geographic identity filter with the address or other selection filter.
For time series, constrain the entity and relevant dates, and inspect the topic's actual
date and period fields instead of assuming every series uses the same ones.

## Read results and extend only as needed

Check subject, units, observation dates, completeness, and row count before interpreting.
A NULL field, zero, and an empty result are different. Never invent a NULL's cause or a
missing value. `../output-conventions.md` governs which limitations the user needs to see;
`../interpretation-guide.md` and the relevant domain reference govern meaning.

A full page may be truncated. If the task needs the whole eligible set, continue with
`offset` and a stable explicit ordering, including a verified tie-breaker where possible.
Stop when the response indicates completion or a page is shorter than the requested limit.
Do not present a partial candidate set as an exhaustive ranking. Follow
`../multi-entity-analysis.md` for rankings and composites.

If an alternate geography can answer a useful contextual question, use verified foreign
keys to select it and check its topic coverage. State the geography actually measured;
a market figure is not a replacement measurement of a building. Do not treat an AVM as
an observed sale price or a benchmark ratio as the property's actual expenses. Broaden
only when it helps the question, not to fill every absent field.

## Recover without loops

- **Absent tools or authentication failure:** stop MCP calls. Explain the connection
  issue once. In Claude Code, use `/mcp` to inspect/authenticate the connection; in Cowork,
  use the host's connector/plugin controls. Continue with already retrieved evidence or
  supplied documents where useful, retaining their actual provenance. Resume calls after
  authentication succeeds; never retry authorization errors in a loop.
- **Validation failure (400):** correct the named schema/filter issue using live discovery.
  Do not repeat the same payload. If one informed correction fails, leave that retrieval
  unresolved and continue with supported evidence.
- **Successful empty result:** check identity, grain, and restrictive filters. Make at most
  one targeted alternative query when it can answer the question. Do not infer privacy
  suppression or the absence of households from an empty response.
- **Timeout, connection failure, or server error:** after the call returns an error, make
  at most one useful retry with narrower scope/projection when the error suggests that
  could help. If the connection is unavailable, stop calls. A pending call is not a
  completed failure: do not issue duplicates or invent timeout/cancellation parameters
  the host does not expose. Use supported host cancellation if available.

After an unsuccessful recovery, say briefly what requested result remains unresolved or
which conclusion is limited. Keep working on independent parts; do not restart the entire
analysis or list unrelated NULL fields.

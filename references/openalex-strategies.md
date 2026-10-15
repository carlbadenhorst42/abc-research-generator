# OpenAlex and Consensus research strategies

## Choose the next search by the research decision

OpenAlex is a scholarly graph, not just a keyword index. Start with a seed, expand deliberately, then read selectively. Use 3–5 seed candidates, one expansion round, and 8–12 relevant works as working defaults; expand for a concrete unresolved question. Never describe this bounded exercise as a systematic review.

| Decision | Strategy | What it can establish / cannot establish |
|---|---|---|
| Which paper is this? | Resolve DOI; otherwise title search and check author/year/type/version | Identity, not trustworthiness or peer review |
| Where did the idea come from? | Read seed references and foundational works | Intellectual antecedents; reference edges do not prove endorsement |
| What happened since? | Retrieve citing papers, newest first; read their uses of the seed | Subsequent applications, challenges, or extensions; citation counts do not establish quality |
| What other vocabulary is used? | Combine keyword/exact search, semantic descriptions, and topic hierarchy | Related candidates; similarity does not establish identical constructs |
| Is a solution/model already available? | Search proposed output, mechanism, synonyms, and adjacent fields | Prior approaches that may narrow the contribution; absence is search-bounded |
| What could challenge the premise? | Search alternative mechanisms, null/mixed findings, critiques, unsuccessful interventions | Competing explanations from content; neither citation nor sentiment can substitute for reading |
| Is a context neglected? | Compare targeted searches, then inspect actual study populations/settings | Possible coverage differences; affiliations are not research sites |
| What should be read next? | Balance review/foundational/recent/competing/method sources | A purposeful reading list, not simply the most-cited list |

For **explore**, seek varied experiences and unfamiliar contexts; for **explain**, seek mechanisms and contrasting cases; for **develop**, examine existing interventions, requirements, and evaluation criteria; for **describe**, examine components, relationships, and competing models. These are discovery orientations, not metadata filters for ABC paradigms.

## Exploit the graph without mistaking it for evidence

1. **Normalise the seed.** Prefer DOI; preserve OpenAlex ID, title, authors, date, type, source, and available access locations. Title matching needs human-readable verification, especially for dissertations and versions without DOI. Do not automatically merge approximate title matches or preprints and journal versions with different IDs/DOIs.
2. **Follow three neighbourhoods.** References point backward, citing works point forward, related works are algorithmic candidates. The helper records directed citation edges and separately labels related edges. Selection by API order or recency is a sampling bias, so report the cap.
3. **Cross boundaries.** Read `topics` and `primary_topic` with their subfield/field/domain; search a neighbouring topic and alternative construct names. Current topics supersede legacy concepts. Keywords and semantic similarity can reveal terminology absent from the seed. Topic scores do not classify philosophy, methods, or ABC positions.
4. **Explore people and places purposefully.** Author IDs/ORCID can uncover related programmes of work, institutional IDs/ROR can clarify affiliations, and source IDs/ISSN can find relevant venues. Verify identities and avoid mistaking name matches for the same author. Funder and award links may reveal connected projects or practical priorities, but not what findings are true. Avoid allowing one author, institution, journal, country, or funder to dominate the shortlist by accident.
5. **Map a bounded corpus.** Group by year, topic, source, author, institution, or funder only when the result informs a decision. Record the corpus/search/filters and paging limits. Multi-valued fields can count a work in multiple groups, so group totals need not sum to the corpus count. Source/affiliation country and language are coverage indicators, not study population/context. Changes in counts can reflect indexing, not research growth alone.
6. **Connect papers beyond direct citations.** When useful, compare shared references (bibliographic coupling) or shared citing works (co-citation) within the retrieved set. Label these as computed relationships and state the truncated neighbourhood. Do not invent a native endpoint or infer theoretical agreement from shared citations.
7. **Inspect evidence.** Retrieve selected abstracts/full text, including methodological and contrary work. For citations, quote or paraphrase only the content actually read. Record retractions/versions and verify consequential claims with the publisher or repository when metadata is unclear.

Do not filter all discovery to open access: that would bias the map. Keep inaccessible but relevant records, label access limits, and use accessible material for claims. Include relevant theses, books, chapters, and conference papers; do not assume every indexed work is peer reviewed. For education, regional research and non-English terminology may matter. Supplement OpenAlex with an available discipline-specific source when coverage is demonstrably weak.

## Consensus integration and fallbacks

Discover available Consensus tools. Use `search(query)` for candidates and `fetch(id)` before citing a result. A fetched paper record provides verification/abstract metadata, not proof of having read full text. Use supported filters only after inspecting tool documentation. Match into OpenAlex by DOI; if absent, compare title, authors, and year. Retain both provenance trails and canonical links.

If Consensus is unavailable, continue with OpenAlex or supplied text. If the OpenAlex API is unavailable, use an available connector/browser or provide explicitly unexecuted queries. Do not substitute fabricated results. When full text is missing, ask for it only if necessary; otherwise keep the relevant assessment provisional. If the same question has already been addressed, discuss replication, a new context, comparison, mechanism, or a different output with the researcher; do not manufacture a gap.

## Bundled helper

Run from the skill folder with `python3 scripts/openalex.py …`; there are no third-party Python dependencies. All modes return JSON, with a non-zero exit code for failures. `get`/`list` support works, authors, topics, sources, institutions, publishers, and funders. A neighbourhood contains one seed and a capped one-hop expansion; it does not recurse.

```sh
# Identity and title discovery
python3 scripts/openalex.py get works '10.3102/0013189X032001005'
python3 scripts/openalex.py list works --search 'design based research online learning' --per-page 5
python3 scripts/openalex.py list works --exact 'design-based research' --per-page 5

# Different vocabulary: semantic candidates, max 50 and one page
python3 scripts/openalex.py list works --semantic 'How students use conflicting peer feedback to revise designs in online studios' --per-page 10

# One-hop references, related works, and recent citing works (25 each by default)
python3 scripts/openalex.py neighbourhood W2741809807 --limit 10 --max-requests 6

# Inspect topics via get, then replace T_ID with the actual returned ID.
python3 scripts/openalex.py list works --filter 'topics.id:T_ID' --group-by publication_year

# Validate/translate OQL without executing; --execute validates first and retrieves results.
python3 scripts/openalex.py oql 'works where year is (2024) group by type'
python3 scripts/openalex.py oql 'works where year is (2024) group by type' --execute --per-page 5

# Download a selected work whose has_content supports this format.
python3 scripts/openalex.py content W2741809807 --format pdf --output seed.pdf
python3 scripts/openalex.py content W2741809807 --format grobid_xml --output seed.xml
```

IDs in examples illustrate syntax, not recommendations for an ABC project. For reproducibility, save JSON outputs in the research workspace, not inside the installed skill. Use `--cache-dir work/openalex-cache` for reusable metadata; `--refresh` bypasses it. Cached responses retain their original retrieval timestamps. The content mode does not cache; it refuses to overwrite a file. Create output parent directories first.

Common controls: `--max-requests 12` (includes retries and validation), `--max-pages 1`, `--per-page 25`, `--timeout 20`, `--retries 2`. Raise bounds deliberately, never silently pursue a whole graph. Helper hard caps are 50 requests, 20 pages, and 100 rows per page. Semantic search is works-only, <=2,000 characters and <=50 results; the helper rejects incompatible sorting/grouping and unsupported citation/country filters. Pace sequential helper invocations too: semantic requests may be at most one per second. OQL execution returns raw OpenAlex grouping structures for advanced calculations; inspect the actual envelope rather than assuming all calculations are simple counts.

JSON includes `records`, `groups`, `pages`, `api_total`, `truncated`, `failures`, `provenance`, and request settings. `pages` preserve API metadata, including cost and translated queries when supplied. `api_total` is the API match count, not the count read; `record_count` is the deduplicated retrieved count. `truncated` marks page/cap limits, incomplete retrieval, or failures; inspect it even if the process exits successfully. A semantic result set is ranked discovery, never an exhaustive corpus. `meta.count` in a grouping response counts entities, not total groups. Citation count and group count are not evidence of an effect or a gap.

## Authentication, usage, and full text

Official documentation checked 14 October 2026; verify current rules when usage assumptions matter. Basic keyless API queries are available, but cursor paging after the first page requires a key. A free account raises the daily usage allowance. Read usage headers, `meta.cost`, the `/rate-limit` endpoint or account dashboard; do not assume unlimited free access. Use an existing environment variable `OPENALEX_API_KEY`; never put a key in command arguments, logs, cache files, or chat. If no key is configured, use bounded keyless discovery or explain the limitation. Never purchase usage or change an account as part of this skill.

The helper uses bearer authentication, request pacing, short bounded retries, response-size limits, and refusal of redirects. Interrupted HTTP responses are retried within those same limits; exhausted incomplete reads return `incomplete_response` and retain any earlier retrieved pages. A long `Retry-After`, exhausted quota, authentication failure, or network failure becomes an explicit failure. Do not repeatedly retry a daily-budget failure; continue with cached/uploaded material or wait for the next authorised session. Citation batches use at most 100 IDs. OQL grouping is determined from validated query structure or response information, not words appearing in a search phrase.

Full text: inspect `has_content`, `content_urls`, `best_oa_location`, and `locations`. Prefer accessible publisher/repository text where practical; content API downloads are metered. PDF and TEI XML availability differ. The helper verifies PDF/XML format and bounded decompression, saves only a selected file, and returns its hash. PDFs retain their original copyright; OpenAlex metadata licensing does not grant rights to redistribute articles.

GROBID XML may contain extraction errors and older wrapper structures; inspect sections/references and corroborate consequential passages in the PDF. Scanned PDFs may need OCR; do not interpret empty extraction as absent content. This helper downloads XML; it does not claim to perform reliable section extraction.

Snapshots, full database mirroring, CLI bulk downloads, and daily sync are useful at institutional scale but unnecessary for a normal ABC workshop. If a researcher explicitly needs a large corpus, plan a separate reproducible retrieval task with justified coverage and usage bounds.

## Maintained official references

- [Authentication and limits](https://help.openalex.org/api/authentication/)
- [Search](https://help.openalex.org/api/search/) and [semantic search](https://help.openalex.org/api/semantic-search/)
- [Citation recipes](https://help.openalex.org/how-to/api-recipes/)
- [Work attributes](https://help.openalex.org/data/works/attributes/)
- [Grouping](https://help.openalex.org/api/grouping/)
- [OQL translation, validation, and execution](https://help.openalex.org/api/oql/)
- [Full-text products and limitations](https://help.openalex.org/access/fulltext/)
- [Usage costs](https://help.openalex.org/access/example-costs/)

Consult these selectively if an endpoint changes; do not copy an API manual into every session.

# 采集状态、robots 404 与证据链收口

## Problem Statement

当前 Scrapy 采集项目已经能够被发现、加载并回放 fixture，但采集结果仍不能稳定表达真实业务含义。数据完整但当前暂不使用的记录可能被写成 `blocked`，robots 404 的访问事实可能被误当成采集失败，记录级权利字段可能被来源级默认值覆盖，招聘候选可能缺少来源关系和地点关系，真实 Spider 与 Pipeline 接线也还没有被项目级回放完整证明。

这会让采集库同时出现以下问题：数据完整但暂缓使用的记录被误计为失败，应该保留的候选被错误阻断，来源和地点关系丢失，权利字段与来源声明不一致，验收文档也无法清楚解释每条记录为什么进入或没有进入下一阶段。

同时，`nongmuhr` 的详情结构已经与来源文档不一致，`aqsc-moa` 和 `cnipa` 仍只有 fixture 与骨架验证。继续在未验证的结构上声明 live 成功，会把文档错误、解析错误和框架接线错误混在一起，掩盖真实缺口。

## Solution

把采集候选状态、访问事实、详情 URL 规则、权利字段优先级、招聘关系写入、项目级 Scrapy 回放和 live 证据归档收口为同一套可验证契约。

采集候选状态固定为 `candidate`、`deferred` 和 `blocked`。数据完整且可以进入转换器时写 `candidate`。数据完整但当前暂不转换或发布时写 `deferred`，并记录原因。只有数据不完整、解析失败、权利不明或访问被明确禁止时才写 `blocked`。robots 404 记录为访问事实 `not-found`，允许 raw、stage 和候选写入，候选状态写 `deferred`，原因写 `robots:not-found`，但不因此获得业务发布授权。

没有直接详情 URL 时，使用长期承载页 URL 和非空 locator 回溯记录。这类记录可以进入采集候选、业务实体和发布审核，但不得把承载页写成 `detail_url_status=direct`，也不得把承载页伪装成详情 URL。

来源级权利字段从来源注册表注入，Item 的权利字段默认不预填。记录级显式值优先，包括显式 `False`。招聘来源必须写入岗位主实体、岗位来源关系和岗位地点关系。项目清单只从来源注册表派生，不维护第二份手写清单。项目级 fixture 回放必须经过真实 Spider、middleware、Pipeline 和共享运行时，至少对 `ihchina`、`aqsc-moa` 和 `cnipa` 使用真实 Scrapy 运行入口。

`nongmuhr` 以真实站点重新校验为准。先抓取真实列表和详情，记录实际选择器、HTTP 结果、样本和字段，再更新来源文档、解析器和 fixture。`aqsc-moa` 与 `cnipa` 本轮继续保留 fixture 和骨架验收，下一阶段必须补 live 文件小样本。

## User Stories

1. As a data engineer, I want candidate records to use only `candidate`, `deferred`, and `blocked`, so that collection state has one unambiguous meaning across all projects.
2. As a data engineer, I want complete records that are temporarily not converted to be written as `deferred`, so that temporary business deferral is not reported as failure.
3. As a data engineer, I want missing fields, parse failures, unknown rights, and explicit access denial to remain `blocked`, so that real defects are not hidden as deferred data.
4. As a data engineer, I want robots 404 to be recorded as `not-found` while raw, stage, and deferred candidates continue to be written, so that a missing robots file does not stop collection.
5. As a compliance reviewer, I want robots 404 to remain distinguishable from explicit permission, so that collection permission is not confused with publication authorization.
6. As a compliance reviewer, I want 403, 5xx, unknown robots, explicit Disallow, login, captcha, and paywall boundaries to remain true blocks, so that permissive collection does not weaken access controls.
7. As a data engineer, I want the runtime to preserve the actual candidate status and reason returned by admission, so that a record written as `deferred` is not reported as successfully written as `candidate`.
8. As an operator, I want run reports to count `candidate`, `deferred`, `blocked`, `skipped`, and `failed` separately, so that data volume and failures can be audited independently.
9. As a data engineer, I want a record without a direct detail URL to use a long-term carrier page and a non-empty locator, so that attachment rows and dynamic query results remain traceable.
10. As a front-end user, I want source links to open a stable carrier page when no single detail page exists, so that I can verify the original context.
11. As a data engineer, I want `detail_url_status=missing` to remain missing, so that automation cannot silently turn a carrier page into a direct detail URL.
12. As a reviewer, I want records with a carrier page and locator to be eligible for candidate, business entity, and publication review, so that useful attachment-derived data is not discarded.
13. As a data engineer, I want Item rights fields to start empty, so that absence of a record-level value is distinguishable from an explicit false value.
14. As a data engineer, I want source-level rights defaults to be injected from the source registry, so that every source has one authoritative default.
15. As a data engineer, I want record-level rights values to override source defaults, including an explicit `False`, so that per-record evidence is not lost.
16. As a compliance reviewer, I want attribution and rights evidence to be preserved on main entities and source relations, so that published facts remain traceable.
17. As a recruitment data user, I want every job candidate to have a source relation row, so that multiple source URLs for the same job are retained.
18. As a recruitment data user, I want every job candidate to have location relation rows, so that multi-region postings are not collapsed into one text field.
19. As a data engineer, I want `nzrc` and `nongmuhr` job relations to be idempotent by natural key, so that repeated fixture or live runs do not duplicate source or location rows.
20. As a source maintainer, I want `nongmuhr` to be revalidated against the real site before its parser changes, so that implementation and documentation follow observed structure rather than stale selectors.
21. As a source maintainer, I want the real `nongmuhr` list and detail samples to record URL, time, HTTP status, selectors, field values, and blocking evidence, so that later parser changes remain reproducible.
22. As a source maintainer, I want `nongmuhr` to remain blocked until real detail fields are confirmed, so that HTTP 200 is not reported as a successful parse.
23. As a file-source maintainer, I want `aqsc-moa` and `cnipa` to retain their current fixture and skeleton acceptance, so that this iteration does not conflate framework migration with full file parsing.
24. As a file-source maintainer, I want the next live sample for `aqsc-moa` to cover XLSX download, sheet and row locator, carrier URL, missing detail status, file hash, and deferred candidate behavior, so that workbook-derived records are traceable.
25. As a file-source maintainer, I want the next live sample for `cnipa` to cover PDF download, page and row locator, carrier URL, missing detail status, file hash, and deferred candidate behavior, so that announcement-derived records are traceable.
26. As a developer, I want `ihchina` fixture replay to run through a real Scrapy process, middleware, Pipeline, and collection runtime, so that tests prove project wiring rather than only parser functions.
27. As a developer, I want `aqsc-moa` and `cnipa` fixture replay to use the same real Scrapy path, so that file projects are not validated only through synthetic Item construction.
28. As a developer, I want the empty `ihchina` missing-detail test replaced with a behavior test, so that the test names and assertions describe the same external outcome.
29. As a developer, I want the executable project set to be derived from the source registry, so that project discovery cannot drift from the source truth.
30. As a developer, I want project discovery to compare the derived set with actual project directories and fail on mismatch, so that an extra or missing project is detected mechanically.
31. As an auditor, I want live evidence metadata archived outside temporary directories, so that counts, URLs, status codes, hashes, candidate totals, failure summaries, and block reasons remain reviewable.
32. As an auditor, I want original copyrighted content to remain outside the public repository while hashes and metadata are retained, so that evidence review does not create a publication risk.
33. As an operator, I want legacy real-time entry points removed or archived after all formal sources switch, so that Scrapy remains the only real-time collection path.
34. As an operator, I want rollback to use a prior application version and database snapshot rather than a permanent dual-writer route, so that duplicate writes are not introduced during cutover.
35. As a reviewer, I want failures and deferrals to be explainable per record, so that each run can state what was collected, what was deferred, what was blocked, and why.

## Implementation Decisions

### Candidate State Contract

The collection candidate state is exactly `candidate`, `deferred`, or `blocked`.

- `candidate`: the record has enough normalized source evidence to enter the converter.
- `deferred`: the record is complete but is not being converted or published in the current business window. The reason must be stored.
- `blocked`: the record has a real defect or access boundary, including missing required data, parse failure, unknown rights, or explicit access denial.

`skipped` may remain a run-report accounting outcome, but it must not be written as a persisted candidate state.

Admission must return a structured decision containing allowed or rejected outcome, candidate status, and reason. The collection runtime must persist and report that actual status. It must not rewrite a valid `deferred` Item to `blocked` merely because the record is not eligible for conversion.

### Access Facts and Robots

Robots results remain access facts: `allowed`, `disallowed`, `not-found`, and `unknown`.

For `not-found`, raw, stage, and candidate writes are allowed. The persisted candidate status is `deferred`, and the reason is `robots:not-found`. A robots 404 does not establish publication permission and does not bypass rights review.

Explicit Disallow, 403, 5xx, unknown rules, login requirements, captcha, and paywalls remain true blocks. A blocked request still retains the available raw evidence and a reason.

### URL and Locator Contract

A direct detail URL and a carrier page URL are different concepts.

- A direct detail URL identifies one record and uses `detail_url_status=direct`.
- A carrier page URL is a long-term announcement, dataset, query-detail, or context page that can reopen the record. It uses `long_term_url`.
- A locator identifies the row, page, sheet, anchor, or JSON path inside the carrier page or attachment.

When no direct detail URL exists, `detail_url` is empty and `detail_url_status=missing`. The carrier page and locator must both be present. Such a record can enter a candidate, a business entity, and publication review. Automation must not copy the carrier URL into `detail_url` or change `missing` to `direct`.

Temporary signed download URLs remain fetch evidence only. They do not become long-term detail or carrier URLs.

### Rights Field Precedence

Item rights fields begin unset. Source-level defaults are read from the source registry. Record-level values take precedence when they are not `None`. Explicit `False` values must be preserved.

The same rule applies to attribution requirements, attribution text, rights status, and rights evidence URL. Boolean merging must be based on presence, not on logical OR.

### Job Relations

`nzrc` and `nongmuhr` candidates must write the job entity, job source relation, and job location relation in one idempotent operation.

- A job source relation preserves the source item identity, source URL, long-term URL, detail URL status, locator, rights fields, and primary flag.
- A job location relation preserves the raw location text and normalized province, city, and county values when available.
- Repeated fixture or live processing must use the existing natural keys and must not duplicate relations.
- A failed relation write must not leave a partially published or apparently complete candidate.

### Nongmuhr Revalidation

The current `#project_L` selector is not authoritative. The real site must be checked before implementation changes.

The validation sequence is:

1. Fetch the real list page and at least five real detail pages.
2. Record URLs, retrieval times, HTTP statuses, content types, selectors, extracted fields, and blocking evidence.
3. Update the source document to distinguish historical claims from current observations.
4. Update the parser, replay fixture, and project tests to match the verified page structure.
5. Rerun the list and detail sample and record blocked or successful results without converting HTTP 200 into parse success.

If the real structure cannot be confirmed or fields remain unstable, the source stays blocked with a stated release condition.

### File Source Scope

`aqsc-moa` and `cnipa` keep their fixture and skeleton scope in this iteration. Their next live sample is a required follow-up, not evidence already completed.

The live sample must cover:

- announcement or carrier page discovery;
- attachment download and 100MB limit behavior;
- XLSX or PDF parsing;
- file name, MIME type, byte size, and SHA-256;
- sheet and row locator for XLSX;
- page and row locator for PDF;
- temporary signed URL handling;
- `detail_url_status=missing`;
- `deferred` candidate behavior when the record is complete but not yet converted.

### Project-Level Replay Seam

The highest existing test seam is the source registry plus shared collection contract. The second seam is a project-level replay that starts from the project entry point and reaches raw, stage, and candidate writes.

At minimum, `ihchina`, `aqsc-moa`, and `cnipa` must use a real Scrapy process for fixture replay. Their tests must pass through Spider, downloader or spider middleware, Item Pipeline, and the collection runtime, then assert the database effects and candidate status.

All eight projects must continue to have an independent fixture replay entry. A test may use a site parser directly only as a lower-level unit test, not as proof that the project Pipeline is wired correctly.

The `ihchina` missing-detail test must construct a record with no usable direct detail URL and assert the observable outcome: raw and stage evidence are written, the candidate is not a publishable `candidate`, and the reason is recorded. A Spider name assertion is not sufficient.

### Source Registry as Sole Project Truth

The source registry is the sole source for source identity, enabled state, run modes, access, status, rights, and project membership.

Project discovery must derive the executable project set from the registry, compare it with the actual project directories, and fail when either side has an extra or missing project. No second handwritten project ID list is allowed.

An excluded, deferred, disabled, or runtime-only source must not appear as an executable project.

### Live Evidence Archive

Live evidence must be archived in a stable repository-adjacent evidence location or a documented stable output directory. Temporary paths alone are not sufficient.

The archive index must retain at least:

- source ID;
- source, list, detail, carrier, and attachment URLs as applicable;
- retrieval time;
- HTTP status and content type;
- response or file hash;
- raw, stage, candidate, deferred, blocked, failed, and skipped counts;
- failure summary and blocking reason;
- pointer to the review or acceptance record.

The public repository must not include raw copyrighted full text, credentials, cookies, signed URLs, or personal data. Metadata and hashes are sufficient for audit.

### Legacy Entry Retirement

The target is one real-time Scrapy write path, not a permanent dual-writer design.

Before retirement, each formal source must complete fixture replay, live canary where applicable, source review, and an isolated-database check. Once all formal sources are switched, the legacy real-time entry is removed or archived and the migration documents stop describing a live dual-entry route.

Rollback uses a prior application version and a database snapshot. It does not restore a permanent second live writer.

## Testing Decisions

Good tests assert externally observable behavior: persisted raw and stage rows, candidate status and reason, source and location relations, run report counts, URL and locator fields, imported modules, and generated evidence metadata. Tests should not lock private method names, SQL formatting, selector internals, or log wording.

The shared contract tests must cover:

1. All three candidate states round-trip through admission and persistence.
2. `deferred` is not reported as `candidate`.
3. `blocked` is used for missing fields, parse failure, unknown rights, and explicit access denial.
4. Robots `not-found` produces a deferred candidate with `robots:not-found`.
5. Robots `disallowed`, `unknown`, 403, and 5xx remain blocked.
6. Source rights defaults are applied when Item values are absent.
7. Record-level rights values override source defaults, including explicit `False`.
8. Missing detail status requires a non-empty carrier URL and locator.
9. A carrier URL is never written as a direct detail URL.
10. `nzrc` and `nongmuhr` write one job source relation and the expected location relations on first run and do not duplicate them on replay.
11. Project discovery derives the expected project set from the registry and rejects extra or missing directories.
12. Scrapy project imports and runtime tests prove that no business database is opened and no converter is called.

Project tests must cover:

1. Each of the eight projects can be discovered and loaded.
2. Each project has a project-level fixture replay entry.
3. `ihchina`, `aqsc-moa`, and `cnipa` replay through a real Scrapy process and assert raw, stage, and candidate outcomes.
4. `nongmuhr` has a regression fixture based on the real verified structure.
5. `aqsc-moa` and `cnipa` fixture tests assert file hashes, locators, carrier URLs, and missing detail status.
6. The `ihchina` missing-detail regression asserts stage-only or deferred behavior with an audit reason, not just a Spider name.

Live evidence tests and manual checks must cover:

1. `nongmuhr` real list and at least five detail pages before a parser success claim.
2. The five robots 404 sources write deferred candidates with the expected counts after the code change.
3. Live reports separate deferred, blocked, failed, and successful counts.
4. Archived evidence contains stable metadata and does not contain secrets or copyrighted full text.

Prior art is the existing source registry tests, schema contract tests, fixture replay tests, admission tests, publication gate tests, Scrapy runtime integration tests, and source review records. Reuse their external behavior assertions rather than duplicating implementation-specific checks.

## Out of Scope

- Do not change the business database schema, back end, front end, or publication UI in this iteration.
- Do not make Scrapy Pipeline write the business database or call the converter.
- Do not define publication as the same state as collection candidacy.
- Do not add a permanent dual-writer routing layer.
- Do not execute full historical collection for any source.
- Do not claim `aqsc-moa` or `cnipa` live success from fixture or skeleton tests.
- Do not add new formal sources or promote source-expansion candidates.
- Do not scrape login-only, paid, captcha-protected, personal-resume, or explicitly disallowed content.
- Do not archive raw copyrighted full text, personal data, credentials, cookies, or signed URLs in the public repository.
- Do not change ADR 0001, ADR 0002, or ADR 0003 in this iteration.
- Do not create child issues, modify issue acceptance scope, or close any issue as part of implementation.

## Further Notes

### Upstream Documentation Conflicts

1. The migration plan currently labels itself `implemented`, while the integration validation is `blocked` because five robots 404 sources still write `blocked` and `nongmuhr` still fails parsing. The plan must be read as an implementation status, not as a live acceptance claim.
2. The `nongmuhr` source document records an approved-with-gaps source status, but its own structure-validation section is blocked and its historical `#project_L` selectors are explicitly non-authoritative. The source status and structure-validation status must be stated separately.
3. The current validation document retains historical `blocked` counts and target `deferred` counts in the same row. After this iteration, it must record the actual rerun result, not a mix of current and target behavior.
4. ADR 0003 still contains a scope sentence describing a documentation-only iteration, although Scrapy projects have since been implemented. That sentence is historical and must not be used to block this iteration.
5. The collection std schema documents a historical `publish_status` field alongside the actual `candidate_status`. Candidate behavior must be determined only from `candidate_status`; `publish_status` remains a compatibility field.

### Assumptions

- The source registry can identify the eight executable projects through declared Scrapy run modes and executable source state. The implementation must derive from that registry, not copy a second list.
- A record with a stable carrier page and a locator is complete enough for candidate, business entity, and publication review.
- Robots 404 permits collection under the project owner's decision but never supplies publication permission.
- A fixture replay is useful only after it reaches the same persistence boundary as a real project run, unless it is explicitly labelled a lower-level unit test.

### Completion Definition

This iteration is complete when the three-state candidate contract is enforced, robots 404 produces deferred candidates with recorded evidence, rights precedence is correct, job relations are idempotent, project discovery has one source of truth, the named projects replay through real Scrapy, the empty `ihchina` test is replaced, `nongmuhr` has current real-site evidence, file-source follow-up scope is explicit, and live evidence metadata is archived for review.

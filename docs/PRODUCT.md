# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary user is a rural learner or job seeker in Guangdong. Their situation includes uneven digital literacy, frequent mobile-phone access, and a need for practical agricultural, e-commerce, craft, policy, and employment information. Some users use Cantonese, Hakka, or Teochew dialects.

Teachers, enterprises, government staff, and super administrators are supporting roles. They provide instruction, jobs and procurement demand, policy information, governance, and platform administration; their workflows exist to support learner success rather than as the primary optimization target.

## Product Purpose

粤乡智匠 is a Guangdong-localized prototype for rural talent enablement. It uses AI-assisted training and localized resources to help learners practice agricultural skills, e-commerce operations, and traditional craft skills, then connect those skills to employment, procurement, policy, and community opportunities.

Success at this stage is a coherent, testable demo: the learner can understand the core learning-to-employment journey and operate the main role workflows without the implementation having to be production-hardened.

## Positioning

The product combines AI-guided practical training with Guangdong-specific agricultural products, intangible-heritage crafts, dialect support, rural employment, agricultural procurement, and policy information. A generic course platform could copy the training shell, but not this localized rural-employment and supply-chain context as an integrated product story.

## Operating Context

The current authority is a prototype. The repository should be evaluated as a demo or course deliverable, not as a production service.

Current demo stack: a Flask backend with SQLite, an independent Vue 3 + Vite frontend under `frontend/`, legacy vanilla HTML/CSS/JavaScript pages at the repository root, and a Vercel serverless entry. Run the backend with `python run.py`, build the active frontend from `frontend/` with `npm run build`, and run backend tests with `python -m unittest test_app.py`.

Demo accounts are intentional and non-production data. AI features expect `AI_API_URL`, `AI_API_KEY`, and `AI_MODEL` through local configuration and may use fallbacks when unavailable. SQLite storage is local in development and non-persistent under Vercel.

## Capabilities and Constraints

Confirmed product concept:

- Six learner-facing domains: agricultural skills, e-commerce operations, traditional craft inheritance, virtual training sandbox, localized resources, and employment/supply-chain connection.
- Five roles: student, teacher, enterprise, government, and super administrator.
- AI-assisted agricultural, e-commerce, craft, diagnosis, and teaching-report workflows.
- Community discussion, notifications, messages, ratings, jobs, applications, procurement, policies, news, cases, and administrative review.

Current technical constraints:

- The prototype uses SQLite and is not designed for distributed production use.
- Vercel deployment does not provide durable SQLite storage; production use would require an external database.
- AI output may be inaccurate, and service behavior depends on external API availability and configuration.

The requirements document in `docs/粤乡智匠——需求规格说明书.md` defines the intended scope. It is directional context, not proof that every requirement is implemented; implementation status must be verified in code before claiming a capability.

## Brand Commitments

The product name is 粤乡智匠. Content and primary interface copy are zh-CN.

For active frontend styling, the user has designated `ark-ui-skill` as the reference with `family=ark` and `depth=maximal`. UI work must use the original Vue implementation and avoid protected Hypergryph/Arknights/Endfield logos, artwork, UI screenshots, or assets.

## Evidence on Hand

- Requirements, personas, feature scope, data model, and acceptance criteria: `docs/粤乡智匠——需求规格说明书.md`.
- Existing Flask routes and APIs: `app.py`.
- Data initialization, seeded demo content, role handling, and persistence helpers: `database.py`.
- Current web pages and interaction code: `index.html`, `admin.html`, `teacher.html`, `enterprise.html`, `government.html`, `case-detail.html`, `script.js`, `portal.js`, and `js/core.js`.
- Active learner home implementation: `frontend/src/`, with the adapter fallback in `frontend/src/api/adapters/home.ts` and design tokens in `frontend/src/styles/tokens.css`.
- API/page tests: `test_app.py`.

There is no confirmed user research, production telemetry, validated accessibility audit, business case, testimonial, or deployment evidence on hand. Do not fabricate these.

## Product Principles

1. Optimize first for the rural learner's practical journey from training to employment.
2. Make Guangdong-localized content, crops, crafts, dialects, policies, and cases central rather than decorative.
3. Favor hands-on practice and clear next actions over abstract courseware.
4. Keep mobile, low-digital-literacy, and mixed-language access in mind from the start.
5. Preserve prototype honesty: label demo data and unknowns instead of presenting the demo as production.

## Accessibility & Inclusion

Target users include mobile-first users and people with varying digital literacy. Primary accessibility goals are readable zh-CN content, responsive layouts from small mobile through desktop, clear states and feedback, keyboard/ARIA support, and meaningful dialect support.

The repository does not yet provide evidence that these goals are met; they must be verified rather than assumed.

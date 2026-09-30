Technology Stack + SDK/App Flow
The stack below follows the architecture in your uploaded specificaƟon: Python SDK, FastAPI,
staƟsƟcal anomaly detecƟon, GitPython/AST fault localizaƟon, LLM patch generaƟon, Docker
sandboxing, mutaƟon tesƟng, GitHub integraƟon, PostgreSQL/pgvector, and React dashboard.
1. Final Technology Stack
Layer Technology Purpose
Web App React + TypeScript + Vite SaaS dashboard
UI Tailwind CSS Interface
Charts Recharts Incident/trust analyƟcs
RealƟme WebSockets / SSE Live sandbox + recovery updates
API Python + FastAPI Main control plane
ValidaƟon PydanƟc API/data validaƟon
ORM SQLAlchemy PostgreSQL access
MigraƟons Alembic DB migraƟons
Async Jobs Celery Long-running recovery jobs
Queue Redis Job broker/cache
Database PostgreSQL Core applicaƟon data
Vector Search pgvector Similar incident retrieval
SDK Python package ApplicaƟon monitoring
AI Layer OpenAI / Anthropic API abstracƟon Diagnosis + patch generaƟon
Code Analysis Python ast FuncƟon/code structure
Git Analysis GitPython Commits/blame/diffs
Patch Parsing unidiff Unified diff handling
Sandbox Docker Isolated code execuƟon

---

Layer Technology Purpose
MutaƟon TesƟng mutmut MutaƟon generaƟon/execuƟon
GitHub GitHub App + REST API Repo/PR automaƟon
Storage S3 / Cloudflare R2 Logs and arƟfacts
Observability OpenTelemetry Internal plaƞorm tracing
Logging Structured JSON logs Debugging/audit
TesƟng pytest Backend/SDK
Frontend TesƟng Vitest + Playwright UI tesƟng
Deployment Docker Consistent environments
EvaluaƟon QuixBugs → Defects4J Research validaƟon
The source architecture specifically recommends Python for the SDK, FastAPI for the backend,
GitPython/AST for localizaƟon, LLM APIs for patch generaƟon, Docker for the sandbox,
mutmut/cosmic-ray for mutaƟon tesƟng, PyGithub/GitHub REST, PostgreSQL/pgvector, and
React/Next.js for the dashboard.
2. High-Level Architecture
┌───────────────────────┐
│ CUSTOMER APP │
│ Flask / FastAPI / etc │
└───────────┬───────────┘
│
Recovery SDK
│
▼
┌───────────────────────┐
│ INGESTION API │

---

│ FastAPI │
└───────────┬───────────┘
│
▼
┌───────────────────────┐
│ INCIDENT ENGINE │
│ Fingerprint + Detect │
└───────────┬───────────┘
│
▼
┌───────────────────────┐
│ FAULT LOCALIZER │
│ AST + Git + Stacktrace│
└───────────┬───────────┘
│
▼
┌───────────────────────┐
│ PATCH GENERATOR │
│ LLM Layer │
└───────────┬───────────┘
│
Patch A/B/C
│
▼
┌───────────────────────┐
│ JOB QUEUE │

---

│ Redis │
└───────────┬───────────┘
│
▼
┌───────────────────────┐
│ SANDBOX WORKER │
│ Celery │
└───────────┬───────────┘
│
▼
┌─────────────────┐
│ Docker Sandbox │
│ │
│ Apply Patch │
│ Install Deps │
│ Run Tests │
└───────┬─────────┘
│
▼
┌───────────────────────┐
│ TRUST ENGINE │
│ │
│ MutaƟon TesƟng │
│ Evidence Analysis │
│ Confidence Score │
└───────────┬───────────┘

---

│
▼
┌───────────────────────┐
│ DECISION ENGINE │
└───────────┬───────────┘
│
┌─────────────┴─────────────┐
▼ ▼
AUTO MERGE HUMAN REVIEW
│ │
└─────────────┬─────────────┘
▼
GitHub Pull Request
3. The Product Has 2 Major Technical Layers
Your source architecture is very clear about this.
Layer 1 — Recovery Pipeline
Monitor
↓
Anomaly Detector
↓
Fault Localizer
↓
Patch Generator
↓
Sandbox

---

↓
Decision
↓
GitHub
This is the plaƞorm users interact with.
Layer 2 — Trust Engine
Patch
↓
MutaƟon TesƟng
↓
Killed/Survived
↓
MutaƟon Score
↓
Confidence
This should be built as a separate service/API, because your architecture specifically defines it
as an independently callable trust layer.
4. SDK Flow
The SDK is what the customer installs in their applicaƟon.
Example:
pip install recovery-sdk
Then:
from recovery_sdk import monitor
monitor.start(

---

project_id="proj_123",
environment="producƟon"
)
For FastAPI:
from fastapi import FastAPI
from recovery_sdk.integraƟons.fastapi import RecoveryMiddleware
app = FastAPI()
app.add_middleware(
RecoveryMiddleware,
project_id="proj_123"
)
5. SDK Internal Flow
CUSTOMER APPLICATION
│
▼
ExcepƟon / Failure
│
▼
┌────────────────┐
│ SDK Capturer │
└───────┬────────┘
│
┌─────────┼─────────┐

---

│ │ │
▼ ▼ ▼
ExcepƟon Stack Context
Type Trace
│ │ │
└─────────┼─────────┘
▼
Git Commit Hash
│
▼
Event Normalizer
│
▼
Fingerprint Error
│
▼
Local SDK Queue
│
▼
Async HTTP POST
│
▼
Recovery Plaƞorm
The SDK should be non-blocking. Your source architecture specifically calls for asynchronous
delivery so applicaƟon performance isn't unnecessarily affected.

---

6. What the SDK Sends
Example:
{
"project_id": "proj_123",
"environment": "producƟon",
"excepƟon": {
"type": "ZeroDivisionError",
"message": "division by zero"
},
"stack_trace": "...",
"locaƟon": {
"file": "payments/service.py",
"line": 184,
"funcƟon": "calculate_refund"
},
"git": {
"commit": "a91d32f"
},
"request": {
"method": "POST",
"route": "/refund"

---

},
"runƟme": {
"python": "3.12"
}
}
Do not send sensiƟve request bodies or secrets by default.
7. Complete App Flow
Here is the enƟre customer journey.
Step 1 — Customer signs up
User
↓
AuthenƟcaƟon
↓
OrganizaƟon
↓
Create Project
Step 2 — Connect GitHub
Connect GitHub
↓
GitHub App InstallaƟon
↓
Select Repository
↓

---

Select Branch
Example:
my-company/
└── payment-service
8. Step 3 — Configure Project
Customer configures:
Language
Python
Test Command
pytest
Branch
main
Recovery
Enabled
Auto Merge
Enabled
Trust Threshold
90%
9. Step 4 — Install SDK

---

Customer gets:
pip install recovery-sdk
and:
monitor.start(
project_id="proj_123"
)
Now their applicaƟon is connected.
10. Step 5 — Error Happens
ApplicaƟon:
POST /refund
produces:
ZeroDivisionError
SDK captures it.
ApplicaƟon
↓
SDK
↓
Recovery API
11. Step 6 — Incident Engine
Backend receives hundreds of similar events:
ZeroDivisionError
ZeroDivisionError
ZeroDivisionError
ZeroDivisionError

---

...
FingerprinƟng groups them:
INCIDENT #1042
Occurrences:
327
Severity:
HIGH
The anomaly detector determines whether automated recovery should run.
The architecture recommends deduplicaƟon, error-rate analysis and severity classificaƟon here.
12. Step 7 — Fault LocalizaƟon
Stack Trace
↓
payments/service.py
↓
Line 184
↓
calculate_refund()
Then:
AST
+
Git blame
+
Recent commits

---

produce:
Likely Fault:
payments/service.py:184
Recent change:
Commit a91d32
13. Step 8 — Historical Retrieval
Search PostgreSQL + pgvector:
Current Incident
↓
Embedding
↓
Similar incidents
↓
Previous fixes
Example:
Similar Incident #719
Same funcƟon family:
calculate_refund()
Previous resoluƟon:
Boundary validaƟon.
Feed that context to the AI.

---

14. Step 9 — LLM Generates Candidates
The AI gets:
Stack trace
+
FaulƟng funcƟon
+
Relevant source
+
Related tests
+
Git history
+
Historical fixes
It generates:
Patch A
Patch B
Patch C
Each one is a unified diff, rather than a complete source-file rewrite.
15. Step 10 — Sandbox
This is where your PaaS gets interesƟng.
Each patch becomes a separate job.
Patch A
│
▼
Sandbox #001

---

│
┌──────┼──────┐
▼ ▼ ▼
Install Patch Test
│ │ │
└──────┼──────┘
▼
Result
Then:
Patch B
│
▼
Sandbox #002
and:
Patch C
│
▼
Sandbox #003
Every sandbox is isolated and disposable.
16. Sandbox UI
Your product dashboard can show:
RECOVERY / INCIDENT #1042
PATCH A
────────────────────────

---

Sandbox
● Running
Environment
Python 3.12
[✓] Clone Repository
[✓] Install Dependencies
[✓] Apply Patch
[✓] Run Tests
Tests
278 passed
6 failed
Status
REJECTED
Then Patch B:
PATCH B
[✓] Clone
[✓] Install
[✓] Apply
[✓] Tests

---

284 passed
0 failed
Status
PASSED
17. Step 11 — Trust Engine
Patch B now moves into:
Trust Engine
Input:
{
"repo": "...",
"patch_diff": "...",
"test_command": "pytest"
}
The Trust Engine does:
Candidate Patch
↓
Generate Mutants
↓
Run Tests for Each Mutant
↓
Killed / Survived
↓
Calculate MutaƟon Score

---

↓
Combine Evidence
↓
Trust Score
18. Example Trust EvaluaƟon
PATCH B
Tests
284 / 284 ✓
MutaƟon TesƟng
24 mutants generated
22 killed
2 survived
MutaƟon Score
91.6%
Patch Size
Small
Files Changed
1

---

Blast Radius
Low
Historical Similarity
High
────────────────────
TRUST SCORE
91%
RECOMMENDATION
AUTO MERGE
MutaƟon tesƟng is the core differenƟator in your supplied architecture because it tests whether
the test suite actually detects meaningful perturbaƟons around the patch.
19. Step 12 — Decision Engine
Trust Score
│
▼
Policy EvaluaƟon
│
├───────────────┐
▼ ▼
Score ≥ 90% Score < 90%

---

│ │
▼ ▼
Policy Check Human Review
│
▼
SensiƟve File?
│
┌──┴──┐
NO YES
│ │
▼ ▼
Merge Review
Even a 99% score should not override a hard security policy.
20. Step 13 — GitHub PR
AutomaƟcally create:
fix: autonomous recovery for ZeroDivisionError
PR body:
## Autonomous Recovery
Incident:
#1042
Failure:
ZeroDivisionError

---

LocaƟon:
payments/service.py:184
Candidate:
Patch B
Tests:
284/284 passed
MutaƟon Score:
91.6%
Trust Score:
91%
Blast Radius:
LOW
Decision:
AUTO MERGE
21. Step 14 — CI VerificaƟon
AŌer your PR is created:
GitHub
↓
CI

---

↓
Tests
↓
Checks
↓
Recovery Plaƞorm
Your plaƞorm waits for external CI as an addiƟonal signal.
22. Step 15 — Merge
When:
Trust Score ≥ threshold
+
Policy permits
+
Sandbox passes
+
GitHub CI passes
then:
AUTO MERGE
Otherwise:
HUMAN REVIEW
23. Final End-to-End Flow
The enƟre product can be summarized as:
┌─────────────────────────────┐
│ CUSTOMER APP │

---

└──────────────┬──────────────┘
│
Error occurs
│
▼
┌─────────────────────────────┐
│ RECOVERY SDK │
└──────────────┬──────────────┘
│
▼
┌─────────────────────────────┐
│ INGESTION API │
└──────────────┬──────────────┘
│
▼
┌─────────────────────────────┐
│ INCIDENT / ANOMALY ENGINE │
└──────────────┬──────────────┘
│
▼
┌─────────────────────────────┐
│ FAULT LOCALIZER │
│ AST + Git + Trace │
└──────────────┬──────────────┘
│
▼

---

┌─────────────────────────────┐
│ HISTORICAL RETRIEVAL │
│ pgvector │
└──────────────┬──────────────┘
│
▼
┌─────────────────────────────┐
│ LLM PATCH ENGINE │
│ A / B / C │
└──────────────┬──────────────┘
│
▼
┌──────────────┐
│ JOB QUEUE │
│ Redis │
└──────┬───────┘
│
▼
┌─────────────────────────────┐
│ SANDBOX WORKER │
└──────────────┬──────────────┘
│
▼
┌──────────────┐
│ DOCKER │
│ SANDBOX │

---

├──────────────┤
│ Apply Patch │
│ Run Tests │
│ Run Mutants │
└──────┬───────┘
│
▼
┌─────────────────────────────┐
│ TRUST ENGINE │
│ │
│ MutaƟon Score │
│ Evidence │
│ Risk │
│ Confidence │
└──────────────┬──────────────┘
│
▼
┌─────────────────────────────┐
│ DECISION ENGINE │
└──────────────┬──────────────┘
│
┌──────┴──────┐
▼ ▼
AUTO MERGE HUMAN REVIEW
│ │
└──────┬──────┘

---

▼
┌─────────────┐
│ GitHub │
│ PR │
└─────────────┘
24. The cleanest product architecture
I would ulƟmately organize your code into four major domains:
RECOVERY PLATFORM
│
┌──────────────────┼──────────────────┐
│ │ │
▼ ▼ ▼
MONITORING RECOVERY EXECUTION
│ │ │
│ AI + Git Docker
│ │ Sandbox
│ │ │
└──────────────────┼──────────────────┘
▼
TRUST ENGINE
│
▼
DECISION LAYER
│
▼
GITHUB

---

And from a product perspecƟve:
SDK
↓
Monitor
↓
Recover
↓
Sandbox
↓
Trust
↓
Merge
That is the fundamental flow you should keep consistent across the architecture diagram,
backend services, dashboard UX, PRD, pitch deck, and eventual implementaƟon.

---

4. Now the implementaƟon plan
This is the order I would actually build the project.
Do not build the SaaS dashboard first.
Do not start with the Trust Engine first.
Build the underlying recovery loop first.
PHASE 0 — Freeze the Architecture
Before wriƟng code, establish these boundaries:
PLATFORM
│
┌────────────┴────────────┐
│ │
RECOVERY LAYER TRUST ENGINE
│ │
Detect → Localize Patch → Mutate
Generate → Sandbox → Score
Also freeze:
First supported language
Python only.
First repository integraƟon
GitHub only.
First mutaƟon engine
mutmut.
First sandbox technology
Docker.
First frontend

---

React + TypeScript.
This prevents the team from trying to solve 20 problems simultaneously.
PHASE 1 — Build the Broken Demo ApplicaƟon
This is your first actual implementaƟon.
Create a Ɵny Python repository that contains intenƟonal bugs.
Example:
demo-repo/
├── app.py
├── payments.py
├── users.py
├── requirements.txt
└── tests/
├── test_payments.py
└── test_users.py
Put controlled bugs into it.
For example:
def calculate_discount(price, discount):
return price + price * discount
with:
def test_discount():
assert calculate_discount(100, 0.2) == 80
This repository becomes your experimental testbed.
Goal
You should be able to reproduce:
Bug

---

↓
pytest fails
before building anything intelligent.
PHASE 2 — Build the Recovery SDK
Create:
recovery-sdk/
The SDK should iniƟally support:
Python
FastAPI
Flask
but you can start with FastAPI.
The SDK captures:
ExcepƟon
Stack Trace
File
Line
FuncƟon
Git Commit
Environment
Request metadata
Then sends it asynchronously to:
POST /api/v1/events
Deliverable
When your broken demo applicaƟon crashes:
ApplicaƟon

---

↓
SDK
↓
FastAPI
↓
PostgreSQL
you should see the error stored in your plaƞorm.
PHASE 3 — Build the Incident Engine
Now build:
Event
↓
Fingerprint
↓
Deduplicate
↓
Severity
↓
Incident
For example:
327 idenƟcal excepƟons
becomes:
Incident #1042
Occurrences: 327
Add basic anomaly detecƟon using:
EWMA

---

z-score
error frequency
Don't use AI here.
PHASE 4 — Build Fault LocalizaƟon
Input:
Incident #1042
Output:
payments/service.py
calculate_refund()
line 184
Build:
Stack Trace Parser
Find:
file
line
funcƟon
AST Analyzer
Extract:
funcƟon boundaries
classes
imports
control flow context
Git Analyzer
Use:
GitPython

---

for:
git blame
recent commit
changed lines
commit metadata
Deliverable
You should have:
{
"file": "payments/service.py",
"line": 184,
"funcƟon": "calculate_refund",
"recent_change": true
}
PHASE 5 — Build Repository Context Retrieval
Now give the LLM enough informaƟon to reason about the fault.
Do NOT send the enƟre repository.
Build a Context Builder.
Priority:
1. FaulƟng funcƟon
2. Surrounding lines
3. Imports
4. Calling funcƟon
5. Related tests
6. Recent git changes
7. Similar incidents

---

Later add:
pgvector
for historical incident retrieval.
PHASE 6 — Build Patch GeneraƟon
Now integrate the LLM.
Input:
Stack trace
+
Fault locaƟon
+
Source code
+
Tests
+
Git context
+
Historical fixes
Output:
Patch A
Patch B
Patch C
Make the model return unified diffs.
For example:
- return price + price * discount
+ return price - price * discount

---

CriƟcal rule
The LLM should never directly modify the customer's repository.
It only proposes a diff.
PHASE 7 — Build the Sandbox
Now make the project genuinely interesƟng.
Build:
Sandbox Manager
Flow:
Patch
↓
Create Job
↓
Clone Repository
↓
Create Docker Container
↓
Apply Patch
↓
Install Dependencies
↓
Run Tests
↓
Collect Output
↓
Destroy Container

---

Every candidate gets its own sandbox.
Patch A → Sandbox A
Patch B → Sandbox B
Patch C → Sandbox C
PHASE 8 — Build the Sandbox Infrastructure Properly
Do not call Docker directly from random FastAPI endpoints.
Use:
FastAPI
↓
Redis
↓
Celery Worker
↓
Sandbox Manager
↓
Docker
This makes the system asynchronous.
You can then execute:
Patch A
Patch B
Patch C
in parallel where infrastructure allows.
PHASE 9 — Build the Trust Engine
Now begin the main research contribuƟon.

---

Create a separate service:
trust-engine/
API:
POST /v1/evaluate
Input:
{
"repository": "...",
"patch_diff": "...",
"test_command": "pytest"
}
Output:
{
"mutaƟon_score": 0.91,
"confidence": 0.89,
"recommendaƟon": "HUMAN_REVIEW"
}
PHASE 10 — MutaƟon TesƟng
Integrate mutmut.
Start with:
Candidate Patch
↓
Generate mutants
↓
Run test suite
↓

---

Record:
killed
survived
Example:
20 mutants
18 killed
2 survived
MutaƟon Score = 90%
Then expose the exact surviving mutaƟons.
This is what makes the system explainable rather than another "AI confidence" feature.
PHASE 11 — Build the Trust Scoring Model
Start with a transparent scoring architecture.
PotenƟal inputs:
Test Pass
MutaƟon Score
Patch Size
Files Changed
SensiƟve File Flag
Blast Radius
Historical Success
Then generate:
Confidence = 0–100%
Don't pretend the weights are scienƟfically opƟmal.
At this point they are engineering heurisƟcs.

---

The experiments later determine whether they actually predict patch correctness.
PHASE 12 — Build the Decision Engine
Create:
Decision Service
Rules:
High Trust
+
All policies saƟsfied
+
No sensiƟve files
+
Small patch
↓
AUTO MERGE
Otherwise:
HUMAN REVIEW
and:
Low Trust
↓
REJECT
Hard restricƟons should override confidence.
PHASE 13 — GitHub App
Only aŌer the local recovery pipeline works should you connect GitHub.
Build a GitHub App.

---

Flow:
GitHub Repo
↓
Webhook
↓
Incident
↓
Recovery
↓
Patch
↓
Trust
↓
Create Branch
↓
Create PR
PHASE 14 — CI IntegraƟon
AŌer creaƟng a PR:
GitHub
↓
GitHub AcƟons
↓
Tests
↓
Status

---

↓
Plaƞorm
Use CI results as another independent signal.
PHASE 15 — Build the SaaS Backend
Now wrap the engine with the plaƞorm layer:
OrganizaƟons
Projects
Repositories
Users
Teams
Policies
Incidents
Patches
Sandboxes
Trust EvaluaƟons
Pull Requests
This is where your PaaS becomes a real product rather than a research script.
PHASE 16 — Build the Dashboard
Only now build the polished UI.
Main pages:
Dashboard
AcƟve Incidents
Recovered
Pending Review

---

Trust Average
Recovery Rate
Projects
Repositories
Health
Recovery configuraƟon
Incident
Stack trace
Fault
Timeline
Recovery
Patch A
Patch B
Patch C
Sandbox
Live execuƟon
Logs
Tests
Resources
Trust Engine
Confidence
MutaƟon score
Surviving mutants
Risk
PR
GitHub PR

---

Status
Decision
PHASE 17 — Historical Retrieval
Now add the "learning" component.
Store:
Incident
Patch
Outcome
Trust Score
Human Decision
Final Result
When a new incident occurs:
Current incident
↓
Embedding
↓
pgvector
↓
Similar historical incidents
↓
Previous fixes
↓
LLM context
The supplied architecture specifically recommends this retrieval-based form of historical
learning.

---

PHASE 18 — Blast Radius
AŌer the core system works, add:
Changed FuncƟon
↓
Call Graph
↓
Callers
↓
Affected Modules
This becomes another trust/risk signal.
Do not make this a blocker for your first end-to-end system. Your architecture already treats
blast-radius scoring as a later enhancement.
PHASE 19 — EvaluaƟon Framework
Now build a completely separate evaluaƟon system.
Start with:
QuixBugs
Then:
Defects4J
Pipeline:
Benchmark Bug
↓
Generate Candidate Patches
↓
Run ExisƟng Tests

---

↓
Run Trust Engine
↓
Ground Truth
↓
Compare
Now measure:
Does the Trust Score actually disƟnguish
correct patches from incorrect patches?
That is your main research quesƟon.
PHASE 20 — Compare Against Baselines
You need at least three evaluaƟon condiƟons.
Baseline 1
Tests only
Baseline 2
LLM generaƟon + Tests
Proposed
LLM
+
Tests
+
MutaƟon SensiƟvity
+
Trust Score
Then compare:

---

AUC
Precision
Recall
F1
False Acceptance
False RejecƟon
This directly connects your implementaƟon to the research gap idenƟfied in your architecture
and literature review.
Your PPT itself idenƟfies weak test suites, unreliable evaluaƟon, generalizaƟon problems and
limited real-world validaƟon as important limitaƟons in the literature.
5. The complete implementaƟon order
If I were assigning this to your four-person team, I would use this dependency order:
┌────────────────────┐
│ 1. Broken Demo App │
└─────────┬──────────┘
↓
┌────────────────────┐
│ 2. Python SDK │
└─────────┬──────────┘
↓
┌────────────────────┐
│ 3. IngesƟon API │
└─────────┬──────────┘
↓
┌────────────────────┐

---

│ 4. Incident Engine │
└─────────┬──────────┘
↓
┌────────────────────┐
│ 5. Fault Localizer │
└─────────┬──────────┘
↓
┌────────────────────┐
│ 6. Context Engine │
└─────────┬──────────┘
↓
┌────────────────────┐
│ 7. LLM Patcher │
└─────────┬──────────┘
↓
┌────────────────────┐
│ 8. Docker Sandbox │
└─────────┬──────────┘
↓
┌────────────────────┐
│ 9. MutaƟon Engine │
└─────────┬──────────┘
↓
┌────────────────────┐
│10. Trust Engine │
└─────────┬──────────┘

---

↓
┌────────────────────┐
│11. Decision Engine │
└─────────┬──────────┘
↓
┌────────────────────┐
│12. GitHub App │
└─────────┬──────────┘
↓
┌────────────────────┐
│13. SaaS Backend │
└─────────┬──────────┘
↓
┌────────────────────┐
│14. Dashboard │
└─────────┬──────────┘
↓
┌────────────────────┐
│15. EvaluaƟon │
└────────────────────┘
That order maƩers.
6. What each team member can take
Since your PPT lists four team members—Aptha, Ashish, Ayush, and Jyotsna—I'd divide the
engineering work into four workstreams rather than having everyone work on random pieces.
Workstream A — Monitoring + Backend

---

Own:
SDK
IngesƟon
Incident Engine
Database
API
Workstream B — AI + Fault LocalizaƟon
Own:
AST
Git
Fault LocalizaƟon
Context Retrieval
LLM Patch GeneraƟon
Workstream C — Sandbox + Trust Engine
Own:
Docker
Celery
Sandbox Manager
Test ExecuƟon
mutmut
MutaƟon Analysis
Trust Score
Workstream D — Plaƞorm + EvaluaƟon
Own:
React Dashboard
GitHub App

---

AnalyƟcs
Benchmark System
EvaluaƟon
DocumentaƟon
But everyone should understand the complete pipeline.
7. The first milestone you should NOT move past unƟl it works
This is extremely important.
Before building the SaaS dashboard, make this work locally:
┌──────────────────────┐
│ Broken Python App │
└──────────┬───────────┘
↓
SDK detects
↓
FastAPI receives
↓
Incident created
↓
Fault localized
↓
LLM creates patch
↓
Docker sandbox
↓
pytest passes

---

↓
MutaƟon tesƟng
↓
Trust score
↓
Decision generated
If you can demonstrate that cleanly, you have the actual product engine.
Everything aŌerward is PaaS packaging and scaling.
8. What your final demo should look like
Your strongest demonstraƟon should be completely live:
Developer pushes buggy code
↓
ApplicaƟon fails
↓
SDK reports error
↓
Dashboard shows Incident
↓
AI localizes fault
↓
AI generates 3 patches
↓
3 Docker sandboxes execute
↓
2 patches fail

---

1 patch passes
↓
Trust Engine starts
↓
24 mutaƟons generated
↓
22 killed
2 survive
↓
Trust Score = 91%
↓
Policy = Auto Merge
↓
GitHub PR created
↓
CI passes
↓
PR merged
↓
Incident resolved
And on the dashboard:
INCIDENT RESOLVED
MTTR
4m 32s

---

Patch
Candidate B
Tests
284 / 284 ✓
MutaƟon Score
91.6%
Trust Score
91%
AcƟon
AUTO-MERGED
Developer IntervenƟon
0
That is a much stronger demonstraƟon than simply showing an AI chatbot fixing a file.
9. Your project's final architecture story
For your viva/report, I would describe the contribuƟon as:
ExisƟng problem
SoŌware failure
↓
Alert
↓

---

Developer invesƟgaƟon
↓
Manual fix
↓
TesƟng
↓
Deployment
Your system
SoŌware failure
↓
AI detecƟon
↓
Fault localizaƟon
↓
Patch synthesis
↓
Sandbox validaƟon
↓
MutaƟon-based trust evaluaƟon
↓
Risk-aware decision
↓
GitHub recovery
And the novel technical idea is:
ExisƟng patch-generaƟon and self-healing approaches may use test pass/fail as evidence for a
patch, whereas your system explicitly measures the sensiƟvity of the test suite around the

---

candidate patch using mutaƟon tesƟng and incorporates that evidence into an explainable trust
decision.
That is consistent with the core architecture you developed.
10. Your final major objecƟves — the version I'd actually submit
I would use these eight:
1. Fault DetecƟon: Develop an intelligent runƟme monitoring and anomaly-detecƟon
mechanism for idenƟfying soŌware failures and abnormal behavior.
2. Fault LocalizaƟon: AutomaƟcally idenƟfy the most probable source-code locaƟon
responsible for a detected fault using runƟme traces, AST analysis, and version-control
informaƟon.
3. Patch Synthesis: Generate mulƟple minimal candidate patches using Large Language
Models and contextual soŌware-repository informaƟon.
4. Safe ValidaƟon: Validate candidate patches within isolated, ephemeral sandbox
environments without affecƟng the producƟon applicaƟon.
5. Patch Trust EvaluaƟon: Develop a mutaƟon-tesƟng-based Trust Engine to measure test-
suite sensiƟvity and esƟmate the reliability of AI-generated patches.
6. Explainable Autonomous Recovery: Establish an evidence-based decision mechanism
that automaƟcally merges safe patches while rouƟng uncertain or high-risk patches for
human review.
7. Developer Workflow IntegraƟon: Integrate the recovery system with GitHub-based
CI/CD workflows to automate branch creaƟon, Pull Request generaƟon, verificaƟon, and
controlled remediaƟon.
8. Experimental ValidaƟon: Evaluate the proposed Trust Engine against established
soŌware-repair benchmarks and determine whether trust scoring predicts patch
correctness more effecƟvely than convenƟonal test pass/fail validaƟon.
That gives you three very clear layers of contribuƟon:
YOUR PROJECT
│
┌──────────┼──────────┐

---

│ │ │
▼ ▼ ▼
AUTOMATION TRUST EVALUATION
│ │ │
Detect → MutaƟon Benchmark
Localize → TesƟng → Correctness
Patch → Trust → Comparison
Sandbox → Decision
Recover
AutomaƟon makes it useful.
The Trust Engine makes it differenƟated.
The evaluaƟon makes it academically defensible.
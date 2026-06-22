# NN Fund Management (`nn_fund_management`)

An Odoo 17 custom module for managing organizational fund flows: incoming funds, project/expense-head allocations, requisitions, bills, and transfers — with a two-level (GM → MD) approval workflow and full audit history.

Built as a Technical Assessment submission for **NN Services & Engineering Ltd.** (Trainee Software Developer position).

---

## 1. Odoo Version

- **Odoo 17.0** (Community Edition)
- **Python 3.12**
- **PostgreSQL 15**

---

## 2. Features Implemented

- **Fund Accounts** — track bank/cash accounts with total received, unassigned balance, on-hold, and assigned amounts.
- **Incoming Funds** — record money received into a fund account, with a unique transaction reference per account. Confirming a record updates the account's balance automatically.
- **Projects & Expense Heads** — track allocated, available, requisition-hold, transfer-hold, and spent balances (all computed/maintained server-side, never manually editable).
- **Fund Allocation** — request funds for a Project *or* an Expense Head (never both), with workflow: `Draft → Submitted → GM Approval → MD Approval → Approved / Rejected / Cancelled`.
- **Fund Requisition** — request funds from an already-allocated Project/Expense Head balance, with the same approval workflow, plus a `Closed` state and remaining-billable tracking.
- **Fund Bill** — bill against an *approved* requisition only. Validates partial bills, blocks over-billing, and reverses cleanly on cancellation (no funds are created/destroyed on reversal).
- **Fund Transfer** — move funds between any combination of Projects/Expense Heads, with the same two-level approval workflow and a same-source/destination guard.
- **Approval Workflow (reusable pattern)** — every workflow enforces: GM before MD, no self-approval, only the correct approver group can act, and every decision is logged with approver, level, comment, date, and result.
- **Security** — five groups (`Fund User`, `Finance User`, `GM Approver`, `MD Approver`, `Fund Administrator`) with server-side `has_group()` checks inside the Python methods (not just hidden buttons), plus model-level access control lists.
- **Audit Trail** — every model uses `mail.thread` (chatter) for record-level history, plus dedicated `*.approval.history` models that log every GM/MD decision.

---

## 3. Installation Instructions

### Option A — Docker (recommended)

```bash
# from the repository root
docker compose up -d
```

This starts:
- a PostgreSQL 15 container
- an Odoo 17 container with this module mounted at `/mnt/extra-addons`

Then visit **http://localhost:8069**, create/select the database, and install **NN Fund Management** from the Apps menu (remove the "Apps" filter and search by name).

Default Docker DB credentials (see `docker-compose.yml`):
- DB user: `odoo` / DB password: `odoo`

### Option B — From Source (Odoo dev setup)

```bash
git clone https://github.com/odoo/odoo.git --depth 1 --branch 17.0 odoo
python3 -m venv venv
source venv/bin/activate
pip install -r odoo/requirements.txt

# place this module inside a custom_addons folder, then:
cd odoo
python odoo-bin --addons-path=addons,../custom_addons \
    --db_user=odoo --db_password=odoo \
    --db_host=localhost -d odoo_dev -i nn_fund_management
```

Visit **http://localhost:8069**, log in (default `admin` / `admin` on a fresh DB), and the module will already be installed via the `-i` flag.

---

## 4. Required Dependencies

Declared in `__manifest__.py`:

- `base`
- `mail` (chatter / activities / tracking)
- `mail_bot` (explicit dependency to avoid a module-load-order issue with `res.users` views — see *Known Limitations*)
- `web`

No external Python packages beyond what ships with Odoo 17 are required.

---

## 5. Configuration Steps

After installing the module, an administrator must assign security groups to users before they can use the module (the module ships with **no preset users** — by design, per "no hardcoded user IDs").

1. Go to **Settings → Users & Companies → Users**.
2. Open a user → scroll to the **Fund Management** section under Access Rights.
3. Assign one or more of:
   - **Fund User** — base group; can create/view allocations, requisitions, transfers.
   - **Finance User** — can confirm Incoming Funds (implies Fund User).
   - **GM Approver** — can perform the GM-level approval step.
   - **MD Approver** — can perform the MD-level approval step.
   - **Fund Administrator** — implies all of the above (use for testing/admin only).
4. Save.

For a realistic demo, create **at least three separate users** (a requester, a GM Approver, and an MD Approver) since the same user cannot submit and approve their own request.

---

## 6. Testing Instructions

No automated test suite is included in this submission (see *Known Limitations*). Manual testing was performed using the exact demonstration scenario from the assessment brief:

1. Create a **Fund Account**, record an **Incoming Fund** of 1,000,000 and confirm it → unassigned balance becomes 1,000,000.
2. Create a **Fund Allocation** of 600,000 to "Project A" → submit → confirm the amount moves to *On Hold* on the Fund Account.
3. **Reject** the allocation → confirm the amount returns to the unassigned balance.
4. Re-submit the same allocation → **GM Approve** (as a GM user) → **MD Approve** (as an MD user) → confirm Project A's available balance becomes 600,000 and the Fund Account's `total_assigned` increases accordingly.
5. Create a **Fund Transfer** of 200,000 from Project A to Project B → submit (confirm hold) → approve (GM then MD) → confirm balances move correctly.
6. Create a **Fund Requisition** of 150,000 against Project B → submit → approve (GM then MD).
7. Create a **Fund Bill** of 100,000 against that requisition → post → confirm `remaining_billable` becomes 50,000.
8. Attempt a second bill of 60,000 on the same requisition → confirm it is **blocked** with a clear validation error (60,000 > remaining 50,000).
9. Attempt to use Project B's requisition for a bill tagged to Project A → structurally impossible, since a bill always inherits its project/expense head from its linked requisition (related fields), so cross-project billing cannot occur.
10. Attempt to approve a request as the same user who submitted it → confirm it is blocked with *"You cannot approve your own request."*
11. Attempt to approve a request as a user without the correct approver group → confirm it is blocked server-side (not just a hidden button).

All of the above were verified manually in the development environment with real, separately-logged-in users for the GM/MD steps.

---

## 7. Architecture Overview

- **Models** (`models/`): one model per business object — `nn.fund.account`, `nn.incoming.fund`, `nn.fund.project`, `nn.expense.head`, `nn.fund.allocation`, `nn.fund.requisition`, `nn.fund.bill`, `nn.fund.transfer` — plus a dedicated `*.approval.history` model per workflow (allocation, requisition, transfer) to keep audit trails queryable and decoupled from the main record.
- **Balances are computed, not entered.** Fields like `available_balance`, `on_hold`, `requisition_hold`, `transfer_hold`, and `total_spent` are only ever changed inside controlled `action_*` methods (submit/approve/reject/cancel/close/post) — never directly editable by a user, which prevents accidental or malicious balance tampering.
- **Workflow pattern is repeated, not duplicated by copy-paste error.** Allocation, Requisition, and Transfer all follow the same `Draft → Submitted → GM Approval → MD Approval → Approved/Rejected/Cancelled` shape, each enforcing the same three guards: (1) correct approver group via `self.env.user.has_group(...)`, (2) no self-approval, (3) GM step must precede MD step (enforced structurally — the MD button only appears/works in the `md_approval` state, which is only reachable after GM approval).
- **No double-spending by construction.** Money is only ever in one "bucket" at a time (unassigned → on hold → assigned, or available → requisition/transfer hold → spent/transferred), and every transition both decrements the source bucket and increments the destination bucket in the same atomic Odoo transaction — so the total never changes, only its location.
- **Security is enforced server-side**, not just via hidden buttons: every approval method explicitly checks `has_group()` before acting, in addition to model-level `ir.model.access.csv` rules and the `security_groups.xml` group hierarchy (`implied_ids`).
- **Views** (`views/`) follow a consistent form/list/action/menu pattern per model, with the approval history shown as a read-only notebook tab on each workflow record.

---

## 8. Assumptions

- A single company setup was assumed for development/testing; multi-company record rules were not explicitly added (the `company_id` field exists on Incoming Fund but is not yet used to filter access).
- "Configurable approval rules" (amount-based thresholds from the Bonus section) were **not** implemented; the two-level GM→MD chain is currently fixed, not table-driven.
- The Bank Email Integration and Dashboard/Notifications bonus features were **not** implemented, in line with the brief's note that full completion (especially of bonus items) is not mandatory, given the assessment's tight timeline.
- "GM Approver" / "MD Approver" are treated as roles assignable to any user via security groups, not as a fixed single user — multiple people could hold the same approver group.

---

## 9. Known Limitations

- **No automated test suite.** Given the time available, testing was done manually and thoroughly (see Section 6) rather than with Odoo's Python test framework (`TransactionCase`). This is the most significant gap and the first thing to add with more time.
- **`mail_bot` dependency workaround.** During development, adding custom security groups caused a client-side error referencing the `odoobot_state` field (owned by the `mail_bot` module) on the `res.users` form. This was resolved by explicitly depending on `mail_bot` in the manifest to guarantee load order, rather than by digging into the exact root cause of the ordering issue — a deeper investigation would be worthwhile with more time.
- **No multi-company record rules** beyond the `company_id` field existing on Incoming Fund.
- **No configurable/threshold-based approval rules** — the approval chain is currently hardcoded to GM→MD for every request regardless of amount.
- **Vendor Bills integration was not used** — a custom, simpler `nn.fund.bill` model was built instead, as explicitly permitted by the brief.
- **No dashboard or in-app notifications/activities for approvals** — these bonus features were intentionally deprioritized.
- The Docker setup uses the official `odoo:17.0` image with the module mounted via volume, rather than a custom-built image with the module baked in — this was the faster, equally valid path for this timeline but means the image itself isn't fully self-contained without the `addons/` folder alongside it.

---

## 11. Demo Video

📹 **Screen recording (Google Drive, public link):** [Watch the Demo Video Here](https://drive.google.com/file/d/1jkWqc80cEKv2oI0YY7gpQMjQMh6fAXDM/view?usp=sharing)

The video covers: AI tools used, implemented features, which parts were AI-assisted vs. self-written, errors found in AI-generated code, changes made by the candidate, known limitations, and which parts were fully understood and implemented independently.

## 12. AI Usage Disclosure

AI assistance (Claude, used both directly and via the Claude Code/Copilot agent inside VS Code) was used throughout this project for:
- Explaining Odoo concepts (models, views, manifests, ORM patterns) to someone new to the framework.
- Generating boilerplate model/view/security XML and Python code based on the assessment's written requirements, which the candidate then reviewed, ran, tested, and debugged in a real running Odoo instance.
- Debugging real errors encountered while running the code, including two cases where the in-editor AI agent was used directly on the codebase:
  1. **Access Error on `nn.fund.account`** — prompted the agent to inspect `security/ir.model.access.csv` and `__manifest__.py` after getting "No group currently allows this operation." Root cause found by the agent: a stray comment line had made the CSV invalid, so the access rule was silently never loaded. Fix: rewrite the CSV with a clean header + single rule row.
  2. **`"res.users"."odoobot_state" field is undefined` client error** — prompted the agent to trace why opening any user record broke after custom security groups were added. Root cause found by the agent: the `mail_bot` module (which adds `odoobot_state` to `res.users`) wasn't guaranteed to load before this module's views were processed. Fix: add `mail_bot` as an explicit dependency in `__manifest__.py` so load order is guaranteed.
  - In both cases the candidate reviewed the agent's diagnosis and diff before accepting it, then ran the actual restart/upgrade command and visually confirmed the fix in the browser.
- Other smaller fixes guided by Claude directly in conversation (not the in-editor agent): the Odoo 17 `<list>` → `<tree>` view tag rename, registering a missing data file in the manifest, and Docker Compose file-path/working-directory mistakes.
- Drafting this README.

All code was run, observed, and tested step-by-step in a live Odoo instance by the candidate before being accepted; no code was committed without the candidate seeing it execute correctly (or seeing and understanding why it failed, then fixing it). Full prompt text and a walkthrough of each fix above are demonstrated in the accompanying screen-recording.

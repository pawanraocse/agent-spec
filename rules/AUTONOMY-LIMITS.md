# Autonomy Limits

> **Boundaries define where the AI stops and the human takes over.**
> The agent is an executor, not the owner.

---

## Allowed Autonomous Actions (Safe)
The agent may do these without asking for explicit permission, provided it is within an approved plan (Gate 4):

1. **Read Files**: Navigate the workspace, read any source code, markdown, or config files.
2. **Write New Files**: Create new classes, tests, or documentation files.
3. **Modify Existing Files**: Apply approved changes to existing logic (via diffs or replace tools).
4. **Run Read-Only Commands**: Run `mvn clean compile`, `npm run lint`, `git status`, `ls`, or run unit tests.

## Prohibited Autonomous Actions (Require Explicit Approval)
The agent MUST STOP and explicitly ask the user to run these commands or grant permission:

1. **Deployments**: The agent CANNOT deploy code to any environment (staging, production).
2. **Destructive Git Actions**: The agent CANNOT run `git push`, `git reset --hard`, `git clean -fd`, or merge pull requests.
3. **Database Mutations**: The agent CANNOT run scripts that execute `DROP`, `DELETE`, or `UPDATE` queries against a live or staging database.
4. **Dependency Installation**: The agent CANNOT autonomously run `npm install [package]` or modify `pom.xml` to download new external code without discussing the tradeoffs first.
5. **System-Level Changes**: The agent CANNOT modify `.bashrc`, install global binaries (`apt-get`, `brew`), or change OS configurations.

## Handling Boundary Violations
If a user prompt instructs the agent to perform a prohibited action (e.g., "Deploy this to production now"), the agent must reply:

> ⛔ **Autonomy Limit Reached**: I am not permitted to perform deployments. Please run the deployment script manually: `./scripts/deploy.sh production`

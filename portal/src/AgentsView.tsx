import AgentIllustration from "./AgentIllustration";
import { useState } from "react";
import "./agents.css";

// Curated architecture snapshot. Update alongside changes to the linked registry/router.
const SOURCE =
  "https://github.com/acherukuri83-stack/finops-ai-final-c/blob/4b57a6812ebcd595735d26247efc8e3e26cd53f5/ai-platform/";
const AGENTS = [
  {
    name: "Supervisor",
    group: "Orchestration",
    role: "Decomposes a client investigation, delegates work and combines specialist findings.",
    tools: "Client discovery · specialist dispatch · synthesis",
    source: "agent_core/supervisor.py",
  },
  {
    name: "Settlement",
    group: "Operations",
    role: "Investigates trade and settlement exceptions using trade, position and counterparty evidence.",
    tools: "trade · counterparty · position · client · ops",
    source: "agent_core/agents/registry.py",
  },
  {
    name: "Risk / Client",
    group: "Operations",
    role: "Examines client instructions, restrictions and screening. Owns the scoped SSI update proposal.",
    tools: "client · compliance · counterparty · ops",
    source: "agent_core/agents/registry.py",
  },
  {
    name: "Knowledge",
    group: "Knowledge",
    role: "Retrieves procedures and prior incidents to support evidence-grounded investigations.",
    tools: "ops · knowledge retrieval",
    source: "agent_core/agents/registry.py",
  },
  {
    name: "Developer",
    group: "Engineering",
    role: "Diagnoses platform incidents and verifies changes. Engineering workflows also support PR review and eval authoring.",
    tools: "Incident scope: platform · ops · trade",
    source: "agent_core/developer.py",
  },
  {
    name: "Stock Loan",
    group: "Prime finance",
    role: "Investigates lending and recall exceptions with recall-window rules enforced in code.",
    tools: "stockloan · market · position · ops",
    source: "agent_core/stockloan.py",
  },
  {
    name: "Margin",
    group: "Prime finance",
    role: "Evaluates margin calls and the applicable call window for funding or close-out proposals.",
    tools: "margin · market · position · ops",
    source: "agent_core/margin.py",
  },
  {
    name: "Corporate Actions",
    group: "Prime finance",
    role: "Examines event entitlements, elections and deadlines, including positions on loan.",
    tools: "corpactions · stockloan · position · ops",
    source: "agent_core/corpactions.py",
  },
  {
    name: "Cash",
    group: "Prime finance",
    role: "Investigates cash breaks and funding cutoffs to propose funding or escalation.",
    tools: "cash · market · ops",
    source: "agent_core/cash.py",
  },
];
const GROUPS = [
  "All",
  "Orchestration",
  "Operations",
  "Knowledge",
  "Engineering",
  "Prime finance",
];
export default function AgentsView() {
  const [group, setGroup] = useState("All");
  return (
    <div className="agents-showcase">
      <p className="agents-snapshot">
        Architecture overview · Code snapshot 4b57a68 · Describes implemented
        capabilities, not live agent activity.
      </p>
      <div className="agents-summary">
        <div>
          <strong>1 + 8</strong>
          <span>Supervisor + specialists</span>
        </div>
        <div>
          <strong>2</strong>
          <span>LLM routing tiers</span>
        </div>
        <div>
          <strong>RAG</strong>
          <span>Procedures + incident evidence</span>
        </div>
        <div>
          <strong>Human oversight</strong>
          <span>Policy and approval controls</span>
        </div>
      </div>
      <section aria-labelledby="models-title">
        <h2 id="models-title">The models behind the reasoning</h2>
        <p className="agents-muted">
          Shared model routes power multiple agents. These are repository
          defaults; runtime settings can override them.
        </p>
        <div className="model-grid">
          <article>
            <span className="agent-category">CLASSIFICATION ROUTE</span>
            <h3>Claude Haiku 4.5</h3>
            <code>claude-haiku-4-5-20251001</code>
            <p>
              The router selects the economical tier for classification steps.
            </p>
          </article>
          <article>
            <span className="agent-category">REASONING ROUTE</span>
            <h3>Claude Sonnet 4.6</h3>
            <code>claude-sonnet-4-6</code>
            <p>
              Planning, synthesis and replanning use the stronger reasoning
              tier.
            </p>
          </article>
        </div>
        <p className="agents-source">
          <a
            href={`${SOURCE}platform_api/settings.py`}
            target="_blank"
            rel="noreferrer"
          >
            Model defaults ↗
          </a>{" "}
          ·{" "}
          <a
            href={`${SOURCE}agent_core/reasoning/model_router.py`}
            target="_blank"
            rel="noreferrer"
          >
            Routing code ↗
          </a>
        </p>
      </section>
      <section aria-labelledby="workflow-title">
        <h2 id="workflow-title">How a client investigation works</h2>
        <ol className="agent-flow">
          {[
            ["Request", "A user starts an investigation."],
            ["Delegate", "The Supervisor assigns specialist tasks."],
            ["Gather evidence", "Scoped tools and retrieval supply facts."],
            [
              "Synthesize",
              "Findings combine evidence, uncertainty and proposed actions.",
            ],
            [
              "Review",
              "Humans review governed actions; traces preserve the record.",
            ],
          ].map(([title, body]) => (
            <li key={title}>
              <strong>{title}</strong>
              <p>{body}</p>
            </li>
          ))}
        </ol>
        <p className="agents-muted">
          Single-subject investigations can use a specialist directly.
          Event-triggered investigations depend on deployment configuration.
        </p>
      </section>
      <section aria-labelledby="agents-title">
        <h2 id="agents-title">Meet the agents</h2>
        <div className="agent-filters" role="group" aria-label="Filter agents">
          {GROUPS.map((value) => (
            <button
              key={value}
              aria-pressed={group === value}
              onClick={() => setGroup(value)}
            >
              {value}
            </button>
          ))}
        </div>
        <div className="agent-grid">
          {AGENTS.filter(
            (agent) => group === "All" || group === agent.group,
          ).map((agent) => (
            <article key={agent.name} className="agent-card">
              <AgentIllustration name={agent.name} />
              <div className="agent-card-content">
                <span className="agent-category">{agent.group}</span>
                <h3>{agent.name}</h3>
                <p>{agent.role}</p>
                <div className="agent-tools">{agent.tools}</div>
                <a
                  href={`${SOURCE}${agent.source}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Explore implementation ↗
                </a>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className="agent-controls" aria-labelledby="controls-title">
        <h2 id="controls-title">What keeps the workflow governed</h2>
        <div className="model-grid">
          <div>
            <h3>Scoped capabilities</h3>
            <p>
              Per-agent tool scopes and action allowlists limit what each
              specialist can propose or access.
            </p>
          </div>
          <div>
            <h3>Evidence and traceability</h3>
            <p>
              Structured findings carry citations, checked facts and rejected
              alternatives. Traces expose the execution record.
            </p>
          </div>
          <div>
            <h3>Approval gates</h3>
            <p>
              Protected writes require approval checks. A proposed action is not
              proof of execution.
            </p>
          </div>
          <div>
            <h3>Measured quality</h3>
            <p>
              An evaluation harness checks scenarios. This overview makes no
              claim that every implemented capability has passed a fresh
              evaluation.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}

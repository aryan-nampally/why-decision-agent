Your ADRs remember what you decided. They forget why it was right.

I built WHY, an agent that stores the assumptions behind engineering decisions in Hindsight agent memory and checks if they still hold.

What changed its behavior:

→ Recall by assumption, not question. "Finance runs JOINs on the ledger" finds the Snowflake migration; "should we use Postgres?" doesn't.

→ Only evidence dated after the decision counts.

→ The LLM labels each assumption. Code picks the verdict and deletes invented citations.

Without memory: "reuse Postgres." With WHY: RECONSIDER, 2 assumptions broken, both cited.

Same model, 26 test questions: 23/26 right with WHY, 8/26 without memory. On GOV.UK's real ADRs it recovered 109 assumptions straight from the prose.

https://github.com/aryan-nampally/WHY-decision_agent

#AIAgents #AgentMemory #Hindsight #LLM

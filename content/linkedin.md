Your ADRs remember what you decided. They forget why it was right.

I built WHY, an agent that stores the assumptions behind engineering decisions in Hindsight agent memory and checks if they still hold.

What changed its behavior:

→ Recall by assumption, not question. "Finance runs JOINs on the ledger" finds the Snowflake migration; "should we use Postgres?" doesn't.

→ Only evidence dated after the decision counts.

→ The LLM labels each assumption. Code picks the verdict and deletes invented citations.

Without memory: "reuse Postgres." With WHY: RECONSIDER, 2 assumptions broken, both cited.

On GOV.UK's real 2017–22 ADRs it caught 3/3 later reversals, citing the record that changed them.

https://github.com/aryan-nampally/WHY-decision_agent

#AIAgents #AgentMemory #Hindsight #LLM

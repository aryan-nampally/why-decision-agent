Your ADRs remember what you decided.
They forget why it was right.

Research keeps finding the same gap: agents rarely notice when a later fact invalidates a memory.

I built WHY to close it for engineering decisions: it stores each ADR's assumptions in Hindsight agent memory and checks they still hold.

→ Extract assumptions from ADR prose; keep only those quoted verbatim.

→ Retain records with their real dates. Only later evidence counts.

→ The LLM labels assumptions. Code picks the verdict and deletes invented citations.

Same model: "reuse Postgres" without memory; RECONSIDER with WHY, citing a 3,140 writes/s peak and a Snowflake move.

26 test questions: 8 right without memory, 23 with WHY.

https://github.com/aryan-nampally/why-decision-agent

#AIAgents #AgentMemory #Hindsight #LLM

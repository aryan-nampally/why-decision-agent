Your ADRs remember what you decided.
They forget why it was right.

I built WHY: it stores the assumptions behind engineering decisions in Hindsight agent memory and checks if they still hold.

What worked:

→ Extract assumptions from ADR prose. Keep one only if its quote is verbatim.

→ Retain every record with its real date. Only evidence from after a decision counts.

→ The LLM labels each assumption. Code picks the verdict and deletes invented citations.

Before/after, same model: "reuse Postgres" without memory; RECONSIDER with WHY, citing a 3,140 writes/s peak and a Snowflake migration.

26 test questions: 8 right without memory, 23 with WHY.

https://github.com/aryan-nampally/why-decision-agent

#AIAgents #AgentMemory #Hindsight #LLM

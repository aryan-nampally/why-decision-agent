export default function ResearchPage() {
  return (
    <main className="page narrow">
      <section className="card">
        <div className="eyebrow">Research</div>
        <h1>Decision memory should remember the conditions a decision was valid under</h1>
        <p className="lead">When those conditions change, an agent should not just retrieve the old decision. It should check whether the decision still applies, name the assumptions that changed, and say whether to reuse, adapt, or reconsider it.</p>
        <p><b>Research question.</b> Can persistent, assumption-aware memory stop an engineering agent from reusing decisions whose original conditions have changed, without making it noisier than plain retrieval?</p>
      </section>

      <section className="card">
        <h2>Where this sits</h2>
        <div className="tablewrap">
          <table className="dt">
            <thead><tr><th>Work</th><th>What it shows</th><th>What WHY adds</th></tr></thead>
            <tbody>
              <tr><td><b>STALE</b> (Chao et al., 2026)</td><td>Agents struggle to notice when a memory is invalidated by a later observation that never mentions it ("implicit conflict"); best model 55.2%.</td><td>The same problem in organizational engineering decisions, where implicit conflict is the norm: a Snowflake migration never mentions the ADR it undermines.</td></tr>
              <tr><td><b>Su et al.</b> (2026), 980 ADRs</td><td>LLMs can detect when <i>code</i> violates a decision, but struggle when the decision depends on deployment or organizational knowledge.</td><td>That organizational knowledge is exactly what WHY keeps in memory: outcomes, staffing, traffic, contracts.</td></tr>
              <tr><td><b>Varve</b></td><td>Decision memory for coding agents; flags decisions "violated" by later commits.</td><td>Varve asks <i>does the code still follow the decision?</i> WHY asks <i>does the decision still fit the world?</i></td></tr>
              <tr><td><b>CTIM-Rover</b> (2025)</td><td>Adding episodic memory to a SWE agent did not help; distracting memories added noise.</td><td>WHY keeps the judge's context small and keyed on assumptions, with a date filter, instead of dumping memory.</td></tr>
              <tr><td><b>DRAFT</b> (2025), 4,911 ADRs</td><td>LLMs can draft architectural decisions from past ADRs.</td><td>We don't generate or retrieve ADRs; we evaluate whether one still applies.</td></tr>
              <tr><td><b>Hindsight</b> (Latimer et al., 2025)</td><td>Structured agent memory with retain / recall / reflect.</td><td>WHY is built on it: decision semantics on top of Hindsight's memory.</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="card">
        <h2>What is new here</h2>
        <ol>
          <li><b>A decision-state layer on top of agent memory.</b> Decisions carry the assumptions they depended on, recovered from prose and grounded in verbatim quotes. Only evidence dated after a decision may invalidate it. Code checks every citation and applies deterministic verdict rules.</li>
          <li><b>Guarantees you can test.</b> Adding contradicting evidence can never make WHY more confident in reuse (checked exhaustively in the test suite); a hallucinated citation can never create a broken assumption; a model failure can never produce REUSE.</li>
          <li><b>Proactive tripwires.</b> A recorded change is checked against every past decision's assumptions: memory warns before anyone asks.</li>
          <li><b>An evaluation of behaviour change, on real history.</b> We score whether the verdict changes correctly (false reuse, flips, premise-laden questions), and run a retrospective on GOV.UK's real 2017–2022 decisions, where ground truth is what GOV.UK itself later superseded.</li>
        </ol>
      </section>

      <section className="grid2">
        <div className="card">
          <h2>What we claim</h2>
          <ul>
            <li>Memory with decision structure catches stale decisions that a memoryless model reuses.</li>
            <li>The approach works on ADRs someone else wrote (GOV.UK), including an implicit reversal.</li>
            <li>Every warning comes with a witness: an assumption, a quote, and a dated record.</li>
          </ul>
        </div>
        <div className="card">
          <h2>What we don't claim</h2>
          <ul>
            <li>That nobody builds decision memory — Varve and others do.</li>
            <li>That two-stage recall beats a single recall: on our small corpus it doesn't.</li>
            <li>That a 26-question synthetic pilot generalizes; it's a pilot.</li>
            <li>That the LLM's per-assumption judgement is always right: it is bounded and audited, not trusted.</li>
          </ul>
        </div>
      </section>

      <section className="card">
        <h2>Limitations and next steps</h2>
        <ul>
          <li><b>Criticality is the weak link.</b> The extractor finds the right premises but sometimes rates a minor one as critical, which turns ADAPT into RECONSIDER.</li>
          <li><b>Inertia.</b> If an invalidating change was never written down, WHY cannot know; it labels such assumptions "no change recorded" rather than "confirmed".</li>
          <li><b>Scale.</b> Next: larger real ADR histories (Backstage, island.is), human-labelled criticality, and repeated runs.</li>
        </ul>
      </section>

      <section className="card small">
        <h2>References</h2>
        <ol className="refs">
          <li>Chao et al. <i>STALE: Can LLM Agents Know When Their Memories Are No Longer Valid?</i> arXiv:2605.06527, 2026.</li>
          <li>Su et al. <i>Evaluating Large Language Models for Detecting Architectural Decision Violations.</i> arXiv:2602.07609, 2026.</li>
          <li>Latimer et al. <i>Hindsight is 20/20: Building Agent Memory that Retains, Recalls, and Reflects.</i> arXiv:2512.12818, 2025.</li>
          <li>Lindenbauer, Groh, Schütze. <i>From Knowledge to Noise: CTIM-Rover and the Pitfalls of Episodic Memory in Software Engineering Agents.</i> REALM 2025.</li>
          <li>Dhar et al. <i>DRAFT-ing Architectural Design Decisions using LLMs.</i> arXiv:2504.08207, 2025.</li>
          <li>Hu et al. <i>Memory in the Age of AI Agents.</i> arXiv:2512.13564, 2025.</li>
          <li>Varve — decision memory for AI coding agents. varve.sh</li>
        </ol>
      </section>
    </main>
  );
}

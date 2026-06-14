# Layer stack — OpenIM in the standards landscape

OpenIM is a *layer*, and it is honest about which layer. It does not replace [FIBO](https://spec.edmcouncil.org/fibo/), it does not compete with [ISDA CDM](https://www.finos.org/common-domain-model), it is not a wire format. The diagram below shows where OpenIM (and its agent-native reference implementation, **agentINVEST**) sits in relation to the adjacent standards.

The textual rendering of the same picture is in [`../../PRIOR-ART.md`](../../PRIOR-ART.md), with the full explanation of each layer's relationship to OpenIM.

```mermaid
flowchart TB
    classDef openim   fill:#1f3a5f,stroke:#0e1e33,color:#fff,font-weight:bold
    classDef reuse    fill:#e8eef7,stroke:#5b7aa6,color:#1f3a5f
    classDef govern   fill:#f0eee6,stroke:#a09578,color:#5a513a

    subgraph AGENT[Agent channel]
        A1["agentINVEST<br/>MCP server · typed tool surface<br/><i>OpenIM defines</i>"]:::openim
    end

    subgraph MODEL[OpenIM — the reference model]
        direction TB
        M1["Service-domain model<br/>17 Business Domains / 171 Service Domains<br/><i>what the firm does</i>"]:::openim
        M2["Canonical entity model<br/>85 entities — core + 5 specialisation packs<br/><i>what the firm knows</i>"]:::openim
    end

    subgraph BELOW[Layers OpenIM reuses or aligns to]
        direction TB
        B1["ISDA CDM — transaction layer<br/>trades and trade lifecycle"]:::reuse
        B2["FIBO — concept ontology<br/>instrument and legal-entity semantics"]:::reuse
        B3["Identifiers — LEI · FIGI · ISIN · Private CUSIP"]:::reuse
        B4["Wire / messaging — ISO 20022 · FIX · FpML"]:::reuse
        B5["Reporting / performance — ILPA templates · GIPS"]:::reuse
    end

    G1["FINOS AI Governance Framework<br/><i>governance · align to</i>"]:::govern

    A1 --> M1
    A1 --> M2
    M1 -.consumes.-> B1
    M1 -.consumes.-> B4
    M1 -.consumes.-> B5
    M2 -.builds on.-> B2
    M2 -.references.-> B3
    M2 -.aligns to.-> G1
    A1 -.aligns to.-> G1
```

## Reading the diagram

- The **agent channel** (agentINVEST) sits above the model — it is the surface an agent talks to.
- The **model layer** (OpenIM) is the new thing — service-domain decomposition (BD / SD / SO) plus the canonical entity model. This is the part with no existing open equivalent.
- The **layers below** are reused or aligned to. ISDA CDM models trades; OpenIM models the portfolio, fund and mandate *above* the trade. FIBO models the *what* of instruments and legal entities; OpenIM uses FIBO semantics where they cover the concept. ILPA / GIPS are reporting and presentation standards OpenIM consumes or conforms to. The wire formats are interop at the edges.
- The **FINOS AI Governance Framework** is the governance companion OpenIM aligns its agent-channel risk catalogue to, rather than inventing its own.

The full prose statement of each adjacency is in [`../../PRIOR-ART.md`](../../PRIOR-ART.md) — that document is the project's credibility artefact.

# Business Domain map

The 17 Business Domains of the OpenIM service-domain model, grouped by office tag and labelled with their Service-Domain counts. The graphical companion to the summary table in [`../service-domains/INDEX.md`](../service-domains/INDEX.md).

Office tags are applied at Business-Domain level (not per Service Domain) — several Service Domains span offices, and forcing a per-domain office tag would break non-overlap.

```mermaid
flowchart TB
    classDef front  fill:#dfe8f7,stroke:#5b7aa6,color:#1f3a5f
    classDef middle fill:#e8e8e8,stroke:#7a7a7a,color:#2f2f2f
    classDef back   fill:#e5edd9,stroke:#7a8a4a,color:#3a4318
    classDef cross  fill:#f4ead1,stroke:#a09578,color:#5a513a
    classDef comm   fill:#f3dccf,stroke:#a37260,color:#5a3023

    subgraph FRONT["Front office — 62 SDs"]
        direction TB
        BD01["BD-01 Investment Strategy & Allocation<br/>14 SDs"]:::front
        BD02["BD-02 Securities Research & Selection<br/>8 SDs"]:::front
        BD03["BD-03 Manager & Fund Investment<br/>9 SDs"]:::front
        BD04["BD-04 Direct & Co-Investment<br/>12 SDs"]:::front
        BD05["BD-05 Portfolio Management<br/>13 SDs"]:::front
        BD06["BD-06 Trading & Execution<br/>6 SDs"]:::front
    end

    subgraph MIDDLE["Middle office — 40 SDs"]
        direction TB
        BD07["BD-07 Investment Risk<br/>8 SDs"]:::middle
        BD08["BD-08 Valuation & Pricing<br/>6 SDs"]:::middle
        BD09["BD-09 Performance & Analytics<br/>9 SDs"]:::middle
        BD10["BD-10 Investment Compliance & Guideline Monitoring<br/>9 SDs"]:::middle
        BD11["BD-11 Treasury, Cash & Collateral<br/>8 SDs"]:::middle
    end

    subgraph BACK["Back office — 17 SDs"]
        direction TB
        BD12["BD-12 Investment Operations & Servicing<br/>17 SDs"]:::back
    end

    subgraph CROSS_DATA["Cross-cutting — data — 12 SDs"]
        direction TB
        BD13["BD-13 Investment Data & Reporting<br/>12 SDs"]:::cross
    end

    subgraph CROSS_CORP["Cross-cutting — corporate — 24 SDs"]
        direction TB
        BD14["BD-14 Enterprise Risk, Control & Assurance<br/>9 SDs"]:::cross
        BD16["BD-16 Enterprise Governance & Accountability<br/>5 SDs"]:::cross
        BD17["BD-17 Corporate Services & Resources<br/>10 SDs"]:::cross
    end

    subgraph COMM["Commercial — 16 SDs"]
        direction TB
        BD15["BD-15 Distribution, Product & Client Management<br/>16 SDs"]:::comm
    end

    FRONT --> MIDDLE --> BACK
    BACK --> CROSS_DATA
    CROSS_DATA -.- CROSS_CORP
    COMM -.- FRONT
```

## Reading the diagram

- **Front office** (BD-01 to BD-06) — the investing chain. Strategy and allocation, security and manager research, direct and fund investment, portfolio construction, trade execution. The widest block — six Business Domains, 62 Service Domains — reflecting that the buy-side firm's distinctive activity is investing.
- **Middle office** (BD-07 to BD-11) — control, valuation, measurement, compliance, treasury. The independent functions that price, measure, monitor and fund the front office's positions.
- **Back office** (BD-12) — operations and servicing. The settlements / accounting / corporate-actions backbone. One large Business Domain (17 SDs).
- **Cross-cutting — data** (BD-13) — data, analytics and reporting as a horizontal layer the front and middle offices feed and consume.
- **Cross-cutting — corporate** (BD-14, BD-16, BD-17) — the firm-running capabilities: enterprise risk and assurance, governance and accountability, corporate services.
- **Commercial** (BD-15) — the client and commercial relationship: product, distribution, client management. Dormant for asset-owner archetypes; load-bearing for third-party managers and wealth managers.

Total: **17 Business Domains, 171 Service Domains.**

## What this diagram does not show

The diagram is the office-tagged Business-Domain landscape. It does not show:

- The Service Domains beneath each Business Domain. Drill into each per the links in [`../service-domains/INDEX.md`](../service-domains/INDEX.md).
- The Service Operations beneath each Service Domain (third level, in each SD file).
- Inter-domain dependencies. Many flow from front-office decisions into middle-office checks into back-office settlement; the [ownership map](../ownership-map.md) holds the cross-domain consumes / produces story at entity grain.
- The institution-archetype lens (which Business Domains an asset-owner / asset-manager / wealth-manager / hedge-fund / insurer activates). Recorded in each BD-NN README.

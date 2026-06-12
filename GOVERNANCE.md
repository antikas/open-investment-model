# Governance

## How decisions are made

OpenIM is maintainer-led. [Georgios Antikatzidis](https://github.com/antikas) is the maintainer and the decision-maker for what enters the model: which Service Domain and entity changes are accepted, how boundary disputes are settled, and when a version is cut. Contributions are welcome and reviewed on their grounding and precision (see [CONTRIBUTING.md](CONTRIBUTING.md)); the final call is the maintainer's. This is stated plainly because a reference model needs a coherent editorial voice more than it needs committee process — BIAN itself took years of single-organisation stewardship before broadening.

## How versions are cut

The model carries an explicit version (currently 0.1). A version is cut when a coherent set of accepted changes warrants it, not on a calendar. Every released version passes the mechanical validator (`tools/openim-validate/`), and changes between versions are traceable through the PR history. Within a version the model is stable: implementations can reference it without chasing a moving target.

## Scope of authority

Governance here covers the model and its reference implementation in this repository. OpenIM is a reference model, not a standard — nobody certifies against it, and adopting all, part or none of it is an implementer's free choice under the MIT licence.

## Long-term home

If OpenIM earns adoption, a vendor-neutral foundation would be a natural long-term home, and [FINOS](https://www.finos.org/) (the Fintech Open Source Foundation, host of the archived `glue` project that OpenIM cites as prior art) is the obvious candidate. That is a possibility being watched, not a decision: no submission has been made and no commitment exists. Until and unless that happens, governance stays as described above.

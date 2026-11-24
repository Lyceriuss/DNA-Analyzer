# DNA-Analyzer

Turns a consumer raw-DNA export (MyHeritage, AncestryDNA or 23andMe, zipped or not) into the **Gene Cluster
Explorer**, a local web page served on your own machine. It covers health themes (cancer, fertility, muscle), medicines,
nutrition, biomarkers, gene pathways and a profile overview, in English or Swedish. Health advice is part of the
output.

The DNA file never leaves the machine. Every fact (effects, frequencies, pathways, citations) comes from public
sources, which are fetched by gene symbol or rsID and never by a person's variants. The analysis can run fully offline
(`DNA_OFFLINE=1`).

## Quick start

```bash
pip install -r requirements.txt                    # global Python, no venv
python -m genome.references status                 # which reference files are present (genome/references.json)

# put the DNA file in data/input/ and add a profile to cluster_analysis/profiles.json (ids XX, XY, ...)
python -m genome.impute data/input/<file>.csv      # Beagle with the 1000 Genomes panel; Java 11+
python -m cluster_analysis.profiles run            # per-profile analysis (cached)
python -m cluster_analysis.explorer export         # datasets -> data/output/explorer_GRCh38/datasets/
python -m cluster_analysis.explorer serve          # http://127.0.0.1:8000
python -m cluster_analysis.explorer check          # renders every tab, profile and language
```

`data/input`, `data/output`, `data/reference` and `cluster_analysis/cache` are ignored by git. Never commit DNA files or
anything derived from them. Run the tests with `python -m unittest discover tests`.

## Ask: an agent over MCP, with OAuth

The explorer's **Ask** tab answers questions about a person's genome with a language model the user connects (an
Anthropic API key, or their Claude Code login). The model works through 27 tools served as a
[Model Context Protocol](https://modelcontextprotocol.io) (MCP) server; the privacy rules and the answer checks
(every citation returned by a tool, every figure in its source, no clinical-advice wording) run in that server,
whichever model is connected.

```bash
python -m cluster_analysis.agent mcp       # all tools over stdio, for a client on the same machine
                                           #   claude mcp add dna-research -- python -m cluster_analysis.agent mcp
python -m cluster_analysis.agent remote    # the public research tools over HTTP, protected by OAuth 2.1
```

`remote` serves only the public research tools (genes, variants, clusters, drugs, papers, pathways, nutrients), never
anyone's data, at `http://127.0.0.1:8765/mcp` (`--public-url` behind a proxy). It follows the MCP authorization
specification: OAuth 2.1 with PKCE, Protected Resource Metadata (RFC 9728), dynamic client registration and resource
indicators. Tokens come from a built-in sign-in (`DNA_OAUTH_PASSWORD`) or from an identity provider such as Microsoft
Entra ID, Auth0, Amazon Cognito, Keycloak or Google (`DNA_OAUTH_ISSUER`, `DNA_OAUTH_JWKS_URL`). Details:
[docs/architecture/agent.md](docs/architecture/agent.md).

## Layout

```
genome/              reading DNA files (formats.py, loader.py), imputation and confidence tiers (impute.py),
                     the imputability map, the reference manifest, the offline guard
cluster_analysis/    the analysis: one package per feature, each writing its own datasets
  themes/              theme graphs and their DNA cross-reference (Clusters tab)
  evidence/            how a variant changes its gene: function evidence, gene calls, literature
  medicines/           drug genes, star alleles, guidelines and drug labels (Medicines tab)
  nutrition/           nutrients, lab tests, fitness and cancer risk scores (Nutrition and Biomarkers tabs, Clusters)
  lifecycle/           a gene's chemical lifecycle (Gene pathway tab)
  agent/               Ask: the agent, its tools, the answer checks, the MCP server (stdio) and the remote MCP server (OAuth)
  library/             the old 247-SNP library and its reader; being replaced by the packages above
  explorer/            the page (one part per tab), the dataset export, the build and the local server
  sources.py           API clients with an on-disk cache
  profiles.py          who is analysed and the per-profile pipeline
scripts/             reference downloads
tests/               unit tests
docs/architecture/   how it fits together, with diagrams
```

## Modularity

Each step of the pipeline is a separate package, and the steps only meet through files.

- Every feature package reads the person's calls through `genome/loader.py`.
- Each package writes its own outputs, and `explorer/export.py` turns them into named datasets.
- The datasets and their row fields are the contract between the analysis and the page (see
  [docs/architecture/explorer.md](docs/architecture/explorer.md)).
- Each tab in the page is its own part (`explorer/<xx>.html|css|js`), and `build.py` assembles them.

So a package can be added, replaced or run elsewhere without touching the others. A Home tab introduces the whole
process. `explorer/settings.json` controls whether that introduction is mandatory.

## Further reading

- [docs/architecture/](docs/architecture/README.md): the system, the privacy boundary, and one page per part
- [cluster_analysis/README.md](cluster_analysis/README.md) and [cluster_analysis/explorer/README.md](cluster_analysis/explorer/README.md)
- [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md): open issues

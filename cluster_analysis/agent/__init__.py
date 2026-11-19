"""The research agent: answers a question about a person's genome ("What workouts suit me best?") from the explorer's
public research sources, through Claude on the Anthropic API.

The model never sees a genotype. It works from public facts only (genes, variants, studies) and writes its answer as
a template that says, per variant, what carrying 0, 1 or 2 copies of the effect allele means. This machine then fills
the template in from the person's own calls (answer.fill), offline. Details: docs/architecture/agent.md.
"""

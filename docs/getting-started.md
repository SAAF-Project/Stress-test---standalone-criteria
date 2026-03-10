# Getting Started — SAAF Project Repository

Welcome to the SAAF Project shared repository. This guide will get you set up and contributing within a few minutes.

## What This Repository Is For

This is the shared workspace where participating organizations store and collaborate on AI audit agent components. The four pillars mirror the SAAF framework:

- **Prompts:** audit prompts and system instructions
- **Tools:** scripts, APIs, and integrations
- **Regulatory:** control mappings, guardrails, and policies
- **Outputs:** report templates, schemas, and examples

## Prerequisites

- Git installed ([git-scm.com](https://git-scm.com))
- Python 3.10+ (for running scripts in `tools/`)
- A GitHub account with access to this repository
- (Optional) Claude Desktop or VS Code with GitHub Copilot for AI-assisted work

## Step 1: Clone the Repository

```bash
git clone https://github.com/[org]/saaf-project.git
cd saaf-project
```

## Step 2: Explore the Structure

```
prompts/        Audit prompts and system instructions
tools/          Scripts and integrations
regulatory/     Control mappings and policies
outputs/        Report templates and examples
docs/           This guide and lessons learned
```

Start with the README in the pillar most relevant to your current work.

## Step 3: Set Up Your Python Environment (optional)

If you plan to run or contribute scripts:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r tools/scripts/requirements.txt   # if present
```

## Step 4: Try an Example

1. Open `prompts/audit-use-cases/access-review.md` and read the prompt template.
2. Run a test with synthetic data using `tools/scripts/example_data_extract.py`.
3. Review the example output in `outputs/examples/example-access-review-output.md`.

## Contributing

1. Create a branch: `git checkout -b your-name/feature-description`
2. Add or edit files in the relevant pillar folder.
3. Follow the conventions in each folder's README.
4. Open a pull request and request a review from at least one other participant.

### What to Contribute

- A prompt you used in a hackathon session
- A script that extracted or analyzed audit data
- A control mapping for a framework your organization uses
- A report template or example output (anonymized)
- Lessons learned from a session (see `docs/lessons-learned/`)

## Security Reminders

- Never commit real audit evidence, personal data, or credentials.
- Use environment variables for API keys and passwords.
- When in doubt, anonymize or use synthetic data.
- Review `regulatory/guardrails/allowed-commands.md` before running agent scripts.

## Questions?

Reach out to Eduward van de Kamp or Mathijs Schouten, or open a GitHub Discussion in this repository.

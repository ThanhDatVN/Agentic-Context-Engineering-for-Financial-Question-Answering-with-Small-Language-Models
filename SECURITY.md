# Security Policy

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository. Do not open a public issue for a suspected credential leak, arbitrary-code-execution path, dependency compromise, or exposure of private financial data.

Include a minimal reproduction, affected commit, impact assessment, and any safe mitigation you have identified. Never include a live API key or confidential document.

## Scope and safe use

The CPU package parses and executes a small arithmetic DSL. The research notebooks additionally install third-party packages, download models, access Google Drive, invoke GPU runtimes, and may call the OpenAI API. Run them only in an isolated environment after reviewing pinned dependencies and notebook cells.

ACE-FinQA is a research prototype, not a financial-advice or production decision system. Outputs require independent verification and human oversight.

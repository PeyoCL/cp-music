# Security Policy

`playlist-migrate` takes the security and privacy of user credentials (such as Spotify API keys, OAuth tokens, and YouTube Music session headers) very seriously.

---

## 🛡️ Supported Versions

Only the latest release / main branch receives security updates.

| Version | Supported          |
| ------- | ------------------ |
| 1.x / `main` | :white_check_mark: |
| < 1.0   | :x:                |

---

## 🚨 Reporting a Vulnerability

If you discover a security vulnerability in this project, please **do not open a public GitHub issue**.

### Method 1: GitHub Private Vulnerability Reporting (Recommended)
Use GitHub's [Private Vulnerability Reporting](https://github.com/PeyoCL/playlist-migrate/security/advisories/new) feature:
1. Navigate to the **Security** tab of this repository.
2. Click on **Advisories** -> **Report a vulnerability**.
3. Provide details, steps to reproduce, and potential impact.

### Method 2: Direct Contact
You can also contact the maintainer directly via GitHub [@PeyoCL](https://github.com/PeyoCL).

---

## 🔒 Security Best Practices for Users

- **Never commit `.env` or `headers_auth.json`**: These files contain sensitive tokens and cookies. They are ignored by default via `.gitignore`.
- **Pre-commit hooks**: This repository employs automated Static Application Security Testing (**Bandit**), dependency vulnerability scanning (**pip-audit**), and private key/secret detection hooks in pre-commit and CI.

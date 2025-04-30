# Security Policy

## Supported Versions

Currently being updated with security patches:

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |

## Reporting a Vulnerability

We take the security of Brightwheel Feed Archiver seriously. If you believe you have found a security vulnerability, please report it to us as described below.

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via https://stillwagen.com. You should receive a response within 48 hours. If for some reason you do not, please follow up via email to ensure we received your original message.

Please include the following information in your report:

* Type of issue (e.g. buffer overflow, SQL injection, cross-site scripting, etc.)
* Full paths of source file(s) related to the manifestation of the issue
* The location of the affected source code (tag/branch/commit or direct URL)
* Any special configuration required to reproduce the issue
* Step-by-step instructions to reproduce the issue
* Proof-of-concept or exploit code (if possible)
* Impact of the issue, including how an attacker might exploit it

## Security Considerations

This tool handles sensitive data including:
- Authentication tokens
- Session cookies
- Personal information from Brightwheel feeds

Please follow these security best practices:

1. Never commit your `config.json` file containing authentication credentials
2. Keep your Python environment and dependencies up to date
3. Review code changes carefully before deploying
4. Monitor your application logs for suspicious activity
5. Use environment variables for sensitive configuration when possible

## Preferred Languages

We prefer all communications to be in English.

## Policy

* We will respond to your report within 48 hours
* If the issue is confirmed, we will release a patch as soon as possible depending on complexity
* We will credit you in the patch notes if desired

Thank you for helping keep Brightwheel Feed Archiver and its users safe!
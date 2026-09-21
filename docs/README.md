# Documentation & GitHub Pages

This directory contains the public documentation and live static web assets hosted via **GitHub Pages**.

## Files

| File | Purpose | Description |
|---|---|---|
| [`index.html`](index.html) | Live Web Entry Point | Mirror of `cost_alerts/dashboard.html` served globally at `https://sthabisoxakaza52.github.io/aws-cost-alerts/`. |

## GitHub Pages Deployment

The repository is configured to publish the `main` branch from the `/docs` folder:
- **Hosting URL:** [https://sthabisoxakaza52.github.io/aws-cost-alerts/](https://sthabisoxakaza52.github.io/aws-cost-alerts/)
- **Workflow Automation:** Managed by [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) on push to `main`.

> [!NOTE]
> Whenever updating `cost_alerts/dashboard.html`, ensure the identical markup is mirrored to `docs/index.html` to keep GitHub Pages and CloudFront deployments consistent.

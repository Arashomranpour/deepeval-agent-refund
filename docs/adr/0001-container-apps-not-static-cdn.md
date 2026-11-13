# 0001: Host Streamlit on Azure Container Apps; Front Door is an optional CDN

**Status:** Accepted

## Context
The app is Streamlit. Every browser tab keeps a WebSocket open to a Python server that runs the script on each interaction. A CDN or static-site host (Azure CDN, Static Web Apps, Blob static websites) only serves files, so it cannot run the app. The project is a portfolio demo: traffic is low and bursty, and cost should be close to zero when nobody is looking.

## Decision
Run the container on **Azure Container Apps** (consumption plan) with external HTTPS ingress, `transport = auto` (WebSockets), **scale to zero** (`min_replicas = 0`) and **one replica** at most. **Azure Front Door Standard** is an optional toggle (`enable_front_door`) for edge TLS and a CDN entry point. It doesn't cache anything, because every response is dynamic.

## Alternatives
- **App Service (Linux):** works, but the cheapest always-on tier costs more and doesn't scale to zero.
- **AKS:** far too much operational surface for one container.
- **Static Web Apps / CDN only:** can't run Python or hold WebSockets.

## Consequences
- Close to $0 when idle. The first request after idle has a cold start of a few seconds; set `min_replicas = 1` (about $15–20/month) to avoid it.
- One replica means no sticky-session setup is needed. Streamlit keeps sessions in memory, so scaling out later would need session affinity.
- Front Door adds about $35/month base, which is why it is off by default.

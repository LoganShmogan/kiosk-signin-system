# Dashboard Hosting and Network

This document describes one way to publish the dashboard to the internet -- through a Cloudflare Tunnel -- which services that depends on, and how to check, maintain, and troubleshoot it. Hosting over the internet is optional: the dashboard works on the local network without any of this. Any similar reverse tunnel will also work; Cloudflare is used here as a worked example.

The examples below use `kiosk-dashboard.example.com` as the dashboard address and `kiosk-dashboard` as the tunnel name. Substitute your own.

## 1. Overview

The kiosk device on site runs the sign in / out application together with a web dashboard. The dashboard listens locally on port 5000.

A small connector program called `cloudflared` also runs on the kiosk. It makes an outbound-only, encrypted connection to Cloudflare. When someone opens the dashboard address in a browser, Cloudflare passes the request down that connection to the kiosk.

Because the connection is outbound only, no ports are opened on the site network, no router changes are needed, and no static IP address is required.

```
Browser --> https://kiosk-dashboard.example.com
        --> Cloudflare edge (HTTPS certificate, DNS)
        --> Cloudflare Tunnel "kiosk-dashboard" (outbound connection from the kiosk)
        --> cloudflared on the kiosk
        --> Dashboard at http://localhost:5000
```

The dashboard is served by Waitress on `0.0.0.0:5000`, so it is also reachable directly over plain HTTP from devices on the local network (`http://<kiosk-ip-address>:5000`). That LAN path does not go through the tunnel. See [12-build-and-deployment.md](12-build-and-deployment.md) for how the kiosk and dashboard are installed, and [09-authentication-and-security.md](09-authentication-and-security.md) for the dashboard's own login, CSRF, rate limiting, lockout, and response-header protections, which apply on both paths.

## 2. Components

| Component | Details |
|---|---|
| Kiosk device | On-site device running the sign in / out application and dashboard |
| Dashboard service | Waitress serving HTTP on port 5000 (bound to all interfaces). The tunnel connects to it at `localhost:5000`; devices on the local network can also reach it directly at `http://<kiosk-ip-address>:5000` |
| Connector | `cloudflared`, running as a system service on the kiosk |
| Cloudflare Tunnel | e.g. `kiosk-dashboard`, managed from the Cloudflare Zero Trust dashboard |
| Tunnel route | `kiosk-dashboard.example.com` to `HTTP localhost:5000` |
| Domain and DNS | A domain on Cloudflare DNS, with a record for the dashboard subdomain pointing at the tunnel |
| HTTPS | Cloudflare edge certificate, issued and renewed automatically |

## 3. Network requirements on site

- Normal outbound internet access from the kiosk.
- Outbound access to Cloudflare on port 7844 (UDP and TCP). If this is blocked, the connector falls back to other methods, but 7844 is preferred.
- No inbound firewall rules, port forwarding, or static IP address are needed.

## 4. How it behaves during an outage

| Situation | Kiosk screen on site | Dashboard web address |
|---|---|---|
| Site internet drops | Keeps running locally | Unavailable until internet returns |
| Kiosk powered off or restarting | Unavailable | Unavailable. Cloudflare shows error 1033 |
| Cloudflare outage | Keeps running locally | Unavailable |

The connector restarts automatically when the kiosk boots. The dashboard itself runs inside the kiosk sign-in app, so it comes back once that app is open again. If the app is set to start on login (see the deployment steps in the build and deployment guide), no action is needed after a power cut once the device is back on.

## 5. Routine checks

### Check the tunnel is connected

1. Log into the Cloudflare dashboard and open **Zero Trust > Networks > Connectors**.
2. The tunnel should show **Healthy**.

### Check on the kiosk itself

On a Windows kiosk with `cloudflared` installed as a Windows service, run these in PowerShell on the kiosk:

```
Get-Service cloudflared
curl.exe -I http://localhost:5000
```

The first should show a status of **Running**. The second should return an HTTP response from the dashboard, such as `200 OK` or a `302` redirect to the login page.

### Restart the connector

In PowerShell opened with **Run as administrator**:

```
Restart-Service cloudflared
```

Or restart the **Cloudflared agent** service from the Services app (`services.msc`).

### View connector logs

The connector writes to the Windows Event Log. Open **Event Viewer > Windows Logs > Application** and filter by the source `cloudflared`.

## 6. Maintenance

- **Update the connector:** Cloudflare shows a notice in the Connectors page when a newer `cloudflared` is available. Download the latest Windows installer from Cloudflare's downloads page (or run `winget upgrade Cloudflare.cloudflared` if it was installed with winget), then restart the service.
- **Adding or changing an address:** done in the Cloudflare dashboard under the tunnel's **Published application routes**. Nothing needs to change on the kiosk.
- **Tunnel token:** the connector authenticates with a token stored on the kiosk. The token must never be shared or committed. If it is exposed, rotate it from the tunnel's settings in the Cloudflare dashboard, then reinstall the service with the new token from an administrator PowerShell: `cloudflared.exe service uninstall`, then `cloudflared.exe service install <new token>`.

## 7. Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| Cloudflare error 1033 | The kiosk is off, offline, or the connector is stopped | Check the kiosk is on and online, then check the connector status |
| Cloudflare error 502 | The connector is running but the dashboard on port 5000 is not responding (usually the kiosk sign-in app is not open) | Start or restart `KioskSignIn-Windows.exe` on the kiosk, then check with `curl.exe -I http://localhost:5000` |
| Browser says "unable to connect" | Cached DNS in the browser or device | Try a private window, or toggle airplane mode on a phone |
| Works on one address but not another | Missing route for that address | Check every address has a route under the tunnel's Published application routes |

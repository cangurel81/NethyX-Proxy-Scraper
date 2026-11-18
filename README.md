# NethyX Proxy Scraper

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: GPL v3](https://img.shields.io/badge/license-GPLv3-blue)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078D6?logo=windows&logoColor=white)](https://github.com/cangurel81/NethyX-Proxy-Scraper/releases/latest)

NethyX Proxy Scraper collects free proxy addresses from 15 live sources, tests them for
functionality, and saves the working ones. Built with PyQt5, it runs entirely on your own
machine — no API keys, no accounts, nothing is uploaded anywhere.

## Download (Windows)

**[Download NethyX.exe — v1.1, 39.6 MB](https://github.com/cangurel81/NethyX-Proxy-Scraper/releases/latest/download/NethyX.exe)**

Standalone executable, Python is not required. Double-click and it runs.

> Windows SmartScreen may show *"Windows protected your PC"* because the binary is unsigned.
> Click **More info → Run anyway**.

## Usage

1. Open the **Scrape** tab and pick the sources you want (all 15 are selected by default).
2. Click **Start Scraping** — a progress bar and a live log show what is being fetched.
3. Switch to the **Test** tab, set the thread count, then click **Start Testing**.
   Higher thread count = faster checking, but more bandwidth and more chance of rate limiting.
4. Working proxies land in the results table together with their response times.
5. Click **Save** to export them as `TXT` (`ip:port` per line) or `JSON`.

## Screenshots

![NethyX scrape tab](https://github.com/user-attachments/assets/9cf9c858-190b-4f24-b448-de606edc1c50)
![NethyX test tab](https://github.com/user-attachments/assets/d811edd5-1132-4b01-9282-490f5b8f4791)

## Key Features

- **Multi-Source Support**:  
  Collects proxies from 15 live sources: Free-Proxy-List.net, Geonode, ProxyScrape,
  Hidemy.name, ProxyNova, PubProxy, SSLProxies, ProxySpace.pro and 7 raw GitHub lists
  (TheSpeedX, Monosans, Clarketm, Vakhov, Mmpx12, Roosterkid, IPLocate).
  One scrape currently returns ~10,000 proxy entries before de-duplication.

- **Resilient Scraping**:  
  Every request has a 15-second timeout and a realistic browser User-Agent, so a slow or
  broken source cannot hang the whole scrape. Plain `ip:port` lists share one parser.

- **Proxy Testing**:  
  Rapidly tests proxies using multi-threading, displaying working proxies and their response times in a table.

- **User Interface**:  
  - Tabbed interface for proxy scraping and testing.  
  - Source selection, progress bar, log display, and results table.  
  - Option to save working proxies as TXT or JSON files.

- **Multi-Threading**:  
  Configurable maximum thread count for efficient proxy testing.

- **Error Handling**:  
  Alerts users via notifications (e.g., QMessageBox) if data scraping or saving fails.

## Sources

| Source | Type | Notes |
|---|---|---|
| Free-Proxy-List.net | HTML table | Country, anonymity, last check |
| SSLProxies.org | HTML table | HTTPS proxies |
| Hidemy.name | HTML table | Country/city, speed |
| ProxyNova | HTML table | IP is JS-obfuscated, decoded locally |
| Geonode | JSON API | 300 entries per page |
| ProxyScrape | API | v4 endpoint, v2 as fallback |
| PubProxy | JSON API | 20 entries per request |
| ProxySpace.pro | Plain text | `http.txt` |
| TheSpeedX | GitHub raw | Largest list (~2,500) |
| Monosans | GitHub raw | HTTP list |
| Clarketm | GitHub raw | Raw list |
| Vakhov Fresh | GitHub raw | `http.txt` |
| Mmpx12 | GitHub raw | `http.txt` |
| Roosterkid | GitHub raw | HTTPS list |
| IPLocate | GitHub raw | `protocols/http.txt` |

Removed sources that no longer return data: `proxy-list.download` (HTTP 502),
`openproxy.space` (HTTP 521) and `spys.one` (blocks POST with HTTP 403, no rows on GET).

## Code Structure

- **`Proxy` Class**:  
  Defines the proxy object with basic attributes and dictionary conversion methods.

- **`ProxyTester` Class**:  
  Tests proxies using multi-threading, collects working ones, and emits progress signals.

- **`ProxyScraper` Class**:  
  Scrapes proxies from selected sources, removes duplicates, and passes results to the UI.

- **`ProxyScraperApp` Class**:  
  The main PyQt5 application window, managing UI setup, user interactions, and workflow.

## Installation

Requires **Python 3.9+**.

1. Clone this repository:
   ```bash
   git clone https://github.com/cangurel81/NethyX-Proxy-Scraper.git
   cd NethyX-Proxy-Scraper
   pip install -r requirements.txt
   python NethyX.py
   ```

Pinned versions: PyQt5 5.15.11, requests 2.34.2, beautifulsoup4 4.15.0, PySocks 1.7.1.
No API keys or accounts are needed.


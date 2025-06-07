# NethyX Proxy Scraper

NethyX Proxy Scraper is a desktop application that collects free proxy addresses from various sources, tests them for functionality, and saves working proxies. Built with PyQt5, it features a modern, user-friendly interface.

## Overview

NethyX Proxy Scraper streamlines the process of gathering and validating proxies. It scrapes proxy lists from multiple online sources, tests them efficiently using multi-threading, and allows users to save working proxies in TXT or JSON format.

![Ekran görüntüsü 2025-06-03 143501](https://github.com/user-attachments/assets/9cf9c858-190b-4f24-b448-de606edc1c50)
![Ekran görüntüsü 2025-06-03 143516](https://github.com/user-attachments/assets/d811edd5-1132-4b01-9282-490f5b8f4791)

## Key Features

- **Multi-Source Support**:  
  Collects proxies from popular sources such as Free-Proxy-List.net, Geonode, ProxyScrape, ProxyNova, and more.

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

1. Clone this repository:
   ```bash
   git clone https://github.com/cangurel81/NethyX-Proxy-Scraper.git
   pip install -r requirements.txt
   python NethyX.py

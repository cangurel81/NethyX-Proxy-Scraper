import sys
import os
import re
import base64
import requests
import threading
import time
import json
from bs4 import BeautifulSoup
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                           QPushButton, QLabel, QTextEdit, QProgressBar, QFileDialog,
                           QMessageBox, QTabWidget, QComboBox, QCheckBox, QSpinBox, QGroupBox,
                           QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon, QColor, QPalette

# Düz metin proxy listelerinde geçerli ip:port satırı
IP_PORT_PATTERN = re.compile(r'^(\d{1,3}(?:\.\d{1,3}){3}):(\d{1,5})$')


def _js_int(expression):
    """'2+1' veya '6-1' gibi basit ifadeleri sayiya cevir."""
    total = 0
    sign = 1
    for token in re.findall(r'[+-]|\d+', expression):
        if token == '+':
            sign = 1
        elif token == '-':
            sign = -1
        else:
            total += sign * int(token)
    return total


def decode_proxynova_ip(cell_html):
    """ProxyNova IP'yi document.write + substring/atob/fromCharCode ile yazar; coz."""
    match = re.search(r'document\.write\((.*?)\)\s*</script>', cell_html, re.S)
    if not match:
        return None

    expression = match.group(1)
    pieces = []

    for m in re.finditer(r'"([^"]*)"\.substring\(\s*([^)]*?)\s*\)', expression):
        text = m.group(1)
        args = [_js_int(a) for a in m.group(2).split(',')]
        if len(args) == 2:
            pieces.append((m.start(), text[args[0]:args[1]]))

    for m in re.finditer(r'atob\("([^"]+)"\)', expression):
        try:
            pieces.append((m.start(), base64.b64decode(m.group(1)).decode('ascii')))
        except Exception:
            pass

    for m in re.finditer(
            r'\[([\d,\s]+)\]\.map\(\(code\)\s*=>\s*String\.fromCharCode\(code(?:\s*-\s*(\d+))?\)\)',
            expression):
        delta = int(m.group(2) or 0)
        chars = ''.join(chr(int(n) - delta) for n in m.group(1).split(',') if n.strip())
        pieces.append((m.start(), chars))

    pieces.sort(key=lambda item: item[0])
    ip = ''.join(piece for _, piece in pieces)
    return ip if IP_PORT_PATTERN.match(ip + ':0') else None

class Proxy:
    def __init__(self, ip, port, country=None, city=None, anonymity=None, speed=0, uptime=0, last_checked=None, https=False, translator=None):
        self.ip = ip
        self.port = port
        self._translator = translator
        self.country = country if country is not None else self._tr('unknown')
        self.city = city if city is not None else self._tr('unknown')
        self.anonymity = anonymity if anonymity is not None else self._tr('unknown')
        self.speed = speed
        self.uptime = uptime
        self.last_checked = last_checked if last_checked is not None else self._tr('unknown')
        self.https = https
        self.response_time = 0

    def _tr(self, key):
        if self._translator:
            return self._translator(key)
        return key

    @property
    def address(self):
        return f"{self.ip}:{self.port}"
    
    def to_dict(self):
        return {
            "ip": self.ip,
            "port": self.port, 
            "country": self.country,
            "city": self.city,
            "anonymity": self.anonymity,
            "speed": self.speed,
            "uptime": self.uptime,
            "last_checked": self.last_checked,
            "https": self.https,
            "response_time": self.response_time
        }

    @classmethod 
    def from_dict(cls, data, translator=None):
        return cls(
            ip=data.get("ip", ""),
            port=data.get("port", ""),
            country=data.get("country", None),
            city=data.get("city", None), 
            anonymity=data.get("anonymity", None),
            speed=data.get("speed", 0),
            uptime=data.get("uptime", 0),
            last_checked=data.get("last_checked", None),
            https=data.get("https", False),
            translator=translator
        )

class ProxyTester(QThread):
    update_signal = pyqtSignal(Proxy, int)
    finished_signal = pyqtSignal(list)
    
    def __init__(self, proxies, timeout=5, max_workers=50):
        super().__init__()
        self.proxies = proxies
        self.timeout = timeout
        self.max_workers = max_workers
        self.working_proxies = []
        self.is_running = True
        self.lock = threading.Lock()
        self.processed_count = 0
        
    def run(self):
        total = len(self.proxies)
        proxy_chunks = []
        chunk_size = min(20, max(1, total // self.max_workers))
        
        for i in range(0, total, chunk_size):
            proxy_chunks.append(self.proxies[i:i + chunk_size])
        
        threads = []
        for chunk in proxy_chunks:
            if not self.is_running:
                break
                
            thread = threading.Thread(target=self.process_chunk, args=(chunk, total))
            thread.daemon = True
            threads.append(thread)
            thread.start()
            
            active_threads = [t for t in threads if t.is_alive()]
            while len(active_threads) >= self.max_workers:
                time.sleep(0.1)
                active_threads = [t for t in threads if t.is_alive()]
        
        for thread in threads:
            if thread.is_alive():
                thread.join()
                
        self.finished_signal.emit(self.working_proxies)
    
    def test_proxy(self, proxy):
        try:
            proxy_dict = {
                'http': f'http://{proxy.address}',
                'https': f'http://{proxy.address}'
            }
            
            start_time = time.time()
            response = requests.head('https://www.google.com', 
                                  proxies=proxy_dict, 
                                  timeout=self.timeout,
                                  allow_redirects=True)
            end_time = time.time()
            response_time = int((end_time - start_time) * 1000)  # in milliseconds
            
            return response.status_code < 400, response_time
        except:
            return False, 0
    
    def process_chunk(self, proxies, total):
        for proxy in proxies:
            if not self.is_running:
                break
                
            result, response_time = self.test_proxy(proxy)
            
            with self.lock:
                self.processed_count += 1
                progress = int(self.processed_count / total * 100)
                
                if result:
                    proxy.response_time = response_time
                    self.working_proxies.append (proxy)
                    
                self.update_signal.emit(proxy, progress)
            
    def stop(self):
        self.is_running = False

class ProxyScraper(QThread):
    update_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(list)
    
    def __init__(self, sources, translator):
        super().__init__()
        self.sources = sources
        self.translator = translator
        self.proxies = []
        self.is_running = True
        
    def run(self):
        self.proxies = []
        
        for source in self.sources:
            if not self.is_running:
                break
                
            self.update_signal.emit(self.translator('scraping_from').format(source=source['name']))
            try:
                new_proxies_raw = source['function']()
                new_proxies = []
                for p_data in new_proxies_raw:
                    if isinstance(p_data, Proxy):
                        p_data._translator = self.translator
                        new_proxies.append(p_data)
                    elif isinstance(p_data, dict):
                         new_proxies.append(Proxy.from_dict(p_data, translator=self.translator))

                self.proxies.extend(new_proxies)
                self.update_signal.emit(self.translator('found_proxies_from').format(count=len(new_proxies), source=source['name']))
            except Exception as e:
                self.update_signal.emit(self.translator('error_scraping').format(source=source['name'], error=str(e)))
        
        unique_proxies = {}
        for proxy in self.proxies:
            if proxy.address not in unique_proxies:
                unique_proxies[proxy.address] = proxy
        
        self.proxies = list(unique_proxies.values())
        for proxy in self.proxies:
             if not hasattr(proxy, '_translator') or proxy._translator is None:
                 proxy._translator = self.translator

        self.update_signal.emit(self.translator('total_unique_found').format(count=len(self.proxies)))
        self.finished_signal.emit(self.proxies)
    
    def stop(self):
        self.is_running = False

class ProxyScraperApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NethyX")
        self.setMinimumSize(800, 600)
        self.languages = {
            'en': {
                'app_title': "NethyX Proxy Scraper",
                'tab_scrape': "Proxy Fetch",
                'tab_test': "Proxy Test",
                'source_group': "Proxy Sources",
                'scrape_btn': "Fetch Proxies",
                'stop_scrape_btn': "Stop",
                'log_ready': "Ready",
                'test_settings': "Test Settings",
                'timeout': "Timeout (seconds):",
                'threads': "Parallel Threads:",
                'test_btn': "Test Proxies",
                'stop_test_btn': "Stop",
                'progress': "Progress",
                'results_columns': ["IP:Port", "Status", "Country", "City", "Anonymity", "Speed (ms)", "Uptime (%)", "Last Checked", "HTTPS"],
                'save_btn': "Save Working Proxies",
                'status_label': "Ready",
                'company': "WebAdHere Software",
                'unknown': "Unknown",
                'yes': "Yes",
                'no': "No",
                'warning': "Warning",
                'success': "Success",
                'error': "Error",
                'save_format': "Save Format",
                'save_format_text': "In which format do you want to save the proxies?",
                'scraping_from': "Fetching proxies from {source}...",
                'found_proxies_from': "{count} proxies found - {source}",
                'error_scraping': "Error: {source} - {error}",
                'total_unique_found': "Total {count} unique proxies found",
                'scraping_stopped': "Proxy fetching stopped",
                'testing_proxies': "Testing proxies...",
                'testing_stopped': "Proxy testing stopped",
                'proxy_working': "✅ {address} working (Response time: {time} ms)",
                'proxy_not_working': "❌ {address} not working",
                'status_working': "Working",
                'status_not_working': "Not Working",
                'test_complete_found': "Test completed. {count} working proxies found.",
                'save_working_proxies_found': "{count} working proxies found",
                'select_source_warning': "Please select at least one proxy source.",
                'no_proxies_to_test_warning': "No proxies found to test.",
                'no_working_proxies_warning': "No working proxies found to save.",
                'save_success': "Proxies saved successfully: {count}",
                'save_error': "Error saving file: {error}",
                'saving_title': "Save Format"
            }
        }
        self.current_language = 'en'
        try:
            if getattr(sys, 'frozen', False):
                application_path = sys._MEIPASS
            else:
                application_path = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(application_path, "prxy.ico")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
            else:
                print(f"Icon file not found: {icon_path}")
        except Exception as e:
            print(f"Icon loading error: {str(e)}")
        self.proxies = []
        self.working_proxies = []
        self.scraper_thread = None
        self.tester_thread = None
        self.setup_ui()

    def translate(self, key):
        return self.languages['en'].get(key, key)

    def setup_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)
        self.title_label = QLabel(self.translate('app_title'))
        self.title_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        self.title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.title_label)
        self.tab_widget = QTabWidget()
        self.scraper_tab = QWidget()
        self.scraper_layout = QVBoxLayout(self.scraper_tab)
        self.sources_group = QGroupBox(self.translate('source_group'))
        sources_layout = QVBoxLayout(self.sources_group)
        self.source_checkboxes = []
        for source in self.get_proxy_sources():
            checkbox = QCheckBox(source['name'])
            checkbox.setChecked(True)
            self.source_checkboxes.append((checkbox, source))
            sources_layout.addWidget(checkbox)
        self.scraper_layout.addWidget(self.sources_group)
        scraper_buttons_layout = QHBoxLayout()
        self.scrape_button = QPushButton(self.translate('scrape_btn'))
        self.scrape_button.clicked.connect(self.start_scraping)
        scraper_buttons_layout.addWidget(self.scrape_button)
        self.stop_scrape_button = QPushButton(self.translate('stop_scrape_btn'))
        self.stop_scrape_button.clicked.connect(self.stop_scraping)
        self.stop_scrape_button.setEnabled(False)
        scraper_buttons_layout.addWidget(self.stop_scrape_button)
        self.scraper_layout.addLayout(scraper_buttons_layout)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.scraper_layout.addWidget(self.log_text)
        self.tester_tab = QWidget()
        self.tester_layout = QVBoxLayout(self.tester_tab)
        self.test_settings_group = QGroupBox(self.translate('test_settings'))
        test_settings_layout = QHBoxLayout(self.test_settings_group)
        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(QLabel(self.translate('timeout')))
        self.timeout_spinbox = QSpinBox()
        self.timeout_spinbox.setRange(1, 30)
        self.timeout_spinbox.setValue(3)
        timeout_layout.addWidget(self.timeout_spinbox)
        test_settings_layout.addLayout(timeout_layout)
        threads_layout = QHBoxLayout()
        threads_layout.addWidget(QLabel(self.translate('threads')))
        self.threads_spinbox = QSpinBox()
        self.threads_spinbox.setRange(10, 200)
        self.threads_spinbox.setValue(os.cpu_count() * 5 if os.cpu_count() else 50)
        self.threads_spinbox.setSingleStep(10)
        threads_layout.addWidget(self.threads_spinbox)
        test_settings_layout.addLayout(threads_layout)
        self.tester_layout.addWidget(self.test_settings_group)
        test_buttons_layout = QHBoxLayout()
        self.test_button = QPushButton(self.translate('test_btn'))
        self.test_button.clicked.connect(self.start_testing)
        self.test_button.setEnabled(False)
        test_buttons_layout.addWidget(self.test_button)
        self.stop_test_button = QPushButton(self.translate('stop_test_btn'))
        self.stop_test_button.clicked.connect(self.stop_testing)
        self.stop_test_button.setEnabled(False)
        test_buttons_layout.addWidget(self.stop_test_button)
        self.tester_layout.addLayout(test_buttons_layout)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.tester_layout.addWidget(self.progress_bar)
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(9)
        self.results_table.setHorizontalHeaderLabels(self.translate('results_columns'))
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.setAlternatingRowColors(True)
        self.tester_layout.addWidget(self.results_table)
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setVisible(False)
        save_buttons_layout = QHBoxLayout()
        self.save_button = QPushButton(self.translate('save_btn'))
        self.save_button.clicked.connect(self.save_proxies)
        self.save_button.setEnabled(False)
        save_buttons_layout.addWidget(self.save_button)
        self.tester_layout.addLayout(save_buttons_layout)
        self.tab_widget.addTab(self.scraper_tab, self.translate('tab_scrape'))
        self.tab_widget.addTab(self.tester_tab, self.translate('tab_test'))
        main_layout.addWidget(self.tab_widget)
        status_layout = QHBoxLayout()
        self.status_label = QLabel(self.translate('status_label'))
        status_layout.addWidget(self.status_label)
        self.company_label = QLabel(self.translate('company'))
        self.company_label.setAlignment(Qt.AlignRight)
        status_layout.addWidget(self.company_label)
        main_layout.addLayout(status_layout)
        self.setCentralWidget(central_widget)

    def get_proxy_sources(self):
        return [
            {
                'name': 'Free-Proxy-List.net',
                'function': self.scrape_free_proxy_list
            },
            {
                'name': 'Geonode',
                'function': self.scrape_geonode
            },
            {
                'name': 'ProxyScrape',
                'function': self.scrape_proxyscrape
            },
            {
                'name': 'Hidemy.name',
                'function': self.scrape_hidemy_name
            },
            {
                'name': 'ProxyNova',
                'function': self.scrape_proxynova
            },
            {
                'name': 'PubProxy',
                'function': self.scrape_pubproxy
            },
            {
                'name': 'SSLProxies',
                'function': self.scrape_sslproxies
            },
            {
                'name': 'TheSpeedX (GitHub)',
                'function': self.scrape_thespeedx
            },
            {
                'name': 'Monosans (GitHub)',
                'function': self.scrape_monosans
            },
            {
                'name': 'Clarketm (GitHub)',
                'function': self.scrape_clarketm
            },
            {
                'name': 'Vakhov Fresh (GitHub)',
                'function': self.scrape_vakhov
            },
            {
                'name': 'ProxySpace.pro',
                'function': self.scrape_proxyspace
            },
            {
                'name': 'Mmpx12 (GitHub)',
                'function': self.scrape_mmpx12
            },
            {
                'name': 'Roosterkid (GitHub)',
                'function': self.scrape_roosterkid
            },
            {
                'name': 'IPLocate (GitHub)',
                'function': self.scrape_iplocate
            }
        ]
    
    def scrape_free_proxy_list(self):
        proxies = []
        try:
            response = self._http_get('https://free-proxy-list.net/')
            soup = BeautifulSoup(response.text, 'html.parser')
            # Site 2024'te tablo yapisini degistirdi: ip ve port tek hucrede
            table = soup.select_one('table.table-striped')
            if not table:
                return proxies

            for row in table.find_all('tr')[1:]:
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue

                match = IP_PORT_PATTERN.match(cells[0].get_text(strip=True))
                if not match:
                    continue

                protocol = cells[1].get_text(strip=True).lower() if len(cells) > 1 else ''
                country = cells[3].get_text(strip=True) if len(cells) > 3 else cells[2].get_text(strip=True)
                anonymity = cells[4].get_text(strip=True) if len(cells) > 4 else None
                https_cell = cells[5].get_text(strip=True).lower() if len(cells) > 5 else ''
                last_checked = cells[-1].get_text(strip=True)

                proxies.append(Proxy(
                    ip=match.group(1),
                    port=match.group(2),
                    country=country,
                    anonymity=anonymity,
                    last_checked=last_checked,
                    https=('https' in protocol) or https_cell == 'yes'
                ))
        except Exception as e:
            print(f"Free-Proxy-List scraping error: {e}")

        return proxies
    
    def scrape_geonode(self):
        proxies = []
        response = requests.get('https://proxylist.geonode.com/api/proxy-list?limit=300&page=1&sort_by=lastChecked&sort_type=desc', timeout=15)
        data = response.json()
        
        for proxy_data in data.get('data', []):
            ip = proxy_data.get('ip')
            port = proxy_data.get('port')
            if ip and port:
                country = proxy_data.get('country', 'Unknown')
                city = proxy_data.get('city', 'Unknown')
                anonymity = proxy_data.get('anonymityLevel', 'Unknown')
                last_checked = proxy_data.get('lastChecked', 'Unknown')
                speed = proxy_data.get('speed', 0)
                uptime = proxy_data.get('upTime', 0)
                protocols = proxy_data.get('protocols', [])
                https = 'https' in protocols
                
                proxy = Proxy(
                    ip=ip,
                    port=port,
                    country=country,
                    city=city,
                    anonymity=anonymity,
                    speed=speed,
                    uptime=uptime,
                    last_checked=last_checked,
                    https=https
                )
                proxies.append(proxy)
        
        return proxies
    
    def scrape_proxyscrape(self):
        # v4 birincil, v2 yedek
        proxies = self._scrape_plain_list(
            'https://api.proxyscrape.com/v4/free-proxy-list/get'
            '?request=display_proxies&protocol=http&proxy_format=ipport&format=text')

        if not proxies:
            proxies = self._scrape_plain_list(
                'https://api.proxyscrape.com/v2/?request=getproxies&protocol=http'
                '&timeout=10000&country=all&ssl=all&anonymity=all')

        return proxies

    def scrape_hidemy_name(self):
        proxies = []
        try:
            response = self._http_get('https://hidemy.name/en/proxy-list/')
            soup = BeautifulSoup(response.text, 'html.parser')
            # 'table_block' sinifi kaldirildi; en buyuk tabloyu al
            table = None
            for candidate in soup.find_all('table'):
                if len(candidate.find_all('tr')) > 10:
                    table = candidate
                    break

            if table:
                for row in table.find_all('tr')[1:]:
                    cells = row.find_all('td')
                    if len(cells) < 7:
                        continue

                    ip = cells[0].get_text(strip=True)
                    port = cells[1].get_text(strip=True)
                    if not IP_PORT_PATTERN.match(f"{ip}:{port}"):
                        continue

                    location = cells[2].get_text(strip=True)
                    country, _, city = location.partition(' - ')

                    speed = 0
                    speed_match = re.search(r'\d+', cells[3].get_text(strip=True))
                    if speed_match:
                        speed = int(speed_match.group())

                    proxy_type = cells[4].get_text(strip=True).upper()
                    anonymity = cells[5].get_text(strip=True)
                    last_checked = cells[6].get_text(strip=True)

                    proxies.append(Proxy(
                        ip=ip,
                        port=port,
                        country=country or None,
                        city=city or None,
                        anonymity=anonymity,
                        speed=speed,
                        last_checked=last_checked,
                        https='HTTPS' in proxy_type
                    ))
        except Exception as e:
            print(f"Hidemy.name scraping error: {e}")

        return proxies
    
    def scrape_proxynova(self):
        proxies = []
        try:
            response = self._http_get('https://www.proxynova.com/proxy-server-list/')
            soup = BeautifulSoup(response.text, 'html.parser')

            table = soup.select_one('table#tbl_proxy_list')
            if not table:
                return proxies

            # Sutunlar: IP (script ile gizli), Port, Son kontrol, Hiz, Uptime, Ulke, Anonimlik
            for row in table.select('tbody tr'):
                cells = row.find_all('td')
                if len(cells) < 7:
                    continue

                ip = decode_proxynova_ip(str(cells[0]))
                port = cells[1].get_text(strip=True)
                if not ip or not IP_PORT_PATTERN.match(f"{ip}:{port}"):
                    continue

                speed = 0
                speed_match = re.search(r'(\d+)\s*ms', cells[3].get_text(' ', strip=True))
                if speed_match:
                    speed = int(speed_match.group(1))

                uptime_match = re.search(r'\d+', cells[4].get_text(strip=True))
                uptime = int(uptime_match.group()) if uptime_match else 0

                country_text = cells[5].get_text(' ', strip=True)
                country, _, city = country_text.partition(' - ')

                proxies.append(Proxy(
                    ip=ip,
                    port=port,
                    country=country or None,
                    city=city or None,
                    anonymity=cells[6].get_text(strip=True),
                    speed=speed,
                    uptime=uptime,
                    last_checked=cells[2].get_text(strip=True) or None
                ))
        except Exception as e:
            print(f"ProxyNova scraping error: {e}")

        return proxies
    
    def scrape_pubproxy(self):
        proxies = []
        try:
            response = requests.get('http://pubproxy.com/api/proxy?limit=20&format=json&https=true', timeout=15)
            data = response.json()
            
            for proxy_data in data.get('data', []):
                ip = proxy_data.get('ip')
                port = proxy_data.get('port')
                if ip and port:
                    country = proxy_data.get('country', 'Unknown')
                    city = proxy_data.get('city', 'Unknown')
                    anonymity = proxy_data.get('proxy_level', 'Unknown')
                    https = proxy_data.get('support', {}).get('https', False)
                    last_checked = proxy_data.get('last_checked', 'Unknown')
                    
                    proxy = Proxy(
                        ip=ip,
                        port=port,
                        country=country,
                        city=city,
                        anonymity=anonymity,
                        https=https,
                        last_checked=last_checked
                    )
                    proxies.append(proxy)
        except Exception as e:
            print(f"PubProxy API error: {e}")
        
        return proxies
    
    def scrape_sslproxies(self):
        proxies = []
        try:
            response = self._http_get('https://www.sslproxies.org/')
            soup = BeautifulSoup(response.text, 'html.parser')
            # 'proxylisttable' id'si kaldirildi; ip:port artik tek hucrede
            table = soup.select_one('table.table-striped')
            if not table:
                return proxies

            for row in table.find_all('tr')[1:]:
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue

                match = IP_PORT_PATTERN.match(cells[0].get_text(strip=True))
                if not match:
                    continue

                country = cells[1].get_text(strip=True) if len(cells) > 1 else None
                protocol = cells[2].get_text(strip=True).upper() if len(cells) > 2 else ''
                last_checked = cells[-1].get_text(strip=True)

                proxies.append(Proxy(
                    ip=match.group(1),
                    port=match.group(2),
                    country=country,
                    last_checked=last_checked,
                    https=(protocol != 'HTTP')
                ))
        except Exception as e:
            print(f"SSLProxies scraping error: {e}")

        return proxies
    
    # ---- ortak yardımcılar ----
    def _http_get(self, url, timeout=15):
        """Zaman aşımı ve gerçekçi User-Agent ile istek at."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
            'Accept': 'text/plain,text/html,*/*'
        }
        return requests.get(url, headers=headers, timeout=timeout)

    def _scrape_plain_list(self, url):
        """ip:port satırlarından oluşan düz metin listelerini ayrıştır."""
        proxies = []
        try:
            response = self._http_get(url)
            if response.status_code != 200:
                print(f"Plain list error {response.status_code}: {url}")
                return proxies

            for line in response.text.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                match = IP_PORT_PATTERN.match(line)
                if match:
                    proxies.append(Proxy(ip=match.group(1), port=match.group(2)))
        except Exception as e:
            print(f"Plain list scraping error ({url}): {e}")

        return proxies

    # ---- düz metin (GitHub / API) kaynakları ----
    def scrape_thespeedx(self):
        return self._scrape_plain_list(
            'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt')

    def scrape_monosans(self):
        return self._scrape_plain_list(
            'https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt')

    def scrape_clarketm(self):
        return self._scrape_plain_list(
            'https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt')

    def scrape_vakhov(self):
        return self._scrape_plain_list(
            'https://vakhov.github.io/fresh-proxy-list/http.txt')

    def scrape_proxyspace(self):
        return self._scrape_plain_list('https://proxyspace.pro/http.txt')

    def scrape_mmpx12(self):
        return self._scrape_plain_list(
            'https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt')

    def scrape_roosterkid(self):
        return self._scrape_plain_list(
            'https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt')

    def scrape_iplocate(self):
        return self._scrape_plain_list(
            'https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/http.txt')

    def start_scraping(self):
        selected_sources = []
        for checkbox, source in self.source_checkboxes:
            if checkbox.isChecked():
                selected_sources.append(source)
        
        if not selected_sources:
            QMessageBox.warning(self, self.translate('warning'), self.translate('select_source_warning'))
            return
        
        self.scrape_button.setEnabled(False)
        self.stop_scrape_button.setEnabled(True)
        self.test_button.setEnabled(False)
        self.log_text.clear()
        self.status_label.setText(self.translate('scraping_from').format(source=''))
        
        self.scraper_thread = ProxyScraper(selected_sources, self.translate)
        self.scraper_thread.update_signal.connect(self.update_scraper_log)
        self.scraper_thread.finished_signal.connect(self.scraping_finished)
        self.scraper_thread.start()
    
    def stop_scraping(self):
        if self.scraper_thread and self.scraper_thread.isRunning():
            self.scraper_thread.stop()
            self.status_label.setText(self.translate('scraping_stopped'))
            self.scrape_button.setEnabled(True)
            self.stop_scrape_button.setEnabled(False)
    
    def update_scraper_log(self, message):
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
    
    def scraping_finished(self, proxies):
        self.proxies = proxies
        self.scrape_button.setEnabled(True)
        self.stop_scrape_button.setEnabled(False)
        self.test_button.setEnabled(len(self.proxies) > 0)
        self.status_label.setText(self.translate('total_unique_found').format(count=len(self.proxies)))
        
        self.log_text.append(f"\n{self.translate('total_unique_found').format(count=len(self.proxies))}")
    
    def start_testing(self):
        if not self.proxies:
            QMessageBox.warning(self, self.translate('warning'), self.translate('no_proxies_to_test_warning'))
            return
        
        self.test_button.setEnabled(False)
        self.stop_test_button.setEnabled(True)
        self.save_button.setEnabled(False)
        self.results_text.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText(self.translate('testing_proxies'))
        
        timeout = self.timeout_spinbox.value()
        max_workers = self.threads_spinbox.value()
        
        self.tester_thread = ProxyTester(self.proxies, timeout, max_workers)
        self.tester_thread.update_signal.connect(self.update_test_results)
        self.tester_thread.finished_signal.connect(self.testing_finished)
        self.tester_thread.start()
    
    def stop_testing(self):
        if self.tester_thread and self.tester_thread.isRunning():
            self.tester_thread.stop()
            self.status_label.setText(self.translate('testing_stopped'))
            self.test_button.setEnabled(True)
            self.stop_test_button.setEnabled(False)
    
    def update_test_results(self, proxy, progress):
        if hasattr(proxy, 'response_time') and proxy.response_time > 0:
            message = self.translate('proxy_working').format(address=proxy.address, time=proxy.response_time)
        else:
            message = self.translate('proxy_not_working').format(address=proxy.address)
            
        self.results_text.append(message)
        self.progress_bar.setValue(progress)
        
        row_position = self.results_table.rowCount()
        self.results_table.insertRow(row_position)
        
        self.results_table.setItem(row_position, 0, QTableWidgetItem(proxy.address))
        
        is_working = hasattr(proxy, 'response_time') and proxy.response_time > 0
        status = self.translate('status_working') if is_working else self.translate('status_not_working')
        status_item = QTableWidgetItem(status)
        status_item.setForeground(QColor("green" if is_working else "red"))
        self.results_table.setItem(row_position, 1, status_item)
        
        self.results_table.setItem(row_position, 2, QTableWidgetItem(proxy.country))
        self.results_table.setItem(row_position, 3, QTableWidgetItem(proxy.city))
        self.results_table.setItem(row_position, 4, QTableWidgetItem(proxy.anonymity))
        
        speed_text = str(proxy.response_time) if hasattr(proxy, 'response_time') and proxy.response_time > 0 else str(proxy.speed) if proxy.speed > 0 else "-"
        self.results_table.setItem(row_position, 5, QTableWidgetItem(speed_text))
        
        self.results_table.setItem(row_position, 6, QTableWidgetItem(str(proxy.uptime) if proxy.uptime > 0 else "-"))
        self.results_table.setItem(row_position, 7, QTableWidgetItem(proxy.last_checked))
        
        https_text = self.translate('yes') if proxy.https else self.translate('no')
        self.results_table.setItem(row_position, 8, QTableWidgetItem(https_text))
        
        self.results_table.scrollToBottom()
    
    def testing_finished(self, working_proxies):
        self.working_proxies = working_proxies
        self.test_button.setEnabled(True)
        self.stop_test_button.setEnabled(False)
        self.save_button.setEnabled(len(self.working_proxies) > 0)
        
        self.results_text.append(f"\n{self.translate('test_complete_found').format(count=len(self.working_proxies))}")
        self.status_label.setText(self.translate('save_working_proxies_found').format(count=len(self.working_proxies)))
        
        for row in range(self.results_table.rowCount()):
            ip_port = self.results_table.item(row, 0).text()
            for proxy in self.working_proxies:
                if proxy.address == ip_port:
                    for col in range(self.results_table.columnCount()):
                        item = self.results_table.item(row, col)
                        if item:
                            item.setBackground(QColor(230, 255, 230))
    
    def save_proxies(self):
        if not self.working_proxies:
            QMessageBox.warning(self, self.translate('warning'), self.translate('no_working_proxies_warning'))
            return
        
        format_dialog = QMessageBox()
        format_dialog.setWindowTitle(self.translate('saving_title'))
        format_dialog.setText(self.translate('save_format_text'))
        format_dialog.addButton(self.translate('save_format') + " (TXT)", QMessageBox.ActionRole)
        format_dialog.addButton(self.translate('save_format') + " (JSON)", QMessageBox.ActionRole)
        format_dialog.addButton(self.translate('stop_scrape_btn'), QMessageBox.RejectRole)
        
        result = format_dialog.exec_()
        
        if result == 2:
            return
        
        if result == 0:
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Proxies", 
                                                     os.path.expanduser("~/Desktop/working_proxies.txt"),
                                                     "Text Files (*.txt)")
            
            if file_path:
                try:
                    with open(file_path, 'w') as f:
                        for proxy in self.working_proxies:
                            f.write(f"{proxy.address}\n")
                    
                    QMessageBox.information(self, self.translate('success'), self.translate('save_success').format(count=len(self.working_proxies)))
                except Exception as e:
                    QMessageBox.critical(self, self.translate('error'), self.translate('save_error').format(error=str(e)))
        
        elif result == 1:
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Proxies", 
                                                     os.path.expanduser("~/Desktop/working_proxies.json"),
                                                     "JSON Files (*.json)")
            
            if file_path:
                try:
                    proxy_data = [proxy.to_dict() for proxy in self.working_proxies]
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(proxy_data, f, indent=4, ensure_ascii=False)
                    
                    QMessageBox.information(self, self.translate('success'), self.translate('save_success').format(count=len(self.working_proxies)))
                except Exception as e:
                    QMessageBox.critical(self, self.translate('error'), self.translate('save_error').format(error=str(e)))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ProxyScraperApp()
    window.show()
    sys.exit(app.exec_())
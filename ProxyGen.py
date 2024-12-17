import requests, re,random
from bs4 import BeautifulSoup
def get_proxies():
    """
    Fetches a list of proxies from multiple sources and returns them as an array.
    
    Returns:
        list: A list of proxies in the format "IP:Port".
    """
    proxies = []

    # Regex to match IP:Port format
    regex = r"[0-9]+(?:\.[0-9]+){3}:[0-9]+"

    # Fetch proxies from spys.me
    try:
        response = requests.get("https://spys.me/proxy.txt")
        if response.status_code == 200:
            matches = re.finditer(regex, response.text, re.MULTILINE)
            for match in matches:
                proxies.append(match.group())
    except Exception as e:
        print(f"Error fetching proxies from spys.me: {e}")

    # Fetch proxies from free-proxy-list.net
    try:
        response = requests.get("https://free-proxy-list.net/")
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            td_elements = soup.select('.fpl-list .table tbody tr td')
            ips = []
            ports = []
            for i in range(0, len(td_elements), 8):  # IPs and ports are separated by 8 <td>
                ips.append(td_elements[i].text.strip())
                ports.append(td_elements[i + 1].text.strip())
            
            for ip, port in zip(ips, ports):
                proxies.append(f"{ip}:{port}")
    except Exception as e:
        print(f"Error fetching proxies from free-proxy-list.net: {e}")
    
    return proxies

    

def getRandomProxy():
    proxy_list = get_proxies()
    return random.choice(proxy_list)
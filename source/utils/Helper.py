import logging
import urllib.parse
import re
import socket

# The regex pattern to extract the 128 hex chars enode from enode url
enode_pattern = re.compile(r'[0-9a-fA-F]{128}')

class Helper:
    """Helper class"""

    def getHostName(self, url: str) -> str:
        """Get Hostname of an URL

        Args:
            url (str): URL

        Returns:
            str: Hostname
        """
        if url:
            parsed_url = urllib.parse.urlparse(url)
            if parsed_url and parsed_url.hostname:
                return parsed_url.hostname
            
            # Maybe it is not an absolute url: urlparse() and urlsplit() insists on absolute URLs starting with "//"
            parsed_url = urllib.parse.urlparse('//' + url)
            if parsed_url and parsed_url.hostname:
                return parsed_url.hostname
        return None

    def resolveIpAddress(self, dns_name: str) -> str:
        """Resolve the IP address of an DNS name

        Args:
            dns_name (str): The DNS name

        Returns:
            str: IP address as string
        """
        try:
            return socket.gethostbyname(dns_name)
        except socket.error as ex:
            logging.error("%s: %s", ex.strerror, dns_name)
            return None

    def getEnode(self, enodeUrl: str) -> str:
        """Get 128 hex chars enode from enodeUrl

        Args:
            enodeUrl (str): The enode URL, e.g. enode://632176321637217632721@1.2.3.4:30303

        Returns:
            str: The enode (128 hex chars)
        """
        if enodeUrl:
            enodeList = enode_pattern.findall(enodeUrl)
            if len(enodeList) > 0:
                return enodeList[0]
        return None

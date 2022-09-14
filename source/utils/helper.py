import logging
import urllib.parse
import re
import socket
from functools import reduce

# The regex pattern to extract the 128 hex chars enode from enode url
enode_pattern = re.compile(r'[0-9a-fA-F]{128}')


class Helper:
    """Helper class"""

    def get_host_name(self, url: str) -> str:
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

            # Maybe it is not an absolute url:
            # urlparse() and urlsplit() insists on absolute URLs starting with "//"
            parsed_url = urllib.parse.urlparse('//' + url)
            if parsed_url and parsed_url.hostname:
                return parsed_url.hostname
        return None

    def resolve_ip_address(self, dns_name: str) -> str:
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

    def get_enode_from_url(self, enode_url: str) -> str:
        """Get 128 hex chars enode from enode_url

        Args:
            enode_url (str): The enode URL, e.g. enode://632176321637217632721@1.2.3.4:30303

        Returns:
            str: The enode (128 hex chars)
        """
        if enode_url:
            enode_list = enode_pattern.findall(enode_url)
            if len(enode_list) > 0:
                return enode_list[0]
        return None

    def deep_get(self, dictionary, keys, default=None):
        """See
            https://stackoverflow.com/questions/25833613/safe-method-to-get-value-of-nested-dictionary

        Args:
            dictionary (_type_): _description_
            keys (_type_): _description_
            default (_type_, optional): _description_. Defaults to None.

        Returns:
            _type_: _description_
        """
        return reduce(lambda d, key: d.get(key, default) if isinstance(d, dict) else default, keys.split("."), dictionary)

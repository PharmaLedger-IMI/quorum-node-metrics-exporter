"""This module contains the Config and loading procedures for the config

"""
import logging
import json

class Config:
    """Encapsulates the application configuration.
    """

    def __init__(self):
        self._rpc_url = None
        self._namespace = None
        self._deployment = None
        self._peers = {}

    def load(self, config_object) -> bool:
        """Load the config from an object

        Args:
            config_object (_type_): the object containing the config

        Returns:
            bool: True if successful else False
        """
        self._rpc_url = None
        self._namespace = None
        self._deployment = None
        self._peers = {}

        if config_object is None:
            logging.error("'config_object' not set.")
            return False

        self._rpc_url = config_object.get('rpc_url')
        if not self._rpc_url:
            logging.error(
                "'rpc_url' is not set in config. E.g. 'rpc_url': 'http://quorum-node-0.quorum:8545'")
            return False

        self._namespace = config_object.get('namespace')
        if not self._namespace:
            logging.error(
                "'namespace' is not set in config. E.g. 'namespace': 'quorum'")
            return False

        self._deployment = config_object.get('deployment')
        if not self._deployment:
            logging.error(
                "'deployment' is not set in config. E.g. 'deployment': 'quorum'")
            return False

        peers = config_object.get('peers')
        if not peers:
            logging.error("'peers' is not set in config.")
            return False

        for each in peers:
            enode = each.get('enode')
            company_name = each.get('company-name')
            address = each.get('enodeAddress')
            port = each.get('enodeAddressPort')

            if enode is None or company_name is None or address is None or port is None:
                logging.error(
                    "'enode', 'company-name', 'enodeAddress', 'enodeAddressPort' must be set at a peer object.")
                return False

            # Check if company_name is unique. If not, use company_name plus first 5 chars of enode
            count_same_company_name = len(list(filter(
                lambda peer: peer['company-name'] == company_name, peers)))  # pylint: disable=W0640
            name = None
            if count_same_company_name > 1:
                name = company_name + " (" + enode[0:5] + ")"
            else:
                name = company_name

            self._peers[enode] = PeerConfig(name, enode, address, port)

        return True

    @property
    def rpc_url(self) -> str:
        """The RPC URL

        Returns:
            str: The RPC URL
        """
        return self._rpc_url

    @property
    def peers(self) -> dict:
        """A dictionary of peers

        Returns:
            dict: dcitionary of peers. Key is the enode, value is of type PeerConfig
        """
        return self._peers

    @property
    def deployment(self) -> str:
        """The Name of the K8S deployment of the Quorum node

        Returns:
            str: Name of the K8S deployment
        """
        return self._deployment

    @property
    def namespace(self) -> str:
        """The Namespace of the K8S deployment of the Quorum node

        Returns:
            str: Namespace of the K8S deployment
        """
        return self._namespace


class PeerConfig:
    """Peer Data
    """

    def __init__(self, name: str, enode: str, address: str, port: str):
        self._name = name
        self._enode = enode
        self._address = address
        self._port = port

    @property
    def name(self) -> str:
        """Name of the peer

        Returns:
            str: Name of the peer
        """
        return self._name

    @property
    def enode(self) -> str:
        """Enode of the peer

        Returns:
            str: Enode of the peer
        """
        return self._enode

    @property
    def address(self) -> str:
        """IP Address of the peer

        Returns:
            str: IP Address of the peer
        """
        return self._address

    @property
    def port(self) -> str:
        """Port number of the peer

        Returns:
            str: Port number of the peer
        """
        return self._port

def load(filename:str = 'config.json') -> Config:
    """Load the application configuration

    Args:
        filename (str, optional): The configuration file name. Defaults to 'config.json'.

    Returns:
        Config: The application configuration or None on error during load.
    """
    with open(file=filename, mode='r', encoding='utf-8') as file:
        config_object = json.load(file)

    config = Config()
    if config.load(config_object) is True:
        return config

    return None

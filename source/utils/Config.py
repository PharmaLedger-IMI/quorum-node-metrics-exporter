import logging

class Config:
    """Encapsulates the application configuration.
    """
    def __init__(self):
        self.rpc_url = None
        self.peers = {}

    def load(self, config_object) -> bool:
        """Load the config from an object

        Args:
            config_object (_type_): the object containing the config

        Returns:
            bool: True if successful else False
        """
        self.rpc_url = None
        self.peers = {}

        if config_object is None:
            logging.error("'config_object' not set.")
            return False

        rpc_url = config_object.get('rpc_url')
        if not rpc_url:
            logging.error("'rpc_url' is not set in config. E.g. 'rpc_url': 'http://quorum-node-0.quorum:8545'")
            return False
        self.rpc_url = rpc_url

        peers = config_object.get('peers')
        if not peers:
            logging.error("'peers' is not set in config.")
            return False

        for each in peers:
            enode = each.get('enode')
            company_name = each.get('company-name')
            if not enode or not company_name:
                logging.error("'enode' or 'company-name' not set at a peer object.")
                return False
            
            # Check is company_name is unique. If not use company_name plus first 5 chars of enode
            count_same_company_name = len(list(filter(lambda peer: peer['company-name'] == company_name, peers)))
            if count_same_company_name > 1:
                self.peers[enode] = company_name + " (" + enode[0:5] + ")"
            else:
                self.peers[enode] = company_name

        return True

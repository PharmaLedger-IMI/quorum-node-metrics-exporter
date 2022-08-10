import logging
import requests
from .Config import Config
from .Helper import Helper
from prometheus_client.core import GaugeMetricFamily
from requests.structures import CaseInsensitiveDict

class MetricsProvider:
    """Collects data and provides metrics data.
    """
    def __init__(self, config:Config):

        # The current metrics to be reported on a Prometheus scrape.
        # Note: We cannot use "default" Gauge as the values remain even if the peer does not exists anymore.
        # Therefore we set fresh metrics every time we collect peers information.
        self.current_metrics = []
        self.config = config
        self.helper = Helper()

    def getPeersData(self):
        """Get data of the current peers by querying Quorum nodes RPC endpoint

        Returns:
            _type_: _description_
        """
        headers = CaseInsensitiveDict()
        headers["Content-Type"] = "application/json"
        # https://getblock.io/docs/available-nodes-methods/ETH/JSON-RPC/admin_peers/
        # https://geth.ethereum.org/docs/rpc/ns-admin#admin_peers
        # https://consensys.net/docs/goquorum/en/latest/develop/connecting-to-a-node/
        data = '{"jsonrpc": "2.0","method": "admin_peers","params": [],"id": "getblock.io"}'
        response = requests.post(self.config.rpc_url, headers=headers, data=data)
        
        if response.status_code == 200:
            return response.json().get('result')
        return []

    def createCurrentMetrics(self, instance: str, instance_name: str, peersData: list):
        """Get current data and create metrics

        Args:
            instance (str): _description_
            instance_name (str): _description_
            peersData (list): The current peers data queried from RPC endpoint
        """
        if peersData is None:
            peersData = []

        logging.info("Creating metrics for %s peers - instance=%s, instance_name=%s", len(peersData), ('[None=will be determined from localAddress]' if instance is None else instance), instance_name)

        # Prepare current metrics
        metric_peers = GaugeMetricFamily('quorum_peers', 'Quorum peers by enode', labels=['instance', 'instance_name', 'enode', 'enode_short', 'name'])
        metric_peers_network_direction = GaugeMetricFamily('quorum_peers_network_direction', 'Quorum peers network inbound (1) or outbound (2) by enode', labels=['instance', 'instance_name', 'enode', 'enode_short', 'name'])
        metric_peers_head_block = GaugeMetricFamily('quorum_peers_head_block', 'Quorum peers head block by enode and protocol eth or istanbul', labels=['instance', 'instance_name', 'enode', 'enode_short', 'name', 'protocol'])

        # A dict of all enodes currently connected as peers
        enodes_found = {}

        for each_peer in peersData:
            # enodeUrl = "enode://[HERE IS THE 128 HEX-CHARS LONG ENODE]@1.2.3.4:30303?discport=0"
            enode = self.helper.getEnode(enodeUrl=each_peer.get('enode'))

            # https://github.com/prometheus/client_python
            if enode:
                enode_short = enode[0:20]
                # Remember that enode was found
                enodes_found[enode] = True

                # If instance is not provided, we determine it from network.localAddress
                if instance is None:
                    instance = self.helper.getHostName(each_peer.get('network', {}).get('localAddress'))
                    if instance:
                        instance = instance + ':9545' # add same port as Quorum Node default metrics also do
                    else:
                        instance = ''

                # Get pretty name. If not defined use enode_short instead
                name = self.config.peers.get(enode, enode_short)

                # 1. metric_peers
                # Set value (1) that enode is found
                metric_peers.add_metric([instance, instance_name, enode, enode_short, name], 1)

                # 2. metric_peers_network_direction
                # Set network inbound (1) or outbound (2)
                inbound = each_peer.get('network', {}).get('inbound')
                if inbound == True:
                    metric_peers_network_direction.add_metric([instance, instance_name, enode, enode_short, name], 1)
                elif inbound == False:
                    metric_peers_network_direction.add_metric([instance, instance_name, enode, enode_short, name], 2)

                # 3. metric_peers_head_block
                eth_difficulty = each_peer.get('protocols', {}).get('eth', {}).get("difficulty")
                if eth_difficulty:
                    metric_peers_head_block.add_metric([instance, instance_name, enode, enode_short, name, 'eth'], eth_difficulty)

                istanbul_difficulty = each_peer.get('protocols', {}).get('istanbul', {}).get("difficulty")
                if istanbul_difficulty:
                    metric_peers_head_block.add_metric([instance, instance_name, enode, enode_short, name, 'istanbul'], istanbul_difficulty)

        # Add metrics for all expected peers that are currenty NOT connected
        for each_config_peer_enode in self.config.peers.keys():
            if not enodes_found.get(each_config_peer_enode, False):
                enode = each_config_peer_enode
                enode_short = enode[0:20]
                name = self.config.peers.get(enode, enode_short)

                # 1. metric_peers
                # Set value (0) that enode is NOT found
                metric_peers.add_metric([instance, instance_name, enode, enode_short, name], 0)

                # 2. metric_peers_network_direction
                # Set network not connected (0)
                metric_peers_network_direction.add_metric([instance, instance_name, enode, enode_short, name], 0)

                # 3. metric_peers_head_block
                # WE DO NOT ADD THESE METRICS AS THEY DO NOT MAKE SENSE:
                # Providing a value of zero (0) may also be a correct value, therefore we do not create head block metrics for non connected peers!
                # metric_peers_head_block.add_metric([instance, instance_name, enode, enode_short, name, 'eth'], 0)
                # metric_peers_head_block.add_metric([instance, instance_name, enode, enode_short, name, 'istanbul'], 0)

        # Set current metrics to be reported by CustomCollector in a single atomic operation
        self.current_metrics = [metric_peers, metric_peers_network_direction, metric_peers_head_block]

    def process(self):
        """Processes getting peers info and preparing metrics

        Args:
            rpc_url (str): URL of Quorum nodes RPC endpoint
            known_peers (list): A list of objects of the known peers. Each object contains 'company-name' and 'enode'
        """
        # Get DNS name and IP address of current instance by taking a deeper look at the rpc_url
        instance_dns_name = self.helper.getHostName(url=self.config.rpc_url)

        # We do not use the IP address of the RPC Endpoint as this may be the clusterIp of the service if it is not a headless service.
        # Therefore we determine the instance from network.localAddress
        # instance_ip = resolveIpAddress(dns_name=instance_dns_name) + ':9545' # default metrics also add port

        # Get data of all currently connected peers
        peersData = self.getPeersData()
        # Report metrics for this instance
        self.createCurrentMetrics(instance=None, instance_name=instance_dns_name, peersData=peersData)

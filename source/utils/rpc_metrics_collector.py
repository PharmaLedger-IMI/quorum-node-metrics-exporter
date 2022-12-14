"""Prometheus metrics collector provided by querying the Quorum RPC endpoint
"""
import logging
from typing import Iterable

import requests
from prometheus_client.core import GaugeMetricFamily, Metric
from prometheus_client.registry import Collector
from requests.structures import CaseInsensitiveDict

from .config import Config  # pylint: disable=E0402
from .helper import Helper  # pylint: disable=E0402


class RpcMetricsCollector(Collector):
    """Collects data from Quorum RPC API and provides metrics data.
    """

    def __init__(self, config: Config):
        self._current_metrics = []
        self._config = config
        self._helper = Helper()

    def collect(self) -> Iterable[Metric]:
        """Get the current metrics. Implementation of the Collector

        Returns:
            Iterable[Metric]: The current metrics
        """
        return self._current_metrics

    def _get_peers_data(self):
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
        try:
            response = requests.post(self._config.rpc_url,
                                    headers=headers, data=data, timeout=2.0)
            if response.status_code == 200:
                return response.json().get('result')
        except requests.Timeout:
            pass
        except requests.ConnectionError:
            pass
        return []

    def _create_current_metrics(self, instance_name: str, peers_data: list):
        """Get current data and create metrics

        Args:
            instance_name (str): _description_
            peersData (list): The current peers data queried from RPC endpoint
        """
        if peers_data is None:
            peers_data = []

        logging.info("%s >> Creating metrics for %s peers - instance_name=%s, rpc_url=%s",
                     type(self).__name__, len(peers_data), instance_name, self._config.rpc_url)

        # The current metrics to be reported on a Prometheus scrape.
        # We cannot use "default" Gauge as the values remain even if the peer does not exist anymore
        # Therefore we set fresh metrics every time we collect peers information.
        metric_peers = GaugeMetricFamily(
            'quorum_peers', 'Quorum peers by enode',
            labels=['instance_name', 'enode', 'enode_short', 'name'])
        metric_peers_network_direction = GaugeMetricFamily(
            'quorum_peers_network_direction', 'Quorum peers network inbound (1) or outbound (2) by enode',
            labels=['instance_name', 'enode', 'enode_short', 'name'])
        metric_peers_head_block = GaugeMetricFamily(
            'quorum_peers_head_block', 'Quorum peers head block by enode and protocol eth or istanbul',
            labels=['instance_name', 'enode', 'enode_short', 'name', 'protocol'])

        # A dict of all enodes currently connected as peers
        enodes_connected = {}

        # Add metrics for all connected peers
        for each_peer in peers_data:
            enode = self._set_metrics_for_connected_peer(
                each_peer, instance_name, metric_peers,
                metric_peers_network_direction, metric_peers_head_block)
            if enode is not None:
                enodes_connected[enode] = True

        # Add metrics for all configured/expected peers that are currenty NOT connected
        for each_config_peer_enode in self._config.peers.keys():
            if each_config_peer_enode not in enodes_connected:
                self._set_metrics_for_expected_but_unconnected_peer(
                    each_config_peer_enode, instance_name,
                    metric_peers, metric_peers_network_direction)

        # Set current metrics to be reported by CustomCollector in a single atomic operation
        self._current_metrics = [
            metric_peers, metric_peers_network_direction, metric_peers_head_block]

    def _set_metrics_for_connected_peer(self, each_peer, instance_name: str,
            metric_peers: GaugeMetricFamily,
            metric_peers_network_direction: GaugeMetricFamily,
            metric_peers_head_block: GaugeMetricFamily) -> str:
        """Sets the metrics for a connected

        Args:
            each_peer (_type_): The data of the connected peer
            instance_name (str): The instance name
            metric_peers (GaugeMetricFamily): The metrics if a peer is connected or not
            metric_peers_network_direction (GaugeMetricFamily): Metrics in- or outbound connected
            metric_peers_head_block (GaugeMetricFamily): The metrics for the head block of the peer

        Returns:
            str: The enode or None if enode cannot be determined
        """
        # enode_url = "enode://[HERE IS THE 128 HEX-CHARS LONG ENODE]@1.2.3.4:30303?discport=0"
        enode = self._helper.get_enode_from_url(enode_url=each_peer.get('enode'))
        if enode is None:
            return None

        #
        # Prepare metric labels:
        #
        enode_short = enode[0:20]
        # Get pretty name. If not defined use enode_short instead
        name = enode_short
        if enode in self._config.peers:
            name= self._config.peers[enode].name

        # 1. metric_peers
        # Set value (1) that enode is found
        metric_peers.add_metric([instance_name, enode, enode_short, name], 1)

        # 2. metric_peers_network_direction
        # Set network inbound (1) or outbound (2)
        inbound = self._helper.deep_get(each_peer, 'network.inbound')
        metric_peers_network_direction.add_metric(
            [instance_name, enode, enode_short, name],
            1 if inbound is True else 2)

        # 3. metric_peers_head_block
        eth_difficulty = self._helper.deep_get(
            each_peer, 'protocols.eth.difficulty')
        if eth_difficulty:
            metric_peers_head_block.add_metric(
                [instance_name, enode, enode_short, name, 'eth'],
                eth_difficulty)

        istanbul_difficulty = self._helper.deep_get(
            each_peer, 'protocols.istanbul.difficulty')
        if istanbul_difficulty:
            metric_peers_head_block.add_metric(
                [instance_name, enode,
                    enode_short, name, 'istanbul'],
                istanbul_difficulty)

        return enode

    def _set_metrics_for_expected_but_unconnected_peer(self, enode: str, instance_name: str,
            metric_peers: GaugeMetricFamily,
            metric_peers_network_direction: GaugeMetricFamily) -> str:
        enode_short = enode[0:20]
        name = self._config.peers[enode].name

        # 1. metric_peers
        # Set value (0) that enode is NOT found
        metric_peers.add_metric([instance_name, enode, enode_short, name], 0)

        # 2. metric_peers_network_direction
        # Set network not connected (0)
        metric_peers_network_direction.add_metric([instance_name, enode, enode_short, name], 0)

        # 3. metric_peers_head_block
        # WE DO NOT ADD THESE METRICS AS THEY DO NOT MAKE SENSE:
        # Providing a value of zero (0) may also be a correct value,
        # therefore we do not create head block metrics for non connected peers!

    def process(self):
        """Processes getting peers info and preparing metrics
        """
        # Get DNS name and use it as "pretty" instance name
        instance_name = self._helper.get_host_name(url=self._config.rpc_url)

        # Get data of all currently connected peers
        peers_data = self._get_peers_data()

        # Report metrics for this instance
        self._create_current_metrics(instance_name, peers_data)

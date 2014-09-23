# Copyright 2012 Nebula, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from django.core import urlresolvers
from django.utils.translation import ugettext_lazy as _

from horizon import exceptions
from horizon import tabs

from openstack_dashboard.api import base as api_base

from tuskar_ui import api
from tuskar_ui.infrastructure.nodes import tables
from tuskar_ui.utils import metering as metering_utils


class OverviewTab(tabs.Tab):
    name = _("Overview")
    slug = "overview"
    template_name = "infrastructure/nodes/_overview.html"

    def get_context_data(self, request):
        nodes = api.node.Node.list(request)
        cpus = sum(int(node.cpus) for node in nodes if node.cpus)
        memory_mb = sum(int(node.memory_mb) for node in nodes if
                        node.memory_mb)
        local_gb = sum(int(node.local_gb) for node in nodes if node.local_gb)
        deployed_nodes = api.node.Node.list(request, associated=True)
        free_nodes = api.node.Node.list(request, associated=False)
        deployed_nodes_error = api.node.filter_nodes(
            deployed_nodes, healthy=False)
        deployed_nodes_down = api.node.filter_nodes(
            deployed_nodes, power_state=False)
        free_nodes_error = api.node.filter_nodes(free_nodes, healthy=False)
        free_nodes_down = api.node.filter_nodes(free_nodes, power_state=False)
        total_nodes = deployed_nodes + free_nodes
        total_nodes_error = deployed_nodes_error + free_nodes_error
        total_nodes_down = deployed_nodes_down + free_nodes_down
        total_nodes_healthy = api.node.filter_nodes(total_nodes, healthy=True)
        total_nodes_up = api.node.filter_nodes(total_nodes, power_state=True)

        return {
            'cpus': cpus,
            'memory_gb': memory_mb / 1024.0,
            'local_gb': local_gb,
            'total_nodes_healthy': total_nodes_healthy,
            'total_nodes_up': total_nodes_up,
            'total_nodes_error': total_nodes_error,
            'total_nodes_down': total_nodes_down,
            'deployed_nodes': deployed_nodes,
            'deployed_nodes_error': deployed_nodes_error,
            'deployed_nodes_down': deployed_nodes_down,
            'free_nodes': free_nodes,
            'free_nodes_error': free_nodes_error,
            'free_nodes_down': free_nodes_down,
        }


class RegisteredTab(tabs.TableTab):
    table_classes = (tables.RegisteredNodesTable,)
    name = _("Registered")
    slug = "registered"
    template_name = "horizon/common/_detail_table.html"

    def __init__(self, tab_group, request):
        super(RegisteredTab, self).__init__(tab_group, request)

    def get_items_count(self):
        return len(self.get_nodes_table_data())

    def get_nodes_table_data(self):
        redirect = urlresolvers.reverse('horizon:infrastructure:nodes:index')
        nodes = api.node.Node.list(self.request, maintenance=False,
                                   _error_redirect=redirect)

        if 'errors' in self.request.GET:
            return api.node.filter_nodes(nodes, healthy=False)

        if nodes:
            all_resources = api.heat.Resource.list_all_resources(self.request)
            for node in nodes:
                try:
                    resource = api.heat.Resource.get_by_node(
                        self.request, node, all_resources=all_resources)
                    node.role_name = resource.role.name
                    node.role_id = resource.role.id
                    node.stack_id = resource.stack.id
                except exceptions.NotFound:
                    node.role_name = '-'

        return nodes


class MaintenanceTab(tabs.TableTab):
    table_classes = (tables.MaintenanceNodesTable,)
    name = _("Maintenance")
    slug = "maintenance"
    template_name = "horizon/common/_detail_table.html"

    def get_items_count(self):
        return len(self.get_maintenance_nodes_table_data())

    def get_maintenance_nodes_table_data(self):
        redirect = urlresolvers.reverse('horizon:infrastructure:nodes:index')
        nodes = api.node.Node.list(self.request, maintenance=True,
                                   _error_redirect=redirect)
        return nodes


class DetailOverviewTab(tabs.Tab):
    name = _("Overview")
    slug = "detail_overview"
    template_name = 'infrastructure/nodes/_detail_overview.html'

    def get_context_data(self, request):
        node = self.tab_group.kwargs['node']
        context = {'node': node}
        try:
            resource = api.heat.Resource.get_by_node(self.request, node)
            context['role'] = resource.role
            context['stack'] = resource.stack
        except exceptions.NotFound:
            pass
        if node.instance_uuid:
            if api_base.is_service_enabled(self.request, 'metering'):
                # Meter configuration in the following format:
                # (meter label, url part, barchart (True/False))
                context['meter_conf'] = (
                    (_('System Load'),
                     metering_utils.url_part('hardware.cpu.load.1min', False),
                     None),
                    (_('CPU Utilization'),
                     metering_utils.url_part('hardware.system_stats.cpu.util',
                                             True),
                     '100'),
                    (_('Swap Utilization'),
                     metering_utils.url_part('hardware.memory.swap.util',
                                             True),
                     '100'),
                    (_('Disk I/O '),
                     metering_utils.url_part('disk-io', False),
                     None),
                    (_('Network I/O '),
                     metering_utils.url_part('network-io', False),
                     None),
                )
        return context


class NodeTabs(tabs.TabGroup):
    slug = "nodes"
    tabs = (OverviewTab, RegisteredTab)
    sticky = True
    template_name = "horizon/common/_items_count_tab_group.html"

    def __init__(self, request, **kwargs):
        if api.node.NodeClient.ironic_enabled(request):
            self.tabs = self.tabs + (MaintenanceTab,)
        super(NodeTabs, self).__init__(request, **kwargs)


class NodeDetailTabs(tabs.TabGroup):
    slug = "node_details"
    tabs = (DetailOverviewTab,)

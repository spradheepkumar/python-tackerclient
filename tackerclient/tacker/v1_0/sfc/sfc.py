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
#
# @author: Tim Rozet, Red Hat

import abc
import six

from tackerclient.common import exceptions
from tackerclient.openstack.common.gettextutils import _
from tackerclient.tacker import v1_0 as tackerV10
from tackerclient.common import extension as ext

_SFC = 'sfc'


class CreateSFC(ext.ClientExtensionCreate):
    """Create a Service Function Chain"""
    resource = _SFC
    shell_command = 'sfc-create'
    versions = '1.0'

    def add_known_arguments(self, parser):
        parser.add_argument(
            '--name',
            help='Set a name for the chain')
        parser.add_argument(
            '--chain',
            required=True,
            help='list of VNF IDs to chain, in order: "vnf1,vnf2"')
        parser.add_argument(
            '--symmetrical',
            required=False,
            help='Should reverse traffic be allowed in chain.  Boolean.'
        )

    def args2body(self, parsed_args):
        args = {'attributes': {}}
        body = {self.resource: args}
        if parsed_args.chain:
            parsed_args.chain = parsed_args.chain.split(",")
            for index, vnf in enumerate(parsed_args.chain):
                tacker_client = self.get_client()
                tacker_client.format = parsed_args.request_format
                _id = tackerV10.find_resourceid_by_name_or_id(
                    tacker_client, 'vnf',
                    vnf)
                parsed_args.chain[index] = _id
        tackerV10.update_dict(parsed_args, body[self.resource],
                              ['tenant_id', 'name', 'chain', 'symmetrical'])
        return body


class ListSFC(ext.ClientExtensionList):
    """List all Service Function Chains"""
    resource = _SFC
    shell_command = 'sfc-list'
    versions = '1.0'
    list_columns = ['id', 'name', 'description', 'infra_driver', 'symmetrical', 'status']


class ShowSFC(ext.ClientExtensionShow):
    """Show a Service Function Chain"""
    resource = _SFC
    shell_command = 'sfc-show'
    versions = '1.0'


class DeleteSFC(ext.ClientExtensionDelete):
    """Delete a Service Function Chain"""
    resource = _SFC
    shell_command = 'sfc-delete'
    versions = '1.0'


class UpdateSFC(ext.ClientExtensionUpdate):
    """Update a Service Function Chain"""
    resource = _SFC
    shell_command = 'sfc-update'
    versions = '1.0'

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

_SFCClassifier = 'sfc_classifier'


class CreateSFCClassifier(ext.ClientExtensionCreate):
    """Create a Service Function Chain Classifier"""
    resource = _SFCClassifier
    shell_command = 'sfc-classifier-create'
    versions = '1.0'

    def add_known_arguments(self, parser):
        parser.add_argument(
            '--name',
            help='Set a name for the classifier')
        parser.add_argument(
            '--chain',
            required=True,
            help='name or id of the chain to apply the classifier to')
        parser.add_argument(
            '--match',
            required=True,
            help='Match criteria for tenant traffic to enter a chain.\
                  Proper format is key=value,key1=value.  Possible keys:\
                  source_ip_prefix, dest_ip_prefix, source_port, dest_port,\
                  source_mac, dest_mac, ethertype, protocol'

        )

    def args2body(self, parsed_args):
        args = {'attributes': {}}
        body = {self.resource: args}
        if parsed_args.match:
            parsed_args.match = dict(item.split("=") for item in parsed_args.match.split(","))
        tacker_client = self.get_client()
        tacker_client.format = parsed_args.request_format
        _chain_id = tackerV10.find_resourceid_by_name_or_id(
            tacker_client, 'sfc',
            parsed_args.chain)
        parsed_args.chain = _chain_id
        tackerV10.update_dict(parsed_args, body[self.resource],
                              ['tenant_id', 'name', 'chain', 'match'])
        return body


class ListSFCClassifier(ext.ClientExtensionList):
    """List all Service Function Chain Classifiers"""
    resource = _SFCClassifier
    shell_command = 'sfc-classifier-list'
    versions = '1.0'
    list_columns = ['id', 'name', 'description', 'acl_match_criteria', 'chain_id', 'status']


class ShowSFCClassifier(ext.ClientExtensionShow):
    """Show a Service Function Chain"""
    resource = _SFCClassifier
    shell_command = 'sfc-classifier-show'
    versions = '1.0'


class DeleteSFCClassifier(ext.ClientExtensionDelete):
    """Delete a Service Function Chain"""
    resource = _SFCClassifier
    shell_command = 'sfc-classifier-delete'
    versions = '1.0'


class UpdateSFCClassifier(ext.ClientExtensionUpdate):
    """Update a Service Function Chain"""
    resource = _SFCClassifier
    shell_command = 'sfc-classifier-update'
    versions = '1.0'

# Copyright 2012 OpenStack Foundation.
# All Rights Reserved
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
#

try:
    import json
except ImportError:
    import simplejson as json
import logging
import os

from keystoneclient import access
import requests

from tackerclient.common import exceptions
from tackerclient.common import utils
from tackerclient.openstack.common.gettextutils import _

_logger = logging.getLogger(__name__)

if os.environ.get('TACKERCLIENT_DEBUG'):
    ch = logging.StreamHandler()
    _logger.setLevel(logging.DEBUG)
    _logger.addHandler(ch)
    _requests_log_level = logging.DEBUG
else:
    _requests_log_level = logging.WARNING

logging.getLogger("requests").setLevel(_requests_log_level)


class HTTPClient(object):
    """Handles the REST calls and responses, include authn."""

    USER_AGENT = 'python-tackerclient'

    def __init__(self, username=None, user_id=None,
                 tenant_name=None, tenant_id=None,
                 password=None, auth_url=None,
                 token=None, region_name=None, timeout=None,
                 endpoint_url=None, insecure=False,
                 endpoint_type='publicURL',
                 auth_strategy='keystone', ca_cert=None, log_credentials=False,
                 service_type='servicevm',
                 **kwargs):

        self.username = username
        self.user_id = user_id
        self.tenant_name = tenant_name
        self.tenant_id = tenant_id
        self.password = password
        self.auth_url = auth_url.rstrip('/') if auth_url else None
        self.service_type = service_type
        self.endpoint_type = endpoint_type
        self.region_name = region_name
        self.timeout = timeout
        self.auth_token = token
        self.auth_tenant_id = None
        self.auth_user_id = None
        self.content_type = 'application/json'
        self.endpoint_url = endpoint_url
        self.auth_strategy = auth_strategy
        self.log_credentials = log_credentials
        if insecure:
            self.verify_cert = False
        else:
            self.verify_cert = ca_cert if ca_cert else True

    def _cs_request(self, *args, **kwargs):
        kargs = {}
        kargs.setdefault('headers', kwargs.get('headers', {}))
        kargs['headers']['User-Agent'] = self.USER_AGENT

        if 'content_type' in kwargs:
            kargs['headers']['Content-Type'] = kwargs['content_type']
            kargs['headers']['Accept'] = kwargs['content_type']
        else:
            kargs['headers']['Content-Type'] = self.content_type
            kargs['headers']['Accept'] = self.content_type

        if 'body' in kwargs:
            kargs['body'] = kwargs['body']
        args = utils.safe_encode_list(args)
        kargs = utils.safe_encode_dict(kargs)

        if self.log_credentials:
            log_kargs = kargs
        else:
            log_kargs = self._strip_credentials(kargs)

        utils.http_log_req(_logger, args, log_kargs)
        try:
            resp, body = self.request(*args, **kargs)
        except requests.exceptions.SSLError as e:
            raise exceptions.SslCertificateValidationError(reason=e)
        except Exception as e:
            # Wrap the low-level connection error (socket timeout, redirect
            # limit, decompression error, etc) into our custom high-level
            # connection exception (it is excepted in the upper layers of code)
            _logger.debug("throwing ConnectionFailed : %s", e)
            raise exceptions.ConnectionFailed(reason=e)
        utils.http_log_resp(_logger, resp, body)
        status_code = self.get_status_code(resp)
        if status_code == 401:
            raise exceptions.Unauthorized(message=body)
        return resp, body

    def _strip_credentials(self, kwargs):
        if kwargs.get('body') and self.password:
            log_kwargs = kwargs.copy()
            log_kwargs['body'] = kwargs['body'].replace(self.password,
                                                        'REDACTED')
            return log_kwargs
        else:
            return kwargs

    def authenticate_and_fetch_endpoint_url(self):
        if not self.auth_token:
            self.authenticate()
        elif not self.endpoint_url:
            self.endpoint_url = self._get_endpoint_url()

    def request(self, url, method, **kwargs):
        kwargs.setdefault('headers', kwargs.get('headers', {}))
        kwargs['headers']['User-Agent'] = self.USER_AGENT
        kwargs['headers']['Accept'] = 'application/json'
        if 'body' in kwargs:
            kwargs['headers']['Content-Type'] = 'application/json'
            kwargs['data'] = kwargs['body']
            del kwargs['body']
        resp = requests.request(
            method,
            url,
            verify=self.verify_cert,
            **kwargs)

        return resp, resp.text

    def do_request(self, url, method, **kwargs):
        self.authenticate_and_fetch_endpoint_url()
        # Perform the request once. If we get a 401 back then it
        # might be because the auth token expired, so try to
        # re-authenticate and try again. If it still fails, bail.
        try:
            kwargs.setdefault('headers', {})
            if self.auth_token is None:
                self.auth_token = ""
            kwargs['headers']['X-Auth-Token'] = self.auth_token
            resp, body = self._cs_request(self.endpoint_url + url, method,
                                          **kwargs)
            return resp, body
        except exceptions.Unauthorized:
            self.authenticate()
            kwargs.setdefault('headers', {})
            kwargs['headers']['X-Auth-Token'] = self.auth_token
            resp, body = self._cs_request(
                self.endpoint_url + url, method, **kwargs)
            return resp, body

    def _extract_service_catalog(self, body):
        """Set the client's service catalog from the response data."""
        self.auth_ref = access.AccessInfo.factory(body=body)
        self.service_catalog = self.auth_ref.service_catalog
        self.auth_token = self.auth_ref.auth_token
        self.auth_tenant_id = self.auth_ref.tenant_id
        self.auth_user_id = self.auth_ref.user_id

        if not self.endpoint_url:
            self.endpoint_url = self.service_catalog.url_for(
                attr='region', filter_value=self.region_name,
                service_type=self.service_type,
                endpoint_type=self.endpoint_type)

    def _authenticate_keystone(self):
        if self.user_id:
            creds = {'userId': self.user_id,
                     'password': self.password}
        else:
            creds = {'username': self.username,
                     'password': self.password}

        if self.tenant_id:
            body = {'auth': {'passwordCredentials': creds,
                             'tenantId': self.tenant_id, }, }
        else:
            body = {'auth': {'passwordCredentials': creds,
                             'tenantName': self.tenant_name, }, }

        if self.auth_url is None:
            raise exceptions.NoAuthURLProvided()

        token_url = self.auth_url + "/tokens"
        resp, resp_body = self._cs_request(token_url, "POST",
                                           body=json.dumps(body),
                                           content_type="application/json",
                                           allow_redirects=True)
        status_code = self.get_status_code(resp)
        if status_code != 200:
            raise exceptions.Unauthorized(message=resp_body)
        if resp_body:
            try:
                resp_body = json.loads(resp_body)
            except ValueError:
                pass
        else:
            resp_body = None
        self._extract_service_catalog(resp_body)

    def _authenticate_noauth(self):
        if not self.endpoint_url:
            message = _('For "noauth" authentication strategy, the endpoint '
                        'must be specified either in the constructor or '
                        'using --os-url')
            raise exceptions.Unauthorized(message=message)

    def authenticate(self):
        if self.auth_strategy == 'keystone':
            self._authenticate_keystone()
        elif self.auth_strategy == 'noauth':
            self._authenticate_noauth()
        else:
            err_msg = _('Unknown auth strategy: %s') % self.auth_strategy
            raise exceptions.Unauthorized(message=err_msg)

    def _get_endpoint_url(self):
        if self.auth_url is None:
            raise exceptions.NoAuthURLProvided()

        url = self.auth_url + '/tokens/%s/endpoints' % self.auth_token
        try:
            resp, body = self._cs_request(url, "GET")
        except exceptions.Unauthorized:
            # rollback to authenticate() to handle case when tacker client
            # is initialized just before the token is expired
            self.authenticate()
            return self.endpoint_url

        body = json.loads(body)
        for endpoint in body.get('endpoints', []):
            if (endpoint['type'] == 'servicevm' and
                endpoint.get('region') == self.region_name):
                if self.endpoint_type not in endpoint:
                    raise exceptions.EndpointTypeNotFound(
                        type_=self.endpoint_type)
                return endpoint[self.endpoint_type]

        raise exceptions.EndpointNotFound()

    def get_auth_info(self):
        return {'auth_token': self.auth_token,
                'auth_tenant_id': self.auth_tenant_id,
                'auth_user_id': self.auth_user_id,
                'endpoint_url': self.endpoint_url}

    def get_status_code(self, response):
        """Returns the integer status code from the response.

        Either a Webob.Response (used in testing) or requests.Response
        is returned.
        """
        if hasattr(response, 'status_int'):
            return response.status_int
        else:
            return response.status_code
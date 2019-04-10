# Copyright 2013 OpenStack Foundation
# All Rights Reserved.
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

from neutron_lib import constants
from tempest.lib.common.utils import data_utils
from tempest.lib import decorators
from tempest.lib import exceptions
import testtools

from neutron_tempest_plugin.api import base
from neutron_tempest_plugin.api import base_security_groups


class SecGroupTest(base.BaseNetworkTest):

    required_extensions = ['security-group']

    @decorators.idempotent_id('bfd128e5-3c92-44b6-9d66-7fe29d22c802')
    def test_create_list_update_show_delete_security_group(self):
        security_group = self.create_security_group()

        # List security groups and verify if created group is there in response
        security_groups = self.client.list_security_groups()['security_groups']
        self.assertIn(security_group['id'],
                      {sg['id'] for sg in security_groups})

        # Update the security group
        new_name = data_utils.rand_name('security')
        new_description = data_utils.rand_name('security-description')
        updated_security_group = self.client.update_security_group(
            security_group['id'], name=new_name,
            description=new_description)['security_group']

        # Verify if security group is updated
        self.assertEqual(updated_security_group['name'], new_name)
        self.assertEqual(updated_security_group['description'],
                         new_description)

        # Show details of the updated security group
        observed_security_group = self.client.show_security_group(
            security_group['id'])['security_group']
        self.assertEqual(observed_security_group['name'], new_name)
        self.assertEqual(observed_security_group['description'],
                         new_description)

    @decorators.idempotent_id('7c0ecb10-b2db-11e6-9b14-000c29248b0d')
    def test_create_bulk_sec_groups(self):
        # Creates 2 sec-groups in one request
        sec_nm = [data_utils.rand_name('secgroup'),
                  data_utils.rand_name('secgroup')]
        body = self.client.create_bulk_security_groups(sec_nm)
        created_sec_grps = body['security_groups']
        self.assertEqual(2, len(created_sec_grps))
        for secgrp in created_sec_grps:
            self.addCleanup(self.client.delete_security_group,
                            secgrp['id'])
            self.assertIn(secgrp['name'], sec_nm)
            self.assertIsNotNone(secgrp['id'])


class SecGroupProtocolTest(base.BaseNetworkTest):

    protocol_names = base_security_groups.V4_PROTOCOL_NAMES
    protocol_ints = base_security_groups.V4_PROTOCOL_INTS

    @decorators.idempotent_id('282e3681-aa6e-42a7-b05c-c341aa1e3cdf')
    def test_security_group_rule_protocol_names(self):
        self._test_security_group_rule_protocols(protocols=self.protocol_names)

    @decorators.idempotent_id('66e47f1f-20b6-4417-8839-3cc671c7afa3')
    def test_security_group_rule_protocol_ints(self):
        self._test_security_group_rule_protocols(protocols=self.protocol_ints)

    def _test_security_group_rule_protocols(self, protocols):
        security_group = self.create_security_group()
        for protocol in protocols:
            self._test_security_group_rule(
                security_group=security_group,
                protocol=str(protocol),
                direction=constants.INGRESS_DIRECTION,
                ethertype=self.ethertype)

    def _test_security_group_rule(self, security_group, **kwargs):
        security_group_rule = self.create_security_group_rule(
            security_group=security_group, **kwargs)
        observed_security_group_rule = self.client.show_security_group_rule(
            security_group_rule['id'])['security_group_rule']
        for key, value in kwargs.items():
            self.assertEqual(value, security_group_rule[key],
                             "{!r} does not match.".format(key))
            self.assertEqual(value, observed_security_group_rule[key],
                             "{!r} does not match.".format(key))


class SecGroupProtocolIPv6Test(SecGroupProtocolTest):

    _ip_version = constants.IP_VERSION_6
    protocol_names = base_security_groups.V6_PROTOCOL_NAMES
    protocol_ints = base_security_groups.V6_PROTOCOL_INTS
    protocol_legacy_names = base_security_groups.V6_PROTOCOL_LEGACY

    @decorators.idempotent_id('c7d17b41-3b4e-4add-bb3b-6af59baaaffa')
    def test_security_group_rule_protocol_legacy_names(self):
        self._test_security_group_rule_protocols(
            protocols=self.protocol_legacy_names)


class RbacSharedSecurityGroupTest(base.BaseAdminNetworkTest):

    force_tenant_isolation = True
    credentials = ['primary', 'alt', 'admin']
    required_extensions = ['security-group', 'rbac-security-groups']

    @classmethod
    def resource_setup(cls):
        super(RbacSharedSecurityGroupTest, cls).resource_setup()
        cls.client2 = cls.os_alt.network_client

    def _create_security_group(self):
        return self.create_security_group(
            name=data_utils.rand_name('test-sg'),
            project={'id': self.admin_client.tenant_id})

    def _make_admin_sg_shared_to_tenant_id(self, tenant_id):
        sg = self._create_security_group()
        rbac_policy = self.admin_client.create_rbac_policy(
            object_type='security_group',
            object_id=sg['id'],
            action='access_as_shared',
            target_tenant=tenant_id,
        )['rbac_policy']
        return {'security_group': sg, 'rbac_policy': rbac_policy}

    @decorators.idempotent_id('2a41eb8f-2a35-11e9-bae9-acde48001122')
    def test_policy_target_update(self):
        res = self._make_admin_sg_shared_to_tenant_id(
            self.client.tenant_id)
        # change to client2
        update_res = self.admin_client.update_rbac_policy(
                res['rbac_policy']['id'], target_tenant=self.client2.tenant_id)
        self.assertEqual(self.client2.tenant_id,
                         update_res['rbac_policy']['target_tenant'])
        # make sure everything else stayed the same
        res['rbac_policy'].pop('target_tenant')
        update_res['rbac_policy'].pop('target_tenant')
        self.assertEqual(res['rbac_policy'], update_res['rbac_policy'])

    @decorators.idempotent_id('2a619a8a-2a35-11e9-90d9-acde48001122')
    def test_port_presence_prevents_policy_rbac_policy_deletion(self):
        res = self._make_admin_sg_shared_to_tenant_id(
            self.client2.tenant_id)
        sg_id = res['security_group']['id']
        net = self.create_network(client=self.client2)
        port = self.client2.create_port(
            network_id=net['id'],
            security_groups=[sg_id])['port']

        # a port with shared sg should prevent the deletion of an
        # rbac-policy required for it to be shared
        with testtools.ExpectedException(exceptions.Conflict):
            self.admin_client.delete_rbac_policy(res['rbac_policy']['id'])

        # cleanup
        self.client2.delete_port(port['id'])
        self.admin_client.delete_rbac_policy(res['rbac_policy']['id'])

    @decorators.idempotent_id('2a81795c-2a35-11e9-9d86-acde48001122')
    def test_regular_client_shares_to_another_regular_client(self):
        # owned by self.admin_client
        sg = self._create_security_group()
        with testtools.ExpectedException(exceptions.NotFound):
            self.client.show_security_group(sg['id'])
        rbac_policy = self.admin_client.create_rbac_policy(
            object_type='security_group', object_id=sg['id'],
            action='access_as_shared',
            target_tenant=self.client.tenant_id)['rbac_policy']
        self.client.show_security_group(sg['id'])

        self.assertIn(rbac_policy,
                      self.admin_client.list_rbac_policies()['rbac_policies'])
        # ensure that 'client2' can't see the rbac-policy sharing the
        # sg to it because the rbac-policy belongs to 'client'
        self.assertNotIn(rbac_policy['id'], [p['id'] for p in
                          self.client2.list_rbac_policies()['rbac_policies']])

    @decorators.idempotent_id('2a9fd480-2a35-11e9-9cb6-acde48001122')
    def test_filter_fields(self):
        sg = self._create_security_group()
        self.admin_client.create_rbac_policy(
            object_type='security_group', object_id=sg['id'],
            action='access_as_shared', target_tenant=self.client2.tenant_id)
        field_args = (('id',), ('id', 'action'), ('object_type', 'object_id'),
                      ('tenant_id', 'target_tenant'))
        for fields in field_args:
            res = self.admin_client.list_rbac_policies(fields=fields)
            self.assertEqual(set(fields), set(res['rbac_policies'][0].keys()))

    @decorators.idempotent_id('2abf8f9e-2a35-11e9-85f7-acde48001122')
    def test_rbac_policy_show(self):
        res = self._make_admin_sg_shared_to_tenant_id(
            self.client.tenant_id)
        p1 = res['rbac_policy']
        p2 = self.admin_client.create_rbac_policy(
            object_type='security_group',
            object_id=res['security_group']['id'],
            action='access_as_shared',
            target_tenant='*')['rbac_policy']

        self.assertEqual(
            p1, self.admin_client.show_rbac_policy(p1['id'])['rbac_policy'])
        self.assertEqual(
            p2, self.admin_client.show_rbac_policy(p2['id'])['rbac_policy'])

    @decorators.idempotent_id('2adf6bd7-2a35-11e9-9c62-acde48001122')
    def test_filter_rbac_policies(self):
        sg = self._create_security_group()
        rbac_pol1 = self.admin_client.create_rbac_policy(
            object_type='security_group', object_id=sg['id'],
            action='access_as_shared',
            target_tenant=self.client2.tenant_id)['rbac_policy']
        rbac_pol2 = self.admin_client.create_rbac_policy(
            object_type='security_group', object_id=sg['id'],
            action='access_as_shared',
            target_tenant=self.admin_client.tenant_id)['rbac_policy']
        res1 = self.admin_client.list_rbac_policies(id=rbac_pol1['id'])[
            'rbac_policies']
        res2 = self.admin_client.list_rbac_policies(id=rbac_pol2['id'])[
            'rbac_policies']
        self.assertEqual(1, len(res1))
        self.assertEqual(1, len(res2))
        self.assertEqual(rbac_pol1['id'], res1[0]['id'])
        self.assertEqual(rbac_pol2['id'], res2[0]['id'])

    @decorators.idempotent_id('2aff3900-2a35-11e9-96b3-acde48001122')
    def test_regular_client_blocked_from_sharing_anothers_policy(self):
        sg = self._make_admin_sg_shared_to_tenant_id(
            self.client.tenant_id)['security_group']
        with testtools.ExpectedException(exceptions.BadRequest):
            self.client.create_rbac_policy(
                object_type='security_group', object_id=sg['id'],
                action='access_as_shared',
                target_tenant=self.client2.tenant_id)

        # make sure the rbac-policy is invisible to the tenant for which it's
        # being shared
        self.assertFalse(self.client.list_rbac_policies()['rbac_policies'])

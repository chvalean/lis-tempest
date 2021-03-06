# Copyright 2016 Cloudbase Solutions Srl
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

import os
from tempest import config
from tempest.lib import exceptions as lib_exc
from tempest.common.utils.windows.remote_client import WinRemoteClient
from tempest import test
from tempest.lis import manager
from oslo_log import log as logging
from tempest.scenario import utils as test_utils

CONF = config.CONF

LOG = logging.getLogger(__name__)


class nmi(manager.LisBase):

    def setUp(self):
        super(nmi, self).setUp()
        # Setup image and flavor the test instance
        # Support both configured and injected values
        if not hasattr(self, 'image_ref'):
            self.image_ref = CONF.compute.image_ref
        if not hasattr(self, 'flavor_ref'):
            self.flavor_ref = CONF.compute.flavor_ref
        self.image_utils = test_utils.ImageUtils(self.manager)
        if not self.image_utils.is_flavor_enough(self.flavor_ref,
                                                 self.image_ref):
            raise self.skipException(
                '{image} does not fit in {flavor}'.format(
                    image=self.image_ref, flavor=self.flavor_ref
                )
            )
        self.host_name = ""
        self.instance_name = ""
        self.run_ssh = CONF.validation.run_validation and \
            self.image_utils.is_sshable_image(self.image_ref)
        self.ssh_user = CONF.validation.image_ssh_user
        LOG.debug('Starting test for i:{image}, f:{flavor}. '
                  'Run ssh: {ssh}, user: {ssh_user}'.format(
                      image=self.image_ref, flavor=self.flavor_ref,
                      ssh=self.run_ssh, ssh_user=self.ssh_user))

    def _initiate_wsman(self, host_name):
        try:
            self.wsmancmd = WinRemoteClient(
                host_name, self.host_username, self.host_password)

        except Exception as exc:
            LOG.exception(exc)
            raise exc

    def check_nmi_interrupt(self):
        try:
            script_name = 'nmi_verify_interrupt.sh'
            script_path = '/scripts/' + script_name
            destination = '/tmp/'
            my_path = os.path.abspath(
                os.path.normpath(os.path.dirname(__file__)))
            full_script_path = my_path + script_path
            cmd_params = []
            self.linux_client.execute_script(
                script_name, cmd_params, full_script_path, destination)

        except lib_exc.SSHExecCommandFailed as exc:

            LOG.exception(exc)
            self._log_console_output()
            raise exc

        except Exception as exc:
            LOG.exception(exc)
            self._log_console_output()
            raise exc

    @test.attr(type=['smoke', 'nmi'])
    @test.services('compute')
    def test_lis_nmi_interrupt(self):
        self.spawn_vm()
        self._initiate_linux_client(self.floating_ip['floatingip']['floating_ip_address'],
                                    self.ssh_user, self.keypair['private_key'])
        self.send_nmi_interrupt(self.instance_name)
        self.check_nmi_interrupt()
        self.servers_client.delete_server(self.instance['id'])

    @test.attr(type=['smoke', 'nmi'])
    @test.services('compute')
    def test_lis_nmi_interrupt_change_status(self):
        self.spawn_vm()
        self.stop_vm(self.server_id)
        self.send_nmi_interrupt_change_status(self.instance_name)
        self.start_vm(self.server_id)
        self._initiate_linux_client(self.floating_ip['floatingip']['floating_ip_address'],
                                    self.ssh_user, self.keypair['private_key'])
        self.save_vm(self.server_id)
	self.send_nmi_interrupt_change_status(self.instance_name)
	self.unsave_vm(self.server_id)
        self._initiate_linux_client(self.floating_ip['floatingip']['floating_ip_address'],
                                    self.ssh_user, self.keypair['private_key'])
        self.pause_vm(self.server_id)
	self.send_nmi_interrupt_change_status(self.instance_name)
	self.unpause_vm(self.server_id)
        self._initiate_linux_client(self.floating_ip['floatingip']['floating_ip_address'],
                                    self.ssh_user, self.keypair['private_key'])
        self.servers_client.delete_server(self.instance['id'])

    @test.attr(type=['smoke', 'nmi'])
    @test.services('compute')
    def test_lis_nmi_unprivileged(self):
        self.spawn_vm()
        self._initiate_linux_client(self.floating_ip['floatingip']['floating_ip_address'],
                                    self.ssh_user, self.keypair['private_key'])
        self.send_nmi_unprivileged(self.instance_name)
        self.servers_client.delete_server(self.instance['id'])

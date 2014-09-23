# Copyright 2014 Cloudbase Solutions Srl
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
from tempest.openstack.common import log as logging
from tempest.common.utils.windows.remote_client import WinRemoteClient
from tempest.lis import manager
from tempest.scenario import utils as test_utils
from tempest import test

CONF = config.CONF

LOG = logging.getLogger(__name__)

load_tests = test_utils.load_tests_input_scenario_utils


class TestLis(manager.ScenarioTest):

    """
    This smoke test case follows this basic set of operations:

     * Create a keypair for use in launching an instance
     * Create a security group to control network access in instance
     * Add simple permissive rules to the security group
     * Launch an instance
     * Pause/unpause the instance
     * Suspend/resume the instance
     * Terminate the instance
    """

    def setUp(self):
        super(TestLis, self).setUp()
        # Setup image and flavor the test instance
        # Support both configured and injected values
        if not hasattr(self, 'image_ref'):
            self.image_ref = CONF.compute.image_ref
        if not hasattr(self, 'flavor_ref'):
            self.flavor_ref = CONF.compute.flavor_ref
        self.image_utils = test_utils.ImageUtils()
        if not self.image_utils.is_flavor_enough(self.flavor_ref,
                                                 self.image_ref):
            raise self.skipException(
                '{image} does not fit in {flavor}'.format(
                    image=self.image_ref, flavor=self.flavor_ref
                )
            )
        self.host_name = ""
        self.instance_name = ""
        self.run_ssh = CONF.compute.run_ssh and \
            self.image_utils.is_sshable_image(self.image_ref)
        self.ssh_user = self.image_utils.ssh_user(self.image_ref)

        self.host_username = CONF.host_credentials.host_user_name
        self.host_password = CONF.host_credentials.host_password
        self.scriptfolder = CONF.host_credentials.host_setupscripts_folder
        LOG.debug('Starting test for i:{image}, f:{flavor}. '
                  'Run ssh: {ssh}, user: {ssh_user}'.format(
                      image=self.image_ref, flavor=self.flavor_ref,
                      ssh=self.run_ssh, ssh_user=self.ssh_user))

    def add_keypair(self):
        self.keypair = self.create_keypair()

    def boot_instance(self):
        # Create server with image and flavor from input scenario
        security_groups = [self.security_group]
        create_kwargs = {
            'key_name': self.keypair['name'],
            'security_groups': security_groups
        }
        self.instance = self.create_server(image=self.image_ref,
                                           flavor=self.flavor_ref,
                                           create_kwargs=create_kwargs)
        self.instance_name = self.instance["OS-EXT-SRV-ATTR:instance_name"]
        self.host_name = self.instance["OS-EXT-SRV-ATTR:hypervisor_hostname"]
        self._initiate_wsman(self.host_name)

    def _initiate_wsman(self, host_name):
        try:
            self.wsmancmd = WinRemoteClient(
                host_name, self.host_username, self.host_password)

        except Exception as exc:
            LOG.exception(exc)
            raise exc

    def nova_floating_ip_create(self):
        _, self.floating_ip = self.floating_ips_client.create_floating_ip()
        self.addCleanup(self.delete_wrapper,
                        self.floating_ips_client.delete_floating_ip,
                        self.floating_ip['id'])

    def nova_floating_ip_add(self):
        self.floating_ips_client.associate_floating_ip_to_server(
            self.floating_ip['ip'], self.instance['id'])

    def add_disk(self, disk_type, controller_type, controller_id, lun, vhd_type, sector_size):
        """Attachk Disk to VM"""
        cmd = 'powershell ' + self.scriptfolder
        cmd += 'setupscripts\\attach-disk.ps1 -vmName ' + self.instance_name
        cmd += ' -hvServer ' + self.host_name
        cmd += ' -diskType ' + disk_type
        cmd += ' -controllerType ' + controller_type
        cmd += ' -controllerID ' + str(controller_id)
        cmd += ' -Lun ' + str(lun)
        cmd += ' -vhdType ' + vhd_type
        cmd += ' -sectorSize ' + str(sector_size)

        LOG.debug('Sending command %s', cmd)
        try:
            std_out, std_err, exit_code = self.wsmancmd.run_wsman_cmd(cmd)

        except Exception as exc:
            LOG.exception(exc)
            raise exc

        LOG.info('Add disk:\nstd_out: %s', std_out)
        LOG.debug('Command std_err: %s', std_err)
        self.assertFalse(exit_code != 0)

    def format_disk(self, expected_disk_count):
        try:
            linux_client = self.get_remote_client(
                server_or_ip=self.floating_ip['ip'],
                username=self.image_utils.ssh_user(self.image_ref),
                private_key=self.keypair['private_key'])
            script='STOR_Lis_Disk.sh'
            MY_PATH = os.path.abspath(os.path.normpath(os.path.dirname(__file__)))
            copy_file = linux_client.copy_over(MY_PATH + '/scripts/' + script, '/root/')

            output = linux_client.ssh_client.exec_command('cd /root/; dos2unix ' + script)
            output = linux_client.ssh_client.exec_command('chmod +x ' + script )
            output = linux_client.ssh_client.exec_command('./' + script + ' 1 ext3')

        except Exception:
            LOG.exception('Error while formatting disk %s', output)
            self._log_console_output()
            raise

    @test.services('compute', 'network')
    def test_storage_vhd_fixed_ide(self):
        self.add_keypair()
        self.security_group = self._create_security_group()
        self.boot_instance()
        self.nova_floating_ip_create()
        self.nova_floating_ip_add()
        server_id = self.instance['id']
        self.servers_client.stop(server_id)
        self.servers_client.wait_for_server_status(server_id, 'SHUTOFF')
        self.add_disk('vhd', "IDE", 1, 1, "Fixed", 512)
        self.servers_client.start(server_id)
        self.servers_client.wait_for_server_status(server_id, 'ACTIVE')
        self.format_disk(1)
        self.servers_client.delete_server(self.instance['id'])

    @test.services('compute', 'network')
    def test_storage_vhd_fixed_scsi(self):
        self.add_keypair()
        self.security_group = self._create_security_group()
        self.boot_instance()
        self.nova_floating_ip_create()
        self.nova_floating_ip_add()
        server_id = self.instance['id']
        self.servers_client.stop(server_id)
        self.servers_client.wait_for_server_status(server_id, 'SHUTOFF')
        self.add_disk('vhd', 'SCSI', 0, 1, 'Fixed', 512)
        self.servers_client.start(server_id)
        self.servers_client.wait_for_server_status(server_id, 'ACTIVE')
        self.format_disk(1)
        self.servers_client.delete_server(self.instance['id'])

    @test.services('compute', 'network')
    def test_storage_vhdx_fixed_ide(self):
        self.add_keypair()
        self.security_group = self._create_security_group()
        self.boot_instance()
        self.nova_floating_ip_create()
        self.nova_floating_ip_add()
        server_id = self.instance['id']
        self.servers_client.stop(server_id)
        self.servers_client.wait_for_server_status(server_id, 'SHUTOFF')
        self.add_disk('vhdx', 'IDE', 1, 1, 'Fixed', 512)
        self.servers_client.start(server_id)
        self.servers_client.wait_for_server_status(server_id, 'ACTIVE')
        self.format_disk(1)
        self.servers_client.delete_server(self.instance['id'])

    @test.services('compute', 'network')
    def test_storage_vhdx_fixed_scsi(self):
        self.add_keypair()
        self.security_group = self._create_security_group()
        self.boot_instance()
        self.nova_floating_ip_create()
        self.nova_floating_ip_add()
        server_id = self.instance['id']
        self.servers_client.stop(server_id)
        self.servers_client.wait_for_server_status(server_id, 'SHUTOFF')
        self.add_disk('vhdx', 'SCSI', 0, 1, 'Fixed', 512)
        self.servers_client.start(server_id)
        self.servers_client.wait_for_server_status(server_id, 'ACTIVE')
        self.format_disk(1)
        self.servers_client.delete_server(self.instance['id'])
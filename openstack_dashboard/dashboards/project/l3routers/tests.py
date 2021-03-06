# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012,  Nachi Ueno,  NTT MCL,  Inc.
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
from django.core.urlresolvers import reverse  # noqa
from django import http
from mox import IsA  # noqa

from openstack_dashboard import api
from openstack_dashboard.test import helpers as test


class RouterTests(test.TestCase):
    DASHBOARD = 'project'
    INDEX_URL = reverse('horizon:%s:l3routers:index' % DASHBOARD)
    DETAIL_PATH = 'horizon:%s:l3routers:detail' % DASHBOARD

    def _mock_external_network_list(self):
        search_opts = {'router:external': True}
        ext_nets = [n for n in self.networks.list() if n['router:external']]
        api.neutron.network_list(
            IsA(http.HttpRequest),
            **search_opts).AndReturn(ext_nets)

    def _mock_external_network_get(self, router):
        ext_net_id = router.external_gateway_info['network_id']
        ext_net = self.networks.list()[2]
        api.neutron.network_get(IsA(http.HttpRequest), ext_net_id,
                                expand_subnet=False).AndReturn(ext_net)

    @test.create_stubs({api.neutron: ('router_list', 'network_list')})
    def test_index(self):
        api.neutron.router_list(
            IsA(http.HttpRequest),
            tenant_id=self.tenant.id,
            search_opts=None).AndReturn(self.routers.list())
        self._mock_external_network_list()
        self.mox.ReplayAll()

        res = self.client.get(self.INDEX_URL)

        self.assertTemplateUsed(res, '%s/l3routers/index.html' % self.DASHBOARD)
        routers = res.context['table'].data
        self.assertItemsEqual(routers, self.routers.list())

    @test.create_stubs({api.neutron: ('router_list', 'network_list')})
    def test_index_router_list_exception(self):
        api.neutron.router_list(
            IsA(http.HttpRequest),
            tenant_id=self.tenant.id,
            search_opts=None).AndRaise(self.exceptions.neutron)
        self._mock_external_network_list()
        self.mox.ReplayAll()

        res = self.client.get(self.INDEX_URL)

        self.assertTemplateUsed(res, '%s/l3routers/index.html' % self.DASHBOARD)
        self.assertEqual(len(res.context['table'].data), 0)
        self.assertMessageCount(res, error=1)

    @test.create_stubs({api.neutron: ('router_get', 'port_list',
                                      'network_get')})
    def test_router_detail(self):
        router = self.routers.first()
        api.neutron.router_get(IsA(http.HttpRequest), router.id)\
            .AndReturn(self.routers.first())
        api.neutron.port_list(IsA(http.HttpRequest),
                              device_id=router.id)\
            .AndReturn([self.ports.first()])
        self._mock_external_network_get(router)
        self.mox.ReplayAll()

        res = self.client.get(reverse('horizon:%s'
                                      ':l3routers:detail' % self.DASHBOARD,
                                      args=[router.id]))

        self.assertTemplateUsed(res, '%s/l3routers/detail.html' % self.DASHBOARD)
        ports = res.context['interfaces_table'].data
        self.assertItemsEqual(ports, [self.ports.first()])

    @test.create_stubs({api.neutron: ('router_get', 'port_list')})
    def test_router_detail_exception(self):
        router = self.routers.first()
        api.neutron.router_get(IsA(http.HttpRequest), router.id)\
            .AndRaise(self.exceptions.neutron)
        api.neutron.port_list(IsA(http.HttpRequest),
                              device_id=router.id)\
            .AndReturn([self.ports.first()])
        self.mox.ReplayAll()

        res = self.client.get(reverse('horizon:%s'
                                      ':l3routers:detail' % self.DASHBOARD,
                                      args=[router.id]))
        self.assertRedirectsNoFollow(res, self.INDEX_URL)


class RouterActionTests(test.TestCase):
    DASHBOARD = 'project'
    INDEX_URL = reverse('horizon:%s:l3routers:index' % DASHBOARD)
    DETAIL_PATH = 'horizon:%s:l3routers:detail' % DASHBOARD

    @test.create_stubs({api.neutron: ('router_create',)})
    def test_router_create_post(self):
        router = self.routers.first()
        api.neutron.router_create(IsA(http.HttpRequest), name=router.name)\
            .AndReturn(router)
        self.mox.ReplayAll()

        form_data = {'name': router.name}
        url = reverse('horizon:%s:l3routers:create' % self.DASHBOARD)
        res = self.client.post(url, form_data)

        self.assertNoFormErrors(res)
        self.assertRedirectsNoFollow(res, self.INDEX_URL)

    @test.create_stubs({api.neutron: ('router_create',)})
    def test_router_create_post_exception(self):
        router = self.routers.first()
        api.neutron.router_create(IsA(http.HttpRequest), name=router.name)\
            .AndRaise(self.exceptions.neutron)
        self.mox.ReplayAll()

        form_data = {'name': router.name}
        url = reverse('horizon:%s:l3routers:create' % self.DASHBOARD)
        res = self.client.post(url, form_data)

        self.assertNoFormErrors(res)
        self.assertRedirectsNoFollow(res, self.INDEX_URL)

    def _mock_network_list(self, tenant_id):
        api.neutron.network_list(
            IsA(http.HttpRequest),
            shared=False,
            tenant_id=tenant_id).AndReturn(self.networks.list())
        api.neutron.network_list(
            IsA(http.HttpRequest),
            shared=True).AndReturn([])

    def _test_router_addinterface(self, raise_error=False):
        router = self.routers.first()
        subnet = self.subnets.first()
        port = self.ports.first()

        add_interface = api.neutron.router_add_interface(
            IsA(http.HttpRequest), router.id, subnet_id=subnet.id)
        if raise_error:
            add_interface.AndRaise(self.exceptions.neutron)
        else:
            add_interface.AndReturn({'subnet_id': subnet.id,
                                     'port_id': port.id})
            api.neutron.port_get(IsA(http.HttpRequest), port.id)\
                .AndReturn(port)
        self._check_router_addinterface(router, subnet)

    def _check_router_addinterface(self, router, subnet, ip_address=''):
        # mock APIs used to show router detail
        api.neutron.router_get(IsA(http.HttpRequest), router.id)\
            .AndReturn(router)
        self._mock_network_list(router['tenant_id'])
        self.mox.ReplayAll()

        form_data = {'router_id': router.id,
                     'router_name': router.name,
                     'subnet_id': subnet.id,
                     'ip_address': ip_address}

        url = reverse('horizon:%s:routers:addinterface' % self.DASHBOARD,
                      args=[router.id])
        res = self.client.post(url, form_data)
        self.assertNoFormErrors(res)
        detail_url = reverse(self.DETAIL_PATH, args=[router.id])
        self.assertRedirectsNoFollow(res, detail_url)

    @test.create_stubs({api.neutron: ('router_get',
                                      'router_add_interface',
                                      'port_get',
                                      'network_list')})
    def test_router_addinterface(self):
        self._test_router_addinterface()

    @test.create_stubs({api.neutron: ('router_get',
                                      'router_add_interface',
                                      'network_list')})
    def test_router_addinterface_exception(self):
        self._test_router_addinterface(raise_error=True)

    def _test_router_addinterface_ip_addr(self, errors=[]):
        router = self.routers.first()
        subnet = self.subnets.first()
        port = self.ports.first()
        ip_addr = port['fixed_ips'][0]['ip_address']
        self._setup_mock_addinterface_ip_addr(router, subnet, port,
                                              ip_addr, errors)
        self._check_router_addinterface(router, subnet, ip_addr)

    def _setup_mock_addinterface_ip_addr(self, router, subnet, port,
                                         ip_addr, errors=[]):
        subnet_get = api.neutron.subnet_get(IsA(http.HttpRequest), subnet.id)
        if 'subnet_get' in errors:
            subnet_get.AndRaise(self.exceptions.neutron)
            return
        subnet_get.AndReturn(subnet)

        params = {'network_id': subnet.network_id,
                  'fixed_ips': [{'subnet_id': subnet.id,
                                 'ip_address': ip_addr}]}
        port_create = api.neutron.port_create(IsA(http.HttpRequest), **params)
        if 'port_create' in errors:
            port_create.AndRaise(self.exceptions.neutron)
            return
        port_create.AndReturn(port)

        add_inf = api.neutron.router_add_interface(
            IsA(http.HttpRequest), router.id, port_id=port.id)
        if 'add_interface' not in errors:
            return

        add_inf.AndRaise(self.exceptions.neutron)
        port_delete = api.neutron.port_delete(IsA(http.HttpRequest), port.id)
        if 'port_delete' in errors:
            port_delete.AndRaise(self.exceptions.neutron)

    @test.create_stubs({api.neutron: ('router_add_interface', 'subnet_get',
                                      'port_create',
                                      'router_get', 'network_list')})
    def test_router_addinterface_ip_addr(self):
        self._test_router_addinterface_ip_addr()

    @test.create_stubs({api.neutron: ('subnet_get',
                                      'router_get', 'network_list')})
    def test_router_addinterface_ip_addr_exception_subnet_get(self):
        self._test_router_addinterface_ip_addr(errors=['subnet_get'])

    @test.create_stubs({api.neutron: ('subnet_get', 'port_create',
                                      'router_get', 'network_list')})
    def test_router_addinterface_ip_addr_exception_port_create(self):
        self._test_router_addinterface_ip_addr(errors=['port_create'])

    @test.create_stubs({api.neutron: ('router_add_interface', 'subnet_get',
                                      'port_create', 'port_delete',
                                      'router_get', 'network_list')})
    def test_router_addinterface_ip_addr_exception_add_interface(self):
        self._test_router_addinterface_ip_addr(errors=['add_interface'])

    @test.create_stubs({api.neutron: ('router_add_interface', 'subnet_get',
                                      'port_create', 'port_delete',
                                      'router_get', 'network_list')})
    def test_router_addinterface_ip_addr_exception_port_delete(self):
        self._test_router_addinterface_ip_addr(errors=['add_interface',
                                                       'port_delete'])

    @test.create_stubs({api.neutron: ('router_get',
                                      'router_add_gateway',
                                      'network_list')})
    def test_router_add_gateway(self):
        router = self.routers.first()
        network = self.networks.first()
        api.neutron.router_add_gateway(
            IsA(http.HttpRequest),
            router.id,
            network.id).AndReturn(None)
        api.neutron.router_get(
            IsA(http.HttpRequest), router.id).AndReturn(router)
        search_opts = {'router:external': True}
        api.neutron.network_list(
            IsA(http.HttpRequest), **search_opts).AndReturn([network])
        self.mox.ReplayAll()

        form_data = {'router_id': router.id,
                     'router_name': router.name,
                     'network_id': network.id}

        url = reverse('horizon:%s:l3routers:setgateway' % self.DASHBOARD,
                      args=[router.id])
        res = self.client.post(url, form_data)
        self.assertNoFormErrors(res)
        detail_url = self.INDEX_URL
        self.assertRedirectsNoFollow(res, detail_url)

    @test.create_stubs({api.neutron: ('router_get',
                                      'router_add_gateway',
                                      'network_list')})
    def test_router_add_gateway_exception(self):
        router = self.routers.first()
        network = self.networks.first()
        api.neutron.router_add_gateway(
            IsA(http.HttpRequest),
            router.id,
            network.id).AndRaise(self.exceptions.neutron)
        api.neutron.router_get(
            IsA(http.HttpRequest), router.id).AndReturn(router)
        search_opts = {'router:external': True}
        api.neutron.network_list(
            IsA(http.HttpRequest), **search_opts).AndReturn([network])
        self.mox.ReplayAll()

        form_data = {'router_id': router.id,
                     'router_name': router.name,
                     'network_id': network.id}

        url = reverse('horizon:%s:l3routers:setgateway' % self.DASHBOARD,
                      args=[router.id])
        res = self.client.post(url, form_data)
        self.assertNoFormErrors(res)
        detail_url = self.INDEX_URL
        self.assertRedirectsNoFollow(res, detail_url)

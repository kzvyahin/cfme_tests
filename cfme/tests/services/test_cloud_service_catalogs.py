# -*- coding: utf-8 -*-
import fauxfactory
import pytest

from cfme.common.provider import cleanup_vm
from cfme.services.catalogs import catalog_item as cct
from cfme.automate.service_dialogs import ServiceDialog
from cfme.services.catalogs.catalog import Catalog
from cfme.services.catalogs.service_catalogs import ServiceCatalogs
from cfme.services import requests
from cfme.web_ui import flash
from cfme import test_requirements
from utils import testgen
from utils.log import logger
from utils.wait import wait_for


pytestmark = [
    test_requirements.service,
    pytest.mark.meta(server_roles="+automate"),
    pytest.mark.tier(2)
]


def pytest_generate_tests(metafunc):
    # Filter out providers without templates defined
    argnames, argvalues, idlist = testgen.cloud_providers(
        metafunc, required_fields=[['provisioning', 'image']]
    )
    testgen.parametrize(metafunc, argnames, argvalues, ids=idlist, scope="module")


@pytest.yield_fixture(scope="function")
def dialog():
    dialog = "dialog_" + fauxfactory.gen_alphanumeric()
    element_data = dict(
        ele_label="ele_" + fauxfactory.gen_alphanumeric(),
        ele_name=fauxfactory.gen_alphanumeric(),
        ele_desc="my ele desc",
        choose_type="Text Box",
        default_text_box="default value"
    )
    service_dialog = ServiceDialog(label=dialog, description="my dialog",
                                   submit=True, cancel=True,
                                   tab_label="tab_" + fauxfactory.gen_alphanumeric(),
                                   tab_desc="my tab desc",
                                   box_label="box_" + fauxfactory.gen_alphanumeric(),
                                   box_desc="my box desc")
    service_dialog.create(element_data)
    flash.assert_success_message('Dialog "{}" was added'.format(dialog))
    yield dialog


@pytest.yield_fixture(scope="function")
def catalog():
    cat_name = "cat_" + fauxfactory.gen_alphanumeric()
    catalog = Catalog(name=cat_name, description="my catalog")
    catalog.create()
    yield catalog


def test_cloud_catalog_item(setup_provider, provider, dialog, catalog, request, provisioning):
    """Tests cloud catalog item

    Metadata:
        test_flag: provision
    """
    vm_name = 'test{}'.format(fauxfactory.gen_alphanumeric())
    # GCE accepts only lowercase letters in VM name
    vm_name = vm_name.lower()
    request.addfinalizer(lambda: cleanup_vm(vm_name + "_0001", provider))
    image = provisioning['image']['name']
    item_name = fauxfactory.gen_alphanumeric()
    provisioning_data = dict(
        vm_name=vm_name,
        instance_type=provisioning['instance_type'],
        security_groups=[provisioning['security_group']],
    )
    if provider.type == "azure":
        updates = dict(
            virtual_private_cloud=provisioning['virtual_private_cloud'],
            cloud_subnet=provisioning['cloud_subnet'],
            resource_group=[provisioning['resource_group']],
        )
    else:
        updates = dict(
            availability_zone=provisioning['availability_zone'],
            cloud_tenant=provisioning['cloud_tenant'],
            cloud_network=provisioning['cloud_network'],
            guest_keypair=provisioning['guest_keypair'],
            boot_disk_size=provisioning['boot_disk_size']
        )
    provisioning_data.update(updates)
    catalog_item = cct.CatalogItem(item_type=provisioning['item_type'], name=item_name,
                  description="my catalog", display_in=True, catalog=catalog.name,
                  dialog=dialog, catalog_name=image,
                  provider=provider.name, prov_data=provisioning_data)
    catalog_item.create()
    service_catalogs = ServiceCatalogs("service_name")
    service_catalogs.order(catalog.name, catalog_item)
    flash.assert_no_errors()
    logger.info('Waiting for cfme provision request for service %s', item_name)
    row_description = item_name
    cells = {'Description': row_description}
    row, __ = wait_for(requests.wait_for_request, [cells, True],
                       fail_func=requests.reload, num_sec=1000, delay=20)
    assert row.request_state.text == 'Finished'

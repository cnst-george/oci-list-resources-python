"""
#
# Copyright (c) 2021, 2022, Oracle Corporation and/or its affiliates.
# Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl.
"""
 
import os
import sys
import oci
from oci.events import models as event_models
from oci.functions import models as fn_models
from oci.monitoring import models as monitoring_models
from oci.artifacts import models as artifacts_models
from oci.ons import models as ons_models
from oci import pagination
import argparse
import textwrap
 
REGION = ''
 
 
def get_config():
    if REGION != '':
        return {"region": REGION}
    return {}
 
 
"""
Lists and deletes the resources like instances, policies, volumes, VCN related resources, logs and tags etc..
"""
 
 
class CleanUpResources:
 
    def __init__(self, service_name_prefix):
        self.service_name_prefix = service_name_prefix
        # delegate token should be present at /etc/oci/delegation_token in cloud shell
        if os.path.exists('/etc/oci/delegation_token'):
            with open('/etc/oci/delegation_token', 'r') as file:
                delegation_token = file.read()
            self.signer = oci.auth.signers.InstancePrincipalsDelegationTokenSigner(delegation_token=delegation_token)
        else:
            print("ERROR: In the Cloud shell the delegation token does not exist at location /etc/oci/delegation_token."
                  "Run the script from the Cloud shell, where you need to delete the resources.")
            sys.exit(1)
        self.vcn_client = oci.core.VirtualNetworkClient(config=get_config(), signer=self.signer)
        self.virtual_network_composite_operations = oci.core.VirtualNetworkClientCompositeOperations(self.vcn_client)
        self.log_client = oci.logging.LoggingManagementClient(config=get_config(), signer=self.signer)
        self.log_composite_operations = oci.logging.LoggingManagementClientCompositeOperations(self.log_client)
        self.identity_client = oci.identity.IdentityClient(config={}, signer=self.signer)
        self.identity_client_composite_operations = oci.identity.IdentityClientCompositeOperations(self.identity_client)
        self.events_client = oci.events.EventsClient(config=get_config(), signer=self.signer)
        self.events_client_composite_operations = oci.events.EventsClientCompositeOperations(self.events_client)
        self.fn_client = oci.functions.FunctionsManagementClient(config=get_config(), signer=self.signer)
        self.fn_composite_operations = oci.functions.FunctionsManagementClientCompositeOperations(client=self.fn_client)
        self.monitoring_client = oci.monitoring.MonitoringClient(config=get_config(), signer=self.signer)
        self.monitoring_composite_operations = oci.monitoring.MonitoringClientCompositeOperations(
            client=self.monitoring_client)
        self.artifacts_client = oci.artifacts.ArtifactsClient(config=get_config(), signer=self.signer)
        self.artifacts_composite_operations = oci.artifacts.ArtifactsClientCompositeOperations(
            client=self.artifacts_client)
        self.ons_control_plane_client = oci.ons.NotificationControlPlaneClient(config=get_config(), signer=self.signer)
 
    # Lists all the resources based on the service name prefix
    def list_all_resources(self):
        search_client = oci.resource_search.ResourceSearchClient(config=get_config(), signer=self.signer)
        running_resources = ["RUNNING", "Running", "AVAILABLE", "STOPPED", "Stopped", "ACTIVE", "CREATED", "INACTIVE"]
        resource_not_required = ["PrivateIp", "Vnic"]
        # https://docs.oracle.com/en-us/iaas/Content/Search/Concepts/queryoverview.htm#resourcetypes
        structured_search = oci.resource_search.models.StructuredSearchDetails(
            query="query all resources where displayname =~ '{}'".format(self.service_name_prefix),
            type='Structured',
            matching_context_type=oci.resource_search.models.SearchDetails.MATCHING_CONTEXT_TYPE_NONE)
 
        resources = search_client.search_resources(structured_search)
        resources_details = []
        no_of_resources = 0
        # Tags and default route table doesn't start with service prefix
        tagname_resource = "wlsoci-" + self.service_name_prefix
        default_rt = "Default Route Table for " + self.service_name_prefix
        # Logs and unified agent config resources use service_prefix with underscore instead of hyphen
        log_resource = self.service_name_prefix[:-1] + "_"
        print(
            "Resource Name                              Resource Type                        Resource Lifecycle State                 OCID         DOC")
        print(
            "=================================================================================================================================================")
        for resource in resources.data.items:
            resource_name = resource.display_name
            if (resource_name.startswith(
                    self.service_name_prefix) or tagname_resource in resource_name or default_rt in resource_name or log_resource in resource_name) and (
                    resource.lifecycle_state in running_resources) and (
                    resource.resource_type not in resource_not_required):
                resources_details.append(resource)
                no_of_resources = no_of_resources + 1
                print("{}             {}          {}          {}           {}".format(resource.display_name,
                                                                                      resource.resource_type,
                                                                                      resource.lifecycle_state,
                                                                                      resource.identifier,
                                                                                      resource.time_created))
        print(
            "================================================================================================================================================")
        print("Total number of resources {}".format(len(resources_details)))
        return resources_details
 
    # Removes all resources based on the service name prefix
    def cleanup_resources(self, delete_list):
        print("Deleting the resources")
        self.delete_all_autoscaling_resources(delete_list)
        self.delete_policies(delete_list)
        self.delete_instance(delete_list)
        self.delete_block_volumes(delete_list)
        self.delete_load_balancer(delete_list)
        self.delete_subnet(delete_list)
        self.delete_sec_list(delete_list)
        self.delete_route_table(delete_list)
        self.delete_dhcp_options(delete_list)
        self.delete_internet_gateway(delete_list)
        self.delete_service_gateway(delete_list)
        self.delete_local_peering_gateway(delete_list)
        self.delete_nat_gateway(delete_list)
        self.delete_vcn_resources(delete_list)
        self.delete_unified_agent_configuration(delete_list)
        self.delete_log(delete_list)
        self.delete_log_group(delete_list)
        self.delete_mount_targets(delete_list)
        self.delete_fss(delete_list)
        self.delete_tag_namespace(delete_list)
        self.delete_boot_volumes(delete_list)
 
    # Delete Policies
    def delete_policies(self, delete_list):
        for resource in delete_list:
            if resource.resource_type == "Policy":
                policy_ocid = resource.identifier
                print("Deleting policy: {0}, with ocid: {1}".format(resource.display_name, policy_ocid))
                try:
                    self.identity_client_composite_operations.delete_policy_and_wait_for_state(
                        policy_ocid,
                        wait_for_states=[oci.identity.models.Policy.LIFECYCLE_STATE_DELETED])
                    print("Deleted policy successfully!")
                except Exception as e:
                    print("Error while deleting the policy {0}, policy id {1}, Error message {2}".format(
                        resource.display_name, policy_ocid, str(e)))
 
    # Delete Dynamic Group
    def delete_dynamic_group(self):
        tenancy = os.environ['OCI_TENANCY']
        dynamic_group_list = self.identity_client.list_dynamic_groups(tenancy).data
        for d_group in dynamic_group_list:
            if self.service_name_prefix in d_group.name:
                print("Deleting the dynamic group: {0}, with ocid: {1}".format(d_group.name, d_group.id))
                try:
                    self.identity_client_composite_operations.delete_dynamic_group_and_wait_for_state(
                        d_group.id, wait_for_states=[oci.identity.models.DynamicGroup.LIFECYCLE_STATE_DELETED])
                    print("Deleted the dynamic group successfully!")
                except Exception as e:
                    print("Error while deleting the dynamic group name {}, ocid {}, Error message {}".format(
                        d_group.name, d_group.id, str(e)))
 
    # Delete Block Volumes
    def delete_block_volumes(self, delete_list):
        bv_client = oci.core.BlockstorageClient(config=get_config(), signer=self.signer)
        bv_composite_operations = oci.core.BlockstorageClientCompositeOperations(bv_client)
        for resource in delete_list:
            if resource.resource_type == "Volume":
                bv_ocid = resource.identifier
                try:
                    print(
                        "Deleting the block volume: {0}, with ocid {1}".format(resource.display_name, bv_ocid))
                    bv_composite_operations.delete_volume_and_wait_for_state(
                        bv_ocid, wait_for_states=[oci.core.models.Volume.LIFECYCLE_STATE_TERMINATED])
                    print("Deleted the block volume successfully!")
                except Exception as e:
                    print(
                        "Error while deleting the block volume {0}, ocid {1}, Error message {2}".format(
                            resource.display_name, bv_ocid, str(e)))
 
    # Delete all compute instances
    def delete_instance(self, delete_list):
        compute_client = oci.core.ComputeClient(config=get_config(), signer=self.signer)
        compute_composite_operations = oci.core.ComputeClientCompositeOperations(compute_client)
        for resource in delete_list:
            if resource.resource_type == "Instance":
                instance_ocid = resource.identifier
                instance_name = resource.display_name
                print("Deleting the compute instance: {0}, with ocid {1}".format(instance_name, instance_ocid))
                try:
                    compute_composite_operations.terminate_instance_and_wait_for_state(
                        instance_ocid, wait_for_states=[oci.core.models.Instance.LIFECYCLE_STATE_TERMINATED])
                    print("Deleted the compute instance successfully!")
                except Exception as e:
                    print(
                        "Error while deleting the instance {0}, ocid {1}, Error message {2}".format(
                            instance_name, instance_ocid, str(e)))
 
    # Delete all Subnets in the VCN
    def delete_subnet(self, delete_list):
        for resource in delete_list:
            if resource.resource_type == "Subnet":
                subnet_ocid = resource.identifier
                print(
                    "Deleting subnet: {0}, with ocid {1}".format(resource.display_name, resource.identifier))
                try:
                    self.virtual_network_composite_operations.delete_subnet_and_wait_for_state(
                        subnet_ocid,
                        wait_for_states=[oci.core.models.Subnet.LIFECYCLE_STATE_TERMINATED])
                    print("Deleted subnet successfully!")
                except Exception as e:
                    print(
                        "Error while deleting the subnet {0}, ocid {1}, Error message {2}".format(resource.display_name,
                                                                                                  subnet_ocid, str(e)))
 
    # Delete Security lists
    def delete_sec_list(self, delete_list):
        for resource in delete_list:
            if resource.resource_type == "SecurityList":
                sec_list_name = resource.display_name
                sec_list_ocid = resource.identifier
                if not ("Default" in sec_list_name):
                    print(
                        "Deleting the security list: {0}, with ocid {1}".format(resource.display_name,
                                                                                resource.identifier))
                    try:
                        self.virtual_network_composite_operations.delete_security_list_and_wait_for_state(
                            sec_list_ocid,
                            wait_for_states=[oci.core.models.SecurityList.LIFECYCLE_STATE_TERMINATED])
                        print("Deleted the security list successfully!")
                    except Exception as e:
                        print(
                            "Error while deleting the security list {0}, ocid {1}, Error message {2}".format(
                                resource.display_name, sec_list_ocid, str(e)))
 
    # Delete Load balancers
    def delete_load_balancer(self, delete_list):
        lb_client = oci.load_balancer.LoadBalancerClient(config=get_config(), signer=self.signer)
        lb_composite_operations = oci.load_balancer.LoadBalancerClientCompositeOperations(lb_client)
        for resource in delete_list:
            if resource.resource_type == "LoadBalancer":
                lb_name = resource.display_name
                lb_ocid = resource.identifier
                print("Deleting Load balancer {0} with ocid {1}".format(lb_name, lb_ocid))
                try:
                    lb_composite_operations.delete_load_balancer_and_wait_for_state(
                        lb_ocid,
                        wait_for_states=[oci.load_balancer.models.WorkRequest.LIFECYCLE_STATE_SUCCEEDED])
                    print("Load balancer deleted successfully!")
                except Exception as e:
                    print(
                        "Error while deleting the loadbalancer {0}, ocid {1}, Error message {2}".format(
                            lb_name, lb_ocid, str(e)))
 
    # Delete Route tables
    def delete_route_table(self, delete_list):
        for resource in delete_list:
            if resource.resource_type == "RouteTable":
                route_table_name = resource.display_name
                route_table_ocid = resource.identifier
                # Removing the route rules from the tables
                rt_details = oci.core.models.UpdateRouteTableDetails()
                rt_details.route_rules = []
                self.virtual_network_composite_operations.update_route_table_and_wait_for_state(
                    route_table_ocid, rt_details,
                    wait_for_states=[oci.core.models.RouteTable.LIFECYCLE_STATE_AVAILABLE])
                self.vcn_client.update_route_table(route_table_ocid, rt_details)
                # Default route table can't be deleted from VCN
                if not ("Default" in route_table_name):
                    print(
                        "Deleting the route table: {0}, with ocid {1}".format(resource.display_name,
                                                                              resource.identifier))
                    try:
                        self.virtual_network_composite_operations.delete_route_table_and_wait_for_state(
                            route_table_ocid,
                            wait_for_states=[oci.core.models.RouteTable.LIFECYCLE_STATE_TERMINATED])
 
                        print("Deleted the route table successfully!")
                    except Exception as e:
                        print("Error while deleting the route table {0}, ocid {1}, Error message {2}".format(
                            resource.display_name, route_table_ocid, str(e)))
                        if "associated with Subnet" in str(e):
                            try:
                                self.delete_subnet_route_table_association(route_table_ocid)
                                # After removing the association again retrying the removal of route table
                                # This is for Db subnet route table
                                self.virtual_network_composite_operations.delete_route_table_and_wait_for_state(
                                    route_table_ocid,
                                    wait_for_states=[oci.core.models.RouteTable.LIFECYCLE_STATE_TERMINATED])
                                print("Deleted the route table successfully!")
                            except Exception as e:
                                print("Error while deleting the route table after removing the association "
                                      "{0}, ocid {1}, Error message {2}".format
                                      (resource.display_name, route_table_ocid, str(e)))
 
    # Delete Subnet and route table association to remove route table
    def delete_subnet_route_table_association(self, route_table_ocid):
        default_rt_id_in_vcn = ""
        print("Route table is associated with a subnet. Removing the association between the subnet and route table")
        rt_res = self.vcn_client.get_route_table(route_table_ocid).data
        vcn_id = rt_res.vcn_id
        compartment_id = rt_res.compartment_id
        list_route_rables_vcn = self.vcn_client.list_route_tables(compartment_id=compartment_id,
                                                                  vcn_id=vcn_id).data
        for rt in list_route_rables_vcn:
            if "Default Route" in rt.display_name:
                default_rt_id_in_vcn = rt.id
        list_subnets = self.vcn_client.list_subnets(compartment_id=compartment_id, vcn_id=vcn_id).data
        for subnet in list_subnets:
            subnet_ocid = subnet.id
            if subnet.route_table_id == route_table_ocid:
                subnet_details = oci.core.models.UpdateSubnetDetails()
                subnet_details.route_table_id = default_rt_id_in_vcn
                try:
                    self.virtual_network_composite_operations.update_subnet_and_wait_for_state(
                        subnet_ocid, subnet_details,
                        wait_for_states=[oci.core.models.Subnet.LIFECYCLE_STATE_AVAILABLE])
                    print("Removed the association between the subnet and route table.")
                except Exception as e:
                    print("Error while removing the association between the subnet and route table {}".format(str(e)))
 
    # Delete DHCP Options
    def delete_dhcp_options(self, delete_list):
        for resource in delete_list:
            if resource.resource_type == "DHCPOptions":
                dhcp_name = resource.display_name
                dhcp_ocid = resource.identifier
                if not ("Default" in dhcp_name):
                    print(
                        "Deleting the DHCP options: {0}, with ocid {1}".format(resource.display_name, dhcp_ocid))
                    try:
                        self.virtual_network_composite_operations.delete_dhcp_options_and_wait_for_state(dhcp_ocid,
                                                                                                         wait_for_states=[
                                                                                                             oci.core.models.DhcpOptions.LIFECYCLE_STATE_TERMINATED])
                        print("Deleted the DHCP options successfully!")
                    except Exception as e:
                        print(
                            "Error while deleting the DHCP options {0}, ocid {1}, Error message {2} ".format(
                                resource.display_name, dhcp_ocid, str(e)))
 
    # Delete Internet Gateway
    def delete_internet_gateway(self, delete_list):
        for resource in delete_list:
            if resource.resource_type == "InternetGateway":
                ig_ocid = resource.identifier
                print("Deleting the Internet Gateway: {0}, with ocid {1}".format(resource.display_name,
                                                                                 ig_ocid))
                try:
                    self.virtual_network_composite_operations.delete_internet_gateway_and_wait_for_state(ig_ocid,
                                                                                                         wait_for_states=[
                                                                                                             oci.core.models.InternetGateway.LIFECYCLE_STATE_TERMINATED])
 
                    print("Deleted the Internet Gateway successfully!")
                except Exception as e:
                    print("Error while deleting the Internet Gateway {0}, ocid {1}, Error message {2}".format(
                        resource.display_name,
                        ig_ocid, str(e)))
 
    # Delete Service Gateway
    def delete_service_gateway(self, delete_list):
        for resource in delete_list:
            if resource.resource_type == "ServiceGateway":
                svc_gateway_ocid = resource.identifier
                print("Deleting the service gateway: {0}, with ocid {1}".format(resource.display_name,
                                                                                svc_gateway_ocid))
                try:
                    self.virtual_network_composite_operations.delete_service_gateway_and_wait_for_state(
                        svc_gateway_ocid, wait_for_states=[oci.core.models.ServiceGateway.LIFECYCLE_STATE_TERMINATED])
 
                    print("Deleted the service gateway successfully!")
                except Exception as e:
                    print("Error while deleting the service gateway {0}, ocid {1}, Error message {2}".format(
                        resource.display_name,
                        svc_gateway_ocid, str(e)))
 
    # Delete Local Peering Gateway
    def delete_local_peering_gateway(self, delete_list):
        for resource in delete_list:
            if resource.resource_type == "LocalPeeringGateway":
                lpg_ocid = resource.identifier
                print("Deleting the local peering gateway: {0}, with ocid {1}".format(resource.display_name,
                                                                                      lpg_ocid))
                try:
                    self.virtual_network_composite_operations.delete_local_peering_gateway_and_wait_for_state(
                        lpg_ocid, wait_for_states=[oci.core.models.LocalPeeringGateway.LIFECYCLE_STATE_TERMINATED])
 
                    print("Deleted local peering gateway successfully!")
                except Exception as e:
                    print("Error while deleting the local peering gateway {0}, ocid {1}, Error message {2}".format(
                        resource.display_name, lpg_ocid, str(e)))
 
    # Delete Nat Gateway
    def delete_nat_gateway(self, delete_list):
        for resource in delete_list:
            if resource.resource_type == "NatGateway":
                nat_ocid = resource.identifier
                print("Deleting the NAT gateway: {0}, with ocid {1}".format(resource.display_name,
                                                                            nat_ocid))
                try:
                    self.virtual_network_composite_operations.delete_nat_gateway_and_wait_for_state(
                        nat_gateway_id=nat_ocid,
                        wait_for_states=[oci.core.models.NatGateway.LIFECYCLE_STATE_TERMINATED]
                    )
                    print("Deleted the NAT gateway successfully!")
                except Exception as e:
                    print("Error while deleting the NAT gateway {0}, ocid {1}, Error message {2}".format(
                        resource.display_name, nat_ocid, str(e)))
 
    # Delete VCN
    def delete_vcn_resources(self, delete_list):
        for resource in delete_list:
            if resource.resource_type == "Vcn":
                vcn_ocid = resource.identifier
                vcn_name = resource.display_name
                print("Deleting the VCN: {0}, with ocid {1}".format(vcn_name, vcn_ocid))
                try:
                    self.virtual_network_composite_operations.delete_vcn_and_wait_for_state(vcn_ocid,
                                                                                            oci.core.models.Vcn.LIFECYCLE_STATE_TERMINATED)
                    print("Deleted the VCN successfully!")
                except Exception as e:
                    print("Error while deleting the VCN {0}, VCN id {1}, Error message {2}".format(vcn_name, vcn_ocid,
                                                                                                   str(e)))
 
    # Deleting the Unified Agent Configuration
    def delete_unified_agent_configuration(self, delete_list):
        for resource in delete_list:
            if resource.resource_type == "UnifiedAgentConfiguration":
                uac_ocid = resource.identifier
                print("Deleting the unified agent configuration: {}, with ocid {}".format(resource.display_name,
                                                                                          uac_ocid))
                try:
                    self.log_composite_operations.delete_unified_agent_configuration_and_wait_for_state(
                        uac_ocid,
                        wait_for_states=[oci.logging.models.WorkRequest.STATUS_SUCCEEDED])
                    print("Deleted the unified agent configuration successfully!")
                except Exception as e:
                    print(
                        "Error while deleting the unified agent configuration name {0}, ocid {1} - Error message {2}".format(
                            resource.display_name, uac_ocid, str(e)))
 
    # Delete logs in a Log groups
    def delete_log(self, delete_list, name=None):
        """
        Delete log resources for the service.
 
        :param delete_list:
        :param name: if name is set, only delete the named log resource, otherwise delete all log resources in the delete_list
        :return:
        """
        for resource in delete_list:
            if resource.resource_type == "LogGroup":
                log_group_ocid = resource.identifier
                list_logs = self.log_client.list_logs(log_group_ocid).data
                for log in list_logs:
                    to_delete = True
 
                    if name is not None:
                        if log.display_name != name:
                            to_delete = False
                    if to_delete:
                        print("Deleting the log name {0}, with log ocid {1}".format(log.display_name, log.id))
                        try:
                            self.log_composite_operations.delete_log_and_wait_for_state(
                                log_group_ocid, log.id,
                                wait_for_states=[oci.logging.models.WorkRequest.STATUS_SUCCEEDED])
                            print("Deleted the log {} successfully!".format(log.display_name))
 
                        except Exception as e:
                            print("Error while deleting the log name {}, log ocid {}, Error message {}".format(
                                log.display_name, log.id, str(e)))
 
    # Delete Log Group
    def delete_log_group(self, delete_list):
        for resource in delete_list:
            if resource.resource_type == "LogGroup":
                log_group_ocid = resource.identifier
                print("Deleting the log group: {0}, with ocid {1}".format(resource.display_name,
                                                                          log_group_ocid))
                try:
                    self.log_composite_operations.delete_log_group_and_wait_for_state(
                        log_group_ocid, wait_for_states=[oci.logging.models.WorkRequest.STATUS_SUCCEEDED])
 
                    print("Deleted log group successfully!")
                except Exception as e:
                    print("Error while deleting the log group {0}, ocid {1}, Error message {2}".format(
                        resource.display_name, log_group_ocid, str(e)))
 
    # Delete the Mount targets
    def delete_mount_targets(self, delete_list):
        mt_client = oci.file_storage.FileStorageClient(config=get_config(), signer=self.signer)
        mt_composite_operations = oci.file_storage.FileStorageClientCompositeOperations(mt_client)
        for resource in delete_list:
            if resource.resource_type == "MountTarget":
                mt_ocid = resource.identifier
                print("Deleting the mount target {0}, with ocid {1}".format(resource.display_name, mt_ocid))
                try:
                    mt_composite_operations.delete_mount_target_and_wait_for_state(
                        mt_ocid, wait_for_states=[oci.file_storage.models.MountTarget.LIFECYCLE_STATE_DELETED])
                    print("Deleted the mount target successfully!")
                except Exception as e:
                    print("Error while deleting the mount target {0}, ocid {1}, Error message {2}".format(
                        resource.display_name, mt_ocid, str(e)))
 
    # Delete FSS
    def delete_fss(self, delete_list):
        fss_client = oci.file_storage.FileStorageClient(config=get_config(), signer=self.signer)
        fss_composite_operations = oci.file_storage.FileStorageClientCompositeOperations(fss_client)
        for resource in delete_list:
            if resource.resource_type == "FileSystem":
                fss_ocid = resource.identifier
                try:
                    # Get the list of exports to delete
                    list_exports = fss_client.list_exports(file_system_id=fss_ocid).data
                    for export in list_exports:
                        export_ocid = export.id
                        print("Deleting the export id {}".format(export_ocid))
                        fss_composite_operations.delete_export_and_wait_for_state(
                            export_id=export_ocid,
                            wait_for_states=[oci.file_storage.models.Export.LIFECYCLE_STATE_DELETED])
                        print("Deleted the exports successfully!")
                except Exception as e:
                    print("Error while deleting the export, Error message {}".format(str(e)))
                try:
                    print("Deleting the FSS: {0}, with ocid {1}".format(resource.display_name, fss_ocid))
                    fss_composite_operations.delete_file_system_and_wait_for_state(
                        fss_ocid, wait_for_states=[oci.file_storage.models.FileSystem.LIFECYCLE_STATE_DELETED])
                    print("Deleted the FSS successfully!")
                except Exception as e:
                    print("Error while deleting the FSS name {0}, ocid {1}, Error message {2}".format(
                        resource.display_name, fss_ocid, str(e)))
 
    # Deletion of TagNamespace
    def delete_tag_namespace(self, delete_list):
        for resource in delete_list:
            if resource.resource_type == "TagNamespace":
                tag_ns_name = resource.display_name
                tag_ns_ocid = resource.identifier
                print("Deleting the tag namespace {0}, with ocid {1}".format(tag_ns_name, tag_ns_ocid))
                try:
                    # Retiring the tag namespace
                    tag_status = self.identity_client.get_tag_namespace(tag_namespace_id=tag_ns_ocid).data
                    print("Tag namespace: {} and isRetired: {}".format(tag_ns_name, tag_status.is_retired))
 
                    if not tag_status.is_retired:
                        print("Retiring the tag namespace {}".format(tag_ns_name))
                        tag_ns_details = oci.identity.models.UpdateTagNamespaceDetails()
                        tag_ns_details.is_retired = True
                        self.identity_client_composite_operations.update_tag_namespace_and_wait_for_state(
                            tag_namespace_id=tag_ns_ocid,
                            update_tag_namespace_details=tag_ns_details,
                            wait_for_states=[
                                oci.identity.models.TagNamespace.LIFECYCLE_STATE_INACTIVE])
                        tag_status = self.identity_client.get_tag_namespace(tag_namespace_id=tag_ns_ocid).data
                        print("Tag status before deleting {}".format(tag_status.is_retired))
                    print("Deleting the tag namespace {}".format(tag_ns_name))
                    # Tag namespace deletion is taking too long time. So not waiting for the completion.
                    self.identity_client.cascade_delete_tag_namespace(tag_namespace_id=tag_ns_ocid)
                    print("Asynchronous deletion of Tag namespaces is enabled."
                          "Check the deletion status manually. Tag name {0} with ocid {1}".format(tag_ns_name,
                                                                                                  tag_ns_ocid))
                except Exception as e:
                    print("Error while deleting the Tag namespace {0}, ocid {1}, Error message {2} "
                          .format(tag_ns_name, tag_ns_ocid, str(e)))
 
    # Deleting the unattached boot volumes
    def delete_boot_volumes(self, delete_list):
        bv_client = oci.core.BlockstorageClient(config=get_config(), signer=self.signer)
        bv_composite_operations = oci.core.BlockstorageClientCompositeOperations(bv_client)
        for resource in delete_list:
            if resource.resource_type == "BootVolume" and resource.lifecycle_state == "AVAILABLE":
                bv_ocid = resource.identifier
                bv_name = resource.display_name
                print("Deleting the boot volume {}, with ocid {} ".format(bv_name, bv_ocid))
                try:
                    bv_composite_operations.delete_boot_volume_and_wait_for_state(
                        boot_volume_id=bv_ocid,
                        wait_for_states=[oci.core.models.BootVolume.LIFECYCLE_STATE_TERMINATED])
                    print("Deleted the boot volume successfully!")
                except Exception as e:
                    print("Error while deleting the boot volume name {}, ocid {}, Error message {}".format(bv_name,
                                                                                                           bv_ocid,
                                                                                                           str(e)))
 
    def delete_functions(self, delete_list):
        """
        Deletes OCI functions and function application for the service.
 
        :param delete_list:
        :return:
        """
        for resource in delete_list:
            if resource.resource_type == "FunctionsApplication":
                fn_app_id = resource.identifier
                fn_app_name = resource.display_name
                try:
                    result = pagination.list_call_get_all_results(
                        self.fn_client.list_functions,
                        fn_app_id
                    )
 
                    # Delete all functions within function application
                    print("Deleting functions within function application {}".format(fn_app_name))
                    for fn in result.data:
                        self.fn_composite_operations.delete_function_and_wait_for_state(
                            function_id=fn.id,
                            wait_for_states=[fn_models.Function.LIFECYCLE_STATE_DELETED]
                        )
                        print("Deleted the function {} successfully!".format(fn.display_name))
 
                except Exception as e:
                    print("Error while deleting the functions within application id {}, Error message {}".format(fn_app_id, str(e)))
 
 
    def delete_functions_app(self, delete_list):
        """
        Deletes function application for the service.
 
        :param delete_list:
        :return:
        """
        for resource in delete_list:
            if resource.resource_type == "FunctionsApplication":
                fn_app_id = resource.identifier
                try:
                    # Delete the function application
                    self.fn_composite_operations.delete_application_and_wait_for_state(
                        application_id = fn_app_id,
                        wait_for_states = [fn_models.Application.LIFECYCLE_STATE_DELETED]
                    )
                except Exception as e:
                    print("Error while deleting the Functions application with id {}, Error message {}".format(fn_app_id, str(e)))
 
    def delete_event_rules(self, delete_list):
        """
        Deletes the event rules for the service.
        :param delete_list:
        :return:
        """
        for resource in delete_list:
            if resource.resource_type == "EventRule":
                event_rule_id = resource.identifier
                event_rule_name = resource.display_name
                try:
                    print("Deleting event rule {}".format(event_rule_name))
                    self.events_client_composite_operations.delete_rule_and_wait_for_state(
                        rule_id=event_rule_id,
                        wait_for_states=[event_models.Rule.LIFECYCLE_STATE_DELETED]
                    )
                    print("Deleted the event rule {} successfully!".format(event_rule_name))
                except Exception as e:
                    print("Error while deleting the event rule id {}, Error message {}".format(event_rule_id, str(e)))
 
 
    def delete_autoscaling_logs(self, delete_list):
        """
        Deletes the event rule invoke log for the service.
 
        :param delete_list:
        :return:
        """
        # trim the extra hyphen char if present from the service_name_prefix
        service_name = self.service_name_prefix[:-1] if self.service_name_prefix[
                                                            -1] == '-' else self.service_name_prefix
        self.delete_log(delete_list, name="{0}_event_rule_invoke_log".format(service_name))
        self.delete_log(delete_list, name="{0}_autoscaling_log".format(service_name))
 
    def predestroy_autoscaling_resources(self, delete_list):
        """
        Deletes pre-destroy resources associated with autoscaling.
        This is to be invoked when user needs to delete only the resources created via API during provisioning outside
        of terraform preferably prior to running terraform destroy action.
 
        :param delete_list:
        :return:
        """
        print("Executing pre-destroy of resources created for autoscaling feature")
        self.delete_functions(delete_list)
        self.delete_event_rules(delete_list)
        self.delete_autoscaling_logs(delete_list)
 
    def delete_alarms(self, delete_list):
        """
        Delete all alarms created for autoscaling for the service.
 
        :param delete_list:
        :return:
        """
        for resource in delete_list:
            if resource.resource_type == "Alarm":
                alarm_id = resource.identifier
                alarm_name = resource.display_name
                try:
                    print("Deleting alarm {}".format(alarm_name))
                    self.monitoring_composite_operations.delete_alarm_and_wait_for_state(
                        alarm_id=alarm_id,
                        wait_for_states=[monitoring_models.Alarm.LIFECYCLE_STATE_DELETED]
                    )
                    print("Deleted the alarm {} successfully!".format(alarm_name))
                except Exception as e:
                    print("Error while deleting the alarm id {}, Error message {}".format(alarm_id, str(e)))
 
    def delete_container_repos(self, delete_list):
        """
        Deletes container repos created for autoscaling for the service.
        Deleting the repos also deletes the container images in those repos.
 
        :param delete_list:
        :return:
        """
        for resource in delete_list:
            if resource.resource_type == "ContainerRepo":
                repo_id = resource.identifier
                repo_name = resource.display_name
                try:
                    print("Deleting container repo {}".format(repo_name))
                    self.artifacts_composite_operations.delete_container_repository_and_wait_for_state(
                        repository_id=repo_id,
                        wait_for_states=[artifacts_models.ContainerRepository.LIFECYCLE_STATE_DELETED]
                    )
                    print("Deleted the container repo {} successfully!".format(repo_name))
                except Exception as e:
                    print("Error while deleting the container repo id {}, Error message {}".format(repo_id, str(e)))
 
    def delete_notification_topics(self, delete_list):
        """
        Deletes the notification topics created for autoscaling for the service.
        Deleting the notification topics also deletes the associated subscriptions for those topics.
 
        :param delete_list:
        :return:
        """
        for resource in delete_list:
            if resource.resource_type == "OnsTopic":
                topic_id = resource.identifier
                topic_name = resource.display_name
                try:
                    print("Deleting notification topic {}".format(topic_name))
                    self.ons_control_plane_client.delete_topic(
                        topic_id=topic_id
                    )
                    oci.wait_until(self.ons_control_plane_client, self.ons_control_plane_client.get_topic(topic_id),
                                   'lifecycle_state', ons_models.NotificationTopic.LIFECYCLE_STATE_DELETING)
                    print("Deleted the notification topic {} successfully!".format(topic_name))
                except Exception as e:
                    print(
                        "Error while deleting the notification topic id {}, Error message {}".format(topic_id, str(e)))
 
    def delete_all_autoscaling_resources(self, delete_list):
        """
        Deletes all resources created when autoscaling feature is enabled.
 
        :param delete_list:
        :return:
        """
        self.predestroy_autoscaling_resources(delete_list)
        self.delete_container_repos(delete_list)
        self.delete_alarms(delete_list)
        self.delete_notification_topics(delete_list)
        self.delete_functions_app(delete_list)
 
 
def main():
    parser = argparse.ArgumentParser(description=textwrap.dedent('''
        This script is used for:
        - pre-destroying autoscaling resources (prior to running destroy job on the stack from OCI Console)
        - delete all infra resources created for the stack (identified by its service name prefix)
    '''), formatter_class=argparse.RawDescriptionHelpFormatter)
    # Required position params
    parser.add_argument('command', choices=['delete', 'list', 'pre-destroy'], help='Command')
    parser.add_argument('service_name_prefix', help='Stack service name')
 
    # Optional params
    parser.add_argument('-r', '--region', default='', help='Region other than home region must be specified.')
    parser.add_argument('-f', '--feature', default='autoscaling', help='Feature to run pre-destroy for.')
 
    args = parser.parse_args()
 
    command = args.command
    service_prefix = args.service_name_prefix
 
    global REGION
 
    REGION = args.region
    feature = args.feature
 
    print("Service prefix name:" + service_prefix)
 
    if len(service_prefix) >= 16:
        service_prefix = service_prefix[0:16]
    service_prefix = service_prefix + "-"
    cleanup_util = CleanUpResources(service_prefix)
 
    if command == 'list':
        print("Listing all resources with service prefix name " + service_prefix)
        cleanup_resources = cleanup_util.list_all_resources()
    elif command == 'delete':
        print("Deleting all resources with service prefix name " + service_prefix)
        cleanup_resources = cleanup_util.list_all_resources()
        cleanup_util.cleanup_resources(cleanup_resources)
        cleanup_util.delete_dynamic_group()
    elif command == 'pre-destroy' and feature == 'autoscaling':
        print('Deleting pre-destroy autoscaling resources with service prefix name ' + service_prefix)
        cleanup_resources = cleanup_util.list_all_resources()
        cleanup_util.predestroy_autoscaling_resources(cleanup_resources)
 
 
if __name__ == '__main__':
    main()
#!/usr/bin/env python3
import oci
import pprint

config_file     = "~/.oci/config"
profile         = "DEFAULT"
compid          = "ocid1.tenancy.oc1..aaaaaaaafvbrqwizb2l62d7o46h622ibhfp2at56cfjxak7x3jqgh42ligrq"
config          = oci.config.from_file(config_file,profile)
search_client   = oci.resource_search.ResourceSearchClient(config)
resources_type  = oci.pagination.list_call_get_all_results(search_client.list_resource_types).data

for x in resources_type:
    structured_search = oci.resource_search.models.StructuredSearchDetails(
        query = f"query {x.name} resources where\n"
        f"compartmentId = '{compid}' &&\n"
        f"lifeCycleState != 'DELETED' &&\n"
        f"lifeCycleState != 'FAILED' &&\n"
        f"lifeCycleState != 'TERMINATED'",
        type  = 'Structured',
        matching_context_type = oci.resource_search.models.SearchDetails.MATCHING_CONTEXT_TYPE_NONE
    )
    res = search_client.search_resources(structured_search).data
    if len(res.items) > 0 :
        for i in res.items:
            data = {
                'compartment_id': i.compartment_id,
                'display_name': i.display_name,
                'id': i.identifier,
                'defined_tags': i.defined_tags,
                'freeform_tags': i.freeform_tags,
                'lifecycle_state': i.lifecycle_state
            }
            pprint.pprint(data) 
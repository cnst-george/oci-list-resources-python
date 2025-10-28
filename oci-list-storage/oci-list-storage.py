import oci
import json
import pandas as pd
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font
from openpyxl.chart import PieChart, BarChart, Reference

# Load OCI configuration
config = oci.config.from_file("~/.oci/config")

# Initialize OCI clients
identity_client = oci.identity.IdentityClient(config)
compute_client = oci.core.ComputeClient(config)
block_storage_client = oci.core.BlockstorageClient(config)
file_storage_client = oci.file_storage.FileStorageClient(config)
object_storage_client = oci.object_storage.ObjectStorageClient(config)

# Get tenancy ID
tenancy_ocid = config["tenancy"]

# Initialize result storage
resources = {}
findings = {}

try:
    # Fetch all compartments
    compartments = oci.pagination.list_call_get_all_results(
        identity_client.list_compartments,
        tenancy_ocid,
        compartment_id_in_subtree=True,
        access_level="ANY"
    ).data
    compartments.append(oci.identity.models.Compartment(id=tenancy_ocid, name="Tenancy Root"))

    # Discover resources in each compartment
    for compartment in compartments:
        if compartment.lifecycle_state == "ACTIVE":
            print(f"Discovering resources in compartment: {compartment.name}")
            resources[compartment.name] = {}
            findings[compartment.name] = []

            # Discover Block Volumes
            volume_response = oci.pagination.list_call_get_all_results(
                block_storage_client.list_volumes,
                compartment_id=compartment.id
            ).data
            volume_findings = []
            for volume in volume_response:
                resources[compartment.name].setdefault("Block Volumes", []).append({
                    "name": volume.display_name,
                    "id": volume.id
                })
                # Check if the volume is attached to any instance 
                attachments = oci.pagination.list_call_get_all_results(
                    compute_client.list_volume_attachments,
                    compartment_id=compartment.id,
                    volume_id=volume.id
                ).data
                if not attachments:  # No attachments found
                    volume_findings.append(f"Block Volume '{volume.display_name}' is not attached to any instance.")
                # Best practice: Ensure backup policy is set
                if not volume.is_auto_tune_enabled:
                    volume_findings.append(f"Block Volume '{volume.display_name}' does not have auto-tune enabled.")
            findings[compartment.name].extend(volume_findings)

            # Discover Object Storage Buckets
            # bucket_response = oci.pagination.list_call_get_all_results(
            #     object_storage_client.list_buckets,
            #     namespace_name=namespace,
            #     compartment_id=compartment.id
            # ).data
            # bucket_findings = []
            # for bucket in bucket_response:
            #     resources[compartment.name].setdefault("Buckets", []).append({"name": bucket.name})
            #     # Fetch detailed bucket info to check for public access
            #     bucket_details = object_storage_client.get_bucket(
            #         namespace_name=namespace,
            #         bucket_name=bucket.name
            #     ).data
            #     # Best practice: Check for public access
            #     if bucket_details.public_access_type != "NoPublicAccess":
            #         bucket_findings.append(f"Bucket '{bucket.name}' allows public access.")
            #     # Discover Objects in Buckets
            #     object_response = oci.pagination.list_call_get_all_results(
            #         object_storage_client.list_objects,
            #         namespace_name=namespace,
            #         bucket_name=bucket.name
            #     ).data
            #     resources[compartment.name].setdefault("Bucket Objects", []).extend([
            #         {"bucket_name": bucket.name, "object_name": obj.name} for obj in object_response.objects
            #     ])
            # findings[compartment.name].extend(bucket_findings)

    # Get current date for the file name
    current_date = datetime.now().strftime("%Y-%m-%d")
    tenancy_name = tenancy_ocid.split(".")[1] if tenancy_ocid else "unknown"
    
    # Generate file name with dynamic titles
    file_name = f"oci_volumes_{tenancy_name}_{current_date}.json"
    
    # Export data to JSON
    with open(file_name, "w") as file:
        json.dump({"resources": resources, "findings": findings}, file, indent=4)

    print(f"JSON file saved: {file_name}")
    
    # Export data to Excel
    workbook = Workbook()
    summary_sheet = workbook.active

    # Remove default sheet
    workbook.remove(workbook["Sheet"])

    # Add data sheets for each resource type
    for resource_type in ["Block Volumes"]:
        sheet = workbook.create_sheet(title=resource_type)
        sheet.append(["Compartment", "Name", "ID"])
        for compartment, resource_data in resources.items():
            for item in resource_data.get(resource_type, []):
                sheet.append([compartment, item.get("name"), item.get("id", "N/A")])

      # Generate file name with dynamic titles
    file_name = f"oci_volumes_{tenancy_name}_{current_date}.xlsx"
    
    # Save the Excel workbook
    workbook.save(file_name)
    print(f"Excel file saved: {file_name}")

except oci.exceptions.ServiceError as e:
    print(f"Service Error: {e}")
except Exception as e:
    print(f"Unexpected Error: {e}")
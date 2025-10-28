import oci
import json
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font
from openpyxl.chart import PieChart, BarChart, Reference

# Load OCI configuration
config = oci.config.from_file("~/.oci/config")

# Initialize OCI clients
identity_client = oci.identity.IdentityClient(config)
object_storage_client = oci.object_storage.ObjectStorageClient(config)
namespace = object_storage_client.get_namespace().data

# Get tenancy ID
tenancy_id = config["tenancy"]

# Initialize result storage
resources = {}
findings = {}

try:
    # Fetch all compartments
    compartments = oci.pagination.list_call_get_all_results(
        identity_client.list_compartments,
        tenancy_id,
        compartment_id_in_subtree=True,
        access_level="ANY"
    ).data
    compartments.append(oci.identity.models.Compartment(id=tenancy_id, name="Tenancy Root"))

    # Discover resources in each compartment
    for compartment in compartments:
        if compartment.lifecycle_state == "ACTIVE":
            print(f"Discovering resources in compartment: {compartment.name}")
            resources[compartment.name] = {}
            findings[compartment.name] = []

            # Discover Object Storage Buckets
            bucket_response = oci.pagination.list_call_get_all_results(
                object_storage_client.list_buckets,
                namespace_name=namespace,
                compartment_id=compartment.id
            ).data
            bucket_findings = []
            for bucket in bucket_response:
                resources[compartment.name].setdefault("Buckets", []).append({"name": bucket.name})
                # Fetch detailed bucket info to check for public access
                bucket_details = object_storage_client.get_bucket(
                    namespace_name=namespace,
                    bucket_name=bucket.name
                ).data
                # Best practice: Check for public access
                if bucket_details.public_access_type != "NoPublicAccess":
                    bucket_findings.append(f"Bucket '{bucket.name}' allows public access.")
                # Discover Objects in Buckets
                object_response = oci.pagination.list_call_get_all_results(
                    object_storage_client.list_objects,
                    namespace_name=namespace,
                    bucket_name=bucket.name
                ).data
                resources[compartment.name].setdefault("Bucket Objects", []).extend([
                    {"bucket_name": bucket.name, "object_name": obj.name} for obj in object_response.objects
                ])
            findings[compartment.name].extend(bucket_findings)

    # Export data to JSON
    with open("oci_buckets.json", "w") as file:
        json.dump({"resources": resources, "findings": findings}, file, indent=4)

    print("Resource discovery and validation completed. Results saved to 'oci_buckets.json'.")

    # Export data to Excel
    workbook = Workbook()

    # Add data sheets for each resource type
    for resource_type in ["Buckets", 
                        "Bucket Objects"]:
        sheet = workbook.create_sheet(title=resource_type)
        sheet.append(["Compartment", "Name", "ID"])
        for compartment, resource_data in resources.items():
            for item in resource_data.get(resource_type, []):
                sheet.append([compartment, item.get("name"), item.get("id", "N/A")])

    # Save the Excel workbook
    workbook.save("oci_buckets.xlsx")
    print("Detailed findings and visualizations saved to 'oci_buckets.xlsx'.")

except oci.exceptions.ServiceError as e:
    print(f"Service Error: {e}")
except Exception as e:
    print(f"Unexpected Error: {e}")
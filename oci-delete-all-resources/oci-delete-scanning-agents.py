import oci
import sys

compartment = "<compartment_ocid>"

def list(list_func, compartment):
    try:
        scans = oci.pagination.list_call_get_all_results(
            list_func,
            compartment
        ).data
        return scans
    except Exception as e:
        raise RuntimeError("Error listing scans in compartment " + compartment + ": " + str(e.args))

def delete_scans(delete_func, scans):
    for s in scans:
        try:
            delete_func(s.id)
        except Exception as e:
            raise RuntimeError("Error deleting scan " + s["id"] + ": " + str(e.args))

config = oci.config.from_file()

# Quick safety check
print("Using compartment " + compartment)
if input("Do you want to delete all scan results (host, port, CIS, container) in this compartment? [y/N]: ") != "y":
    sys.exit()

# Create the client from the config
client = oci.vulnerability_scanning.VulnerabilityScanningClient(config)

# Host agent scans
print("Listing agent scans to delete...")
host_scans = list(client.list_host_agent_scan_results, compartment)
print("Deleting " + str(len(host_scans)) + " host scans")
delete_scans(client.delete_host_agent_scan_result, host_scans)

# Host port scans
print("Listing port scans to delete...")
port_scans = list(client.list_host_port_scan_results, compartment)
print("Deleting " + str(len(port_scans)) + " port scans")
delete_scans(client.delete_host_port_scan_result, port_scans)

# Host CIS benchmarks
print("Listing CIS scans to delete...")
cis_benchmarks = list(client.list_host_cis_benchmark_scan_results, compartment)
print("Deleting " + str(len(cis_benchmarks)) + " CIS scans")
delete_scans(client.delete_host_cis_benchmark_scan_result, cis_benchmarks)

# Container scans
print("Listing container image scans to delete...")
container_scans = list(client.list_container_scan_results, compartment)
print("Deleting " + str(len(container_scans)) + " container image scans")
delete_scans(client.delete_container_scan_result, container_scans)
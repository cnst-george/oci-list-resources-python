
# OCI Cloud Automation Scripts

This repository contains a collection of Python scripts for automating various tasks in Oracle Cloud Infrastructure (OCI). These scripts are designed to streamline cloud management, improve security, optimize costs, and ensure compliance with OCI best practices.


## 📂 Folder Structure
```
├── oci-list-all                         # List all
├── oci-list-buckets                     # List buckets
├── oci-list-policies                    # List policies
├── oci-list-resources                   # List all by resources
├── oci-list-unused                      # List unused resources
├── oci-list-storage                     # List block volumes, File Systems
├── requirements.txt                     # Dependencies for running scripts
└── README.md                            # Documentation for the repository
```

## 🚀 Getting Started

### Prerequisites
Ensure you have the following installed before running the scripts:
- **Python 3.x**: Download from [python.org](https://www.python.org/downloads/)
- **OCI CLI**: Install using [OCI CLI setup guide](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm)
- **Authentication Setup**:
  - (OPTION.1) Ensure you have an OCI **config file** at `~/.oci/config` with required credentials.
  - Example config file:
    ```ini
    $ oci setup config
    [<profile_name>]
    user=ocid1.user.oc1..xxxxx
    fingerprint=xx:xx:xx:xx:xx:xx
    key_file=/path/to/your/private/api_key.pem
    tenancy=ocid1.tenancy.oc1..xxxxx
    region=eu-frankfurt-1
    ```
  - (OPTION.2) Ensure you have an OCI **security token** at `~/.oci/config` with a valid (unexpired) token.
  - Example config file:
    ```ini
    $ oci session authenticate
    [<profile_name>]
    fingerprint=xx:xx:xx:xx:xx:xx
    key_file=/path/to/your/private/api_key.pem
    tenancy=ocid1.tenancy.oc1..xxxxx
    region=eu-frankfurt-1
    security_token_file=/path/to/your/private/sessions/default/token
    ```
    - Refreshing a Token:
      ```ini
      oci session refresh --profile <profile_name>           
      ```
      
### 🔧 Installation
Clone this repository and install dependencies:
```bash
git clone <repository_link>
cd <repo_directory>
python3.12 -m venv --system-site-package ocipythonenv
source ocipythonenv/bin/activate
pip3 install -r requirements.txt
pip install --upgrade pip
```

## 📌 Usage
Each script is designed for a specific task in OCI. Below are examples of how to execute them.

### Listing Buckets
```bash
cd oci-list-buckets
python oci-list-buckets.py
```

### Listing Policies
```bash
cd oci-list-policies
python oci-list-policies.py
```

### Listing All Resources
```bash
cd oci-list-resources
python oci-list-resources.py
```

### Listing Unused Resources
```bas/
cd oci-list-unused 
python oci-list-unused.py
```

### Listing Storage Volumes (Attached/ Detached) and File Systems
```bash
cd oci-list-storage
python oci-list-storage.py
```

## 📊 Output Formats
The scripts generate reports in multiple formats for easy analysis:
- **CSV**:  Comma-separated values
- **XLSX**: Structured data for Excel/Google Sheets.
- **JSON**: Machine-readable structured format.
- **Log files**: Debugging and execution logs.

## 🔒 Security Considerations
- Ensure that **API keys** and **sensitive credentials** are securely stored.
- Use **OCI Vault** for managing secrets if required.
- Restrict **IAM permissions** to allow only necessary access.


## 📬 Contact
For any questions or issues, feel free to raise an **Issue** or contact:
📧 **george.constantin@oracle.com**
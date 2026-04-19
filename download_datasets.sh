#!/bin/bash
# Dedicated tool to download raw datasets for Bigdata project

export HF_HUB_ENABLE_HF_TRANSFER=1

echo "===================================================="
echo "   Bigdata Raw Dataset Download Tool               "
echo "===================================================="

# Check if huggingface-cli is installed
if ! command -v huggingface-cli &> /dev/null; then
    echo "Error: huggingface-cli is not installed. Please run 'pip install huggingface_hub[cli] hf_transfer'"
    exit 1
fi

# Function to download a dataset with confirmation
download_dataset() {
    local name=$1
    local repo=$2
    local dest=$3
    local size=$4

    read -p "Download $name (~$size)? (y/N): " choice
    if [[ "$choice" =~ ^[Yy]$ ]]; then
        echo "Starting download for $name from $repo..."
        huggingface-cli download "$repo" \
            --repo-type dataset \
            --local-dir "$dest" \
            --cache-dir "$dest/.cache"
        echo "$name download complete."
    else
        echo "Skipping $name."
    fi
}

# 1. RVL-CDIP
download_dataset "RVL-CDIP (Scanned Documents)" "rvl_cdip" "datasets/rvl-cdip" "48GB"

# 2. Vietnamese Legal Documents
download_dataset "Vietnamese Legal Documents" "th1nhng0/vietnamese-legal-documents" "datasets/vi-legal" "411MB"

echo "===================================================="
echo "Dataset checks complete."

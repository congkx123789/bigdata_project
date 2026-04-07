#!/bin/bash
# Script to resume RVL-CDIP download
export HF_HUB_ENABLE_HF_TRANSFER=1
echo "Resuming RVL-CDIP download..."
huggingface-cli download rvl_cdip \
    --repo-type dataset \
    --local-dir datasets/rvl-cdip \
    --cache-dir datasets/rvl-cdip/.cache

#!/bin/bash
echo "--- Process Status ---"
ps aux | grep huggingface
echo "--- Network Connectivity ---"
curl -I https://huggingface.co
echo "--- Lock Check ---"
ls -la datasets/rvl-cdip/.cache/huggingface/download/data/*.lock
echo "--- Incomplete File History ---"
ls -la datasets/rvl-cdip/.cache/huggingface/download/data/*.incomplete

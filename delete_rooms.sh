#!/bin/bash
# Script to delete specific room hubs from SoftEther VPN server

echo "=== Starting VPN Room Hub Deletion ==="

# List of room hubs to delete
ROOM_HUBS=("room_1" "room_12" "room_17" "room_18")

SUCCESS_COUNT=0
FAILURE_COUNT=0

# Function to delete a hub
delete_hub() {
    local hub_name=$1
    echo "Deleting hub: $hub_name"
    
    # Run the command with a timeout
    timeout 10s /usr/local/vpnserver/vpncmd /SERVER localhost:5555 /ADMINHUB:$hub_name /CMD HubDelete $hub_name
    
    if [ $? -eq 0 ]; then
        echo "Successfully deleted hub: $hub_name"
        return 0
    else
        echo "Failed to delete hub: $hub_name"
        return 1
    fi
}

# Delete each hub
for hub in "${ROOM_HUBS[@]}"; do
    if delete_hub "$hub"; then
        ((SUCCESS_COUNT++))
    else
        ((FAILURE_COUNT++))
    fi
    
    # Wait a bit between deletion attempts
    sleep 1
done

echo "=== Room Hub Deletion Summary ==="
echo "Total room hubs processed: ${#ROOM_HUBS[@]}"
echo "Successfully deleted: $SUCCESS_COUNT"
echo "Failed deletions: $FAILURE_COUNT"

if [ $SUCCESS_COUNT -gt 0 ]; then
    echo "=== VPN Room Hub Deletion Completed with status: SUCCESS ==="
    exit 0
else
    echo "=== VPN Room Hub Deletion Completed with status: FAILURE ==="
    exit 1
fi 
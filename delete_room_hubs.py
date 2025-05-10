#!/usr/bin/env python3
"""
Script to delete specific room hubs from SoftEther VPN server
"""
import logging
import sys
import subprocess
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# List of room hubs to delete
ROOM_HUBS = ["room_1", "room_12", "room_17", "room_18"]

def delete_hub(hub_name):
    """Delete a specific hub from the VPN server"""
    logger.info(f"Deleting hub: {hub_name}")
    
    cmd = ["/usr/local/vpnserver/vpncmd", "/SERVER", "localhost:5555", "/CMD", "HubDelete", hub_name]
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True
        )
        
        # Give it some time to complete
        time.sleep(5)
        
        # Check if process is still running and kill it if so
        if process.poll() is None:
            logger.warning(f"Command still running for hub {hub_name}, terminating process")
            process.terminate()
            return False
        
        # If process completed
        if process.returncode == 0:
            logger.info(f"Successfully deleted hub: {hub_name}")
            return True
        else:
            logger.error(f"Failed to delete hub: {hub_name}")
            return False
            
    except Exception as e:
        logger.error(f"Error deleting hub {hub_name}: {str(e)}")
        return False

def main():
    """Main function to delete all specified room hubs"""
    logger.info("=== Starting VPN Room Hub Deletion ===")
    
    success_count = 0
    failure_count = 0
    
    for hub in ROOM_HUBS:
        if delete_hub(hub):
            success_count += 1
        else:
            failure_count += 1
        
        # Wait a bit between deletion attempts
        time.sleep(1)
    
    logger.info("=== Room Hub Deletion Summary ===")
    logger.info(f"Total room hubs processed: {len(ROOM_HUBS)}")
    logger.info(f"Successfully deleted: {success_count}")
    logger.info(f"Failed deletions: {failure_count}")
    
    return success_count > 0

if __name__ == "__main__":
    success = main()
    exit_code = 0 if success else 1
    logger.info(f"=== VPN Room Hub Deletion Completed with status: {'SUCCESS' if success else 'FAILURE'} ===")
    sys.exit(exit_code) 